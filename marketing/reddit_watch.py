#!/usr/bin/env python3
"""Watch Reddit for people asking about Odoo telephony, and notify.

Reddit blocks anonymous JSON endpoints (403) but still serves Atom/RSS, so this
polls `search.rss`. That feed is rate limited hard — a second request 45 seconds
later already returns 429 — so queries are paced and retried rather than fired in
a burst. A full pass takes several minutes by design; run it hourly from cron,
not every minute.

    python3 marketing/reddit_watch.py                 # one pass, digest to stdout
    python3 marketing/reddit_watch.py --dry-run       # do not record what was seen
    python3 marketing/reddit_watch.py --telegram      # also push to Telegram
    python3 marketing/reddit_watch.py --queries 2     # short pass, for testing

Telegram delivery needs two environment variables:
    TELEGRAM_BOT_TOKEN   from @BotFather
    TELEGRAM_CHAT_ID     your user or group id

Tuning knobs: REDDIT_WATCH_PAUSE (seconds between queries, default 75),
REDDIT_WATCH_STATE (path to the seen-ids file).
"""

import argparse
import html
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent
STATE = pathlib.Path(os.environ.get("REDDIT_WATCH_STATE", ROOT / "out" / "reddit_seen.json"))
ATOM = {"a": "http://www.w3.org/2005/Atom"}
UA = "oduist-connect-monitor/1.0 (Odoo telephony lead monitor)"
PAUSE = int(os.environ.get("REDDIT_WATCH_PAUSE", "75"))
RETRY_WAIT = 90
MAX_RETRIES = 2

# tier A: someone is looking for what we sell. tier B: a question we can answer,
# which is how we earn the right to mention the product at all.
QUERIES = [
    ("A", "odoo + telephony", 'odoo (voip OR telephony OR pbx OR sip)'),
    ("A", "odoo + a provider", 'odoo (twilio OR telnyx OR asterisk OR freeswitch OR 3cx OR vonage)'),
    ("A", "odoo phone system", 'odoo "phone system"'),
    ("A", "odoo call centre", 'odoo ("call center" OR "call centre" OR "click to call")'),
    ("A", "odoo messaging", 'odoo (whatsapp OR sms) integration'),
    ("A", "odoo voice ai", 'odoo (voice agent OR "ai receptionist" OR transcription)'),
    ("B", "crm <-> pbx", '(voip OR pbx OR sip) "crm integration"'),
    ("B", "erp telephony", 'erp (telephony OR "phone system") integration'),
]

INTENT = re.compile(
    r"\b(looking for|recommend|anyone using|anyone know|how do i|how to|"
    r"need a|need an|best way|suggestions|advice|is there a|alternatives?|"
    r"struggling|can't get|cannot get|doesn't work|does not work|help)\b",
    re.I,
)
VENDOR_NEWS = re.compile(
    r"\b(now (natively )?integrat(es|ed)|integration is (now )?(live|available)|"
    r"we('ve| have) (launched|released|built)|introducing|announcing|"
    r"is now available|new release|we are excited)\b",
    re.I,
)
ODOO = re.compile(r"\bodoo\b", re.I)
# Unambiguous telephony terms: seeing one is enough to care about the post.
TEL_STRONG = re.compile(
    r"\b(voip|telephony|pbx|twilio|telnyx|asterisk|freeswitch|freepbx|"
    r"3cx|vonage|infobip|livekit|softphone|call cent(er|re)|"
    r"click.?to.?call|ivr|dialer|phone system|sip trunk)\b",
    re.I,
)
# Ambiguous in ordinary English or in consumer chat ("take a sip", "send an
# sms"), so these only count when Odoo is mentioned too.
TEL_WEAK = re.compile(r"\b(sip|sms|whatsapp|extension|dial)\b", re.I)
PRIORITY_SUBS = {
    "odoo", "voip", "freepbx", "asterisk", "crm", "sysadmin", "telephony",
    "smallbusiness", "msp", "erp",
}


