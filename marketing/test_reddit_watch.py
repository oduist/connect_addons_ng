#!/usr/bin/env python3
"""Regression tests for the Reddit watcher's relevance rules.

Every fixture below is a real result from a production run. The noise cases are
what the first unfiltered digest surfaced; they are kept here so a future tweak
to the scoring cannot quietly let them back in.

    python3 marketing/test_reddit_watch.py
"""

import importlib.util
import pathlib
import sys
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location(
    "reddit_watch", pathlib.Path(__file__).with_name("reddit_watch.py")
)
rw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rw)

KEEP, DROP = "keep", "drop"

# (name, subreddit, title, body, expected, expected_kind)
CASES = [
    # --- genuine finds, must always survive -------------------------------
    ("odoo ai assistant question", "Odoo",
     "What would you actually want from an AI sales assistant in Odoo?",
     "Curious what people would use it for.", KEEP, "lead"),
    ("voip + crm need", "CRMSoftware",
     "I need a VoIP + CRM setup that works? Looking at voip crm integration",
     "We need click to call and call logging.", KEEP, "lead"),
    ("competitor announcement", "3CXOfficial",
     "3CX + Odoo CRM: Now Natively Integrated with 3CX",
     "The integration is live.", KEEP, "competitor"),
    ("plain odoo telephony ask", "Odoo",
     "Need a phone system that works with Odoo?",
     "Looking for recommendations, we use Odoo.", KEEP, "lead"),

    # --- noise from the first live digest ---------------------------------
    ("profile feed: vendor blog", "u_perfonec16",
     "Odoo v20 coming October 2026 - full breakdown of new features for UAE businesses",
     "AI integration, construction updates.", DROP, None),
    ("profile feed: generic sales", "u_techtalkstreak_",
     "What's the small tool/process fix that quietly gave your sales team a huge boost?",
     "Tell me about your dialer.", DROP, None),
    ("profile feed: agency ad", "u_ecosmob_Technologies",
     "Looking for the Best Telecom Software Development Company? Here's What We've Learned",
     "We build VoIP solutions.", DROP, None),
    ("seo listicle 1", "RankPine",
     "Best Surfer SEO Alternatives in 2026 - honest review",
     "Tools compared, including Odoo.", DROP, None),
    ("seo listicle 2", "RankPine",
     "Best Content Automation Platforms for SEO: Find the Leaking Handoff",
     "Odoo mentioned in passing.", DROP, None),
    ("seo listicle 3", "RankPine",
     "Best SEO Automation Software in 2026: What Can You Actually Leave Unattended?",
     "Odoo is listed.", DROP, None),
    ("self-promo post", "ZentechAI",
     "A New Digital Home for My Work in Communication & Software Engineering",
     "I write about telephony and software.", DROP, None),

    # --- previously fixed defects, kept as guards -------------------------
    ("drink review says 'sip'", "AlaniNu",
     "Alani + Elixir Review #11: Sherbet Swirl",
     "I took a sip and it was great.", DROP, None),
    ("unrelated", "cats", "My cat is cute", "nothing", DROP, None),
]

MIN_SCORE = 4


def run():
    failures = []
    for name, sub, title, body, expected, kind in CASES:
        post = {"id": "t3_x", "title": title, "body": body, "subreddit": sub,
                "url": "", "author": "", "updated": ""}
        result = rw.classify(post, "A")
        kept = result is not None and result["score"] >= MIN_SCORE
        got = KEEP if kept else DROP
        if got != expected:
            failures.append(
                f"{name}: expected {expected}, got {got}"
                + (f" (score {result['score']}, {result['kind']})" if result else "")
            )
        elif kept and kind and result["kind"] != kind:
            failures.append(f"{name}: expected kind {kind}, got {result['kind']}")
        flag = "ok  " if got == expected else "FAIL"
        score = f"{result['score']:>2}" if result else " -"
        print(f"  {flag} [{score}] {name}")

    # a subreddit row rather than a post
    atom = ('<feed xmlns="http://www.w3.org/2005/Atom">'
            '<entry><id>t5_a</id><title>r/Odoo</title>'
            '<link href="https://www.reddit.com/r/Odoo/"/>'
            '<category term="Odoo" label="r/Odoo"/><content>x</content></entry>'
            '<entry><id>t3_b</id><title>Odoo pbx help</title>'
            '<link href="https://reddit.com/x"/>'
            '<category term="VOIP" label="r/VOIP"/><content>x</content></entry></feed>')
    kept_ids = [p["id"] for p in rw.parse(ET.fromstring(atom))]
    if kept_ids != ["t3_b"]:
        failures.append(f"parse(): expected only t3_b, got {kept_ids}")
    print(f"  {'ok  ' if kept_ids == ['t3_b'] else 'FAIL'} [  ] subreddit rows filtered")

    print()
    if failures:
        print(f"{len(failures)} failure(s):")
        for f in failures:
            print("  -", f)
        return 1
    print(f"all {len(CASES) + 1} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