def fetch(query, limit=25):
    """Fetch one search as Atom, retrying through Reddit's rate limiting."""
    url = "https://www.reddit.com/search.rss?" + urllib.parse.urlencode(
        {"q": query, "sort": "new", "t": "month", "limit": limit}
    )
    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return ET.fromstring(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < MAX_RETRIES:
                print(f"  rate limited, waiting {RETRY_WAIT}s", file=sys.stderr)
                time.sleep(RETRY_WAIT)
                continue
            print(f"  HTTP {exc.code} for {query!r}", file=sys.stderr)
            return None
        except (urllib.error.URLError, ET.ParseError) as exc:
            print(f"  failed {query!r}: {exc}", file=sys.stderr)
            return None
    return None


def parse(root):
    for entry in root.findall("a:entry", ATOM):
        # Reddit search mixes subreddit rows (t5_) in with posts (t3_).
        if not (entry.findtext("a:id", "", ATOM) or "").startswith("t3_"):
            continue
        link = entry.find("a:link", ATOM)
        author = entry.find("a:author/a:name", ATOM)
        category = entry.find("a:category", ATOM)
        yield {
            "id": entry.findtext("a:id", "", ATOM),
            "title": (entry.findtext("a:title", "", ATOM) or "").strip(),
            "url": link.get("href") if link is not None else "",
            "author": author.text if author is not None else "",
            "updated": entry.findtext("a:updated", "", ATOM),
            "subreddit": (category.get("label") if category is not None else "").removeprefix("r/"),
            "body": re.sub(r"<[^>]+>", " ", entry.findtext("a:content", "", ATOM) or ""),
        }


def classify(post, tier):
    """Score a post and label what kind of attention it deserves."""
    text = f"{post['title']} {post['body']}"
    has_odoo = bool(ODOO.search(text))
    strong = bool(TEL_STRONG.search(text))
    weak = bool(TEL_WEAK.search(text))
    # A weak term on its own is noise, so it never carries a post by itself.
    if not (has_odoo or strong):
        return None

    score, why = 0, []
    if has_odoo and strong:
        score += 4
        why.append("odoo+telephony")
    elif has_odoo and weak:
        score += 3
        why.append("odoo+maybe telephony")
    elif has_odoo:
        score += 2
        why.append("odoo")
    else:
        score += 1
        why.append("telephony")

    if VENDOR_NEWS.search(post["title"]):
        kind = "competitor"
        why.append("vendor announcement")
    elif INTENT.search(text) or post["title"].rstrip().endswith("?"):
        kind = "lead"
        score += 3
        why.append("asking for help")
    else:
        kind = "discussion"

    if post["subreddit"].lower() in PRIORITY_SUBS:
        score += 1
        why.append(f"r/{post['subreddit']}")
    if tier == "A":
        score += 1

    return {**post, "kind": kind, "score": score, "why": why}


def load_seen():
    try:
        return set(json.loads(STATE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return set()


def save_seen(seen):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    # keep the file from growing without bound
    STATE.write_text(json.dumps(sorted(seen)[-5000:]), encoding="utf-8")


ICON = {"lead": "🔥", "competitor": "👀", "discussion": "💬"}


def render(hits):
    if not hits:
        return "No new Reddit posts matched."
    order = {"lead": 0, "competitor": 1, "discussion": 2}
    hits.sort(key=lambda h: (order[h["kind"]], -h["score"]))
    lines = [f"<b>Reddit watch — {len(hits)} new</b>", ""]
    for h in hits:
        title = html.escape(h["title"][:150])
        lines.append(
            f"{ICON[h['kind']]} <b>{h['kind'].upper()}</b> · score {h['score']} · "
            f"r/{html.escape(h['subreddit'])}\n"
            f"<a href=\"{html.escape(h['url'])}\">{title}</a>\n"
            f"<i>{html.escape(', '.join(h['why']))}</i>\n"
        )
    return "\n".join(lines)


def send_telegram(text):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set, skipping push", file=sys.stderr)
        return False
    # Telegram caps a message at 4096 characters
    for chunk in [text[i:i + 3800] for i in range(0, len(text), 3800)]:
        payload = urllib.parse.urlencode({
            "chat_id": chat, "text": chunk, "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=payload
        )
        try:
            urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.URLError as exc:
            print(f"telegram push failed: {exc}", file=sys.stderr)
            return False
    return True


def main():
    ap = argparse.ArgumentParser(description="Watch Reddit for Odoo telephony questions.")
    ap.add_argument("--dry-run", action="store_true", help="do not record seen ids")
    ap.add_argument("--telegram", action="store_true", help="push the digest to Telegram")
    ap.add_argument("--queries", type=int, help="only run the first N queries")
    ap.add_argument("--min-score", type=int, default=4, help="drop weaker matches (default 4)")
    args = ap.parse_args()

    seen = load_seen()
    queries = QUERIES[: args.queries] if args.queries else QUERIES
    hits, fresh = [], set()

    for i, (tier, label, query) in enumerate(queries):
        print(f"[{i + 1}/{len(queries)}] {label}", file=sys.stderr)
        root = fetch(query)
        if root is not None:
            for post in parse(root):
                if not post["id"] or post["id"] in seen or post["id"] in fresh:
                    continue
                scored = classify(post, tier)
                if scored and scored["score"] >= args.min_score:
                    hits.append(scored)
                fresh.add(post["id"])
        if i < len(queries) - 1:
            time.sleep(PAUSE)

    print(render(hits))
    if args.telegram and hits:
        send_telegram(render(hits))
    if not args.dry_run:
        save_seen(seen | fresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
