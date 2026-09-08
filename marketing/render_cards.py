#!/usr/bin/env python3
"""Render social-media cards for Oduist Connect posts.

Each post in ``marketing/posts/*.md`` carries a fenced ``json`` block under its
``## Card`` heading describing the card. This script turns that spec into a
1200x627 HTML page and, with ``--png``, screenshots it through agent-browser.

    python3 marketing/render_cards.py                 # all posts -> HTML
    python3 marketing/render_cards.py D01 D02 --png   # two posts -> HTML + PNG

Card templates (``template`` key):

  thesis      headline + a grid of "periodic table" module tiles
  comparison  headline + a feature table with one column per product
  diagram     headline + stacked nodes joined by a labelled connector
  dialog      headline + chat bubbles, optional confirmation badge

Common keys: kicker, headline, headline_grad, lede, footer, url, accent
("cyan" | "purple"). Per-template keys are documented in marketing/README.md.
"""

import argparse
import html
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
POSTS = ROOT / "posts"
OUT = ROOT / "out"

# Brand palette, taken from the Apps Store description pages.
PALETTE = {
    "cyan": "#2dd4ff",
    "purple": "#7c83ff",
    "magenta": "#e16bff",
    "provider": "#3987e5",
    "app": "#199e70",
    "memory": "#c98500",
    "core": "#e66767",
}

CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 1200px; height: 627px; overflow: hidden; }
  body {
    font-family: "Inter", "Segoe UI", -apple-system, Arial, sans-serif;
    background: #0e0f14; color: #eef0fa; position: relative;
  }
  .glow { position: absolute; border-radius: 50%; filter: blur(120px); opacity: .35; }
  .glow.a { width: 500px; height: 500px; top: -220px; right: -120px; }
  .glow.b { width: 420px; height: 420px; background: #e16bff; bottom: -240px; left: -140px; opacity: .22; }

  .wrap { position: relative; z-index: 2; display: flex; height: 100%;
          padding: 60px 72px 96px; align-items: center; gap: 48px; }
  .copy { flex: 1.2; }
  .kicker { font-size: 19px; letter-spacing: .28em; text-transform: uppercase;
            font-weight: 600; margin-bottom: 24px; }
  h1 { line-height: 1.05; font-weight: 800; letter-spacing: -0.02em; }
  h1 .grad { -webkit-background-clip: text; background-clip: text; color: transparent; }
  .lede { margin-top: 24px; font-size: 25px; line-height: 1.45; color: #9aa1bd; max-width: 560px; }
  .lede b { color: #eef0fa; font-weight: 600; }

  /* thesis */
  .grid { flex: 1; display: grid; grid-template-columns: repeat(3, 128px); gap: 14px; justify-content: end; }
  .tile { width: 128px; height: 128px; border-radius: 18px; background: #14161f;
          border: 1px solid rgba(238,240,250,.08); padding: 14px 16px; display: flex;
          flex-direction: column; justify-content: space-between; border-top: 3px solid var(--c); }
  .tile .sym { font-size: 34px; font-weight: 800; color: var(--c); }
  .tile .nm { font-size: 15px; color: #9aa1bd; font-weight: 500; line-height: 1.2; }
  .tile.hero { background: linear-gradient(135deg, rgba(45,212,255,.16), rgba(225,107,255,.14));
               border-color: rgba(45,212,255,.45); }

  /* comparison */
  .table { flex: 1; background: #14161f; border: 1px solid rgba(238,240,250,.08);
           border-radius: 20px; padding: 26px 30px; }
  .thead, .row { display: grid; align-items: center; }
  .thead { font-size: 18px; color: #9aa1bd; font-weight: 600;
           padding-bottom: 12px; border-bottom: 1px solid rgba(238,240,250,.1); }
  .thead .col { text-align: center; }
  .thead .col.hl { color: #2dd4ff; }
  .row { font-size: 20px; padding: 11px 0; border-bottom: 1px solid rgba(238,240,250,.05); }
  .row:last-child { border-bottom: none; }
  .row .f { color: #eef0fa; font-weight: 500; }
  .row .m { text-align: center; font-size: 23px; }
  .yes { color: #2dd4ff; } .no { color: #5b6184; }

  /* diagram */
  .diagram { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }
  .node { width: 300px; border-radius: 18px; background: #14161f;
          border: 1px solid rgba(238,240,250,.08); padding: 20px 24px; text-align: center; }
  .node .t { font-size: 28px; font-weight: 800; color: var(--c); }
  .node .s { font-size: 16px; color: #9aa1bd; margin-top: 4px; }
  .link { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 4px 0; }
  .link .arrow { font-size: 28px; color: #2dd4ff; line-height: 1; }
  .link .lbl { background: rgba(45,212,255,.1); border: 1px solid rgba(45,212,255,.3);
               color: #2dd4ff; border-radius: 999px; padding: 4px 14px; font-weight: 600; font-size: 15px; }

  /* dialog */
  .chat { flex: 1; display: flex; flex-direction: column; gap: 13px; }
  .bubble { border-radius: 18px; padding: 16px 20px; font-size: 20px; line-height: 1.4; max-width: 430px; }
  .bubble .who { font-size: 14px; color: #9aa1bd; margin-bottom: 5px; font-weight: 600;
                 letter-spacing: .06em; text-transform: uppercase; }
  .left { background: #14161f; border: 1px solid rgba(238,240,250,.08); align-self: flex-start; }
  .right { background: linear-gradient(135deg, rgba(124,131,255,.18), rgba(225,107,255,.16));
           border: 1px solid rgba(124,131,255,.4); align-self: flex-end; }
  .right .who { color: #9085e9; }
  .badge { align-self: flex-end; background: rgba(25,158,112,.12); border: 1px solid rgba(25,158,112,.4);
           color: #4ade9d; border-radius: 999px; padding: 8px 18px; font-size: 18px; font-weight: 600; }

  .foot { position: absolute; z-index: 2; left: 72px; right: 72px; bottom: 32px;
          display: flex; justify-content: space-between; align-items: center;
          font-size: 18px; color: #9aa1bd; gap: 24px; }
  .foot .url { color: #2dd4ff; font-weight: 600; white-space: nowrap; }
"""

# Default site URL shown in the card footer. Override per post with "url".
DEFAULT_URL = "oduist.com"


def esc(value):
    return html.escape(str(value), quote=False)


def headline_size(card):
    """Shrink the headline as it gets longer so it never overflows the card."""
    text = f"{card.get('headline', '')} {card.get('headline_grad', '')}".strip()
    length = len(text)
    if length <= 24:
        return 72
    if length <= 38:
        return 64
    if length <= 52:
        return 56
    return 48


def render_headline(card):
    grad_from = PALETTE["cyan"] if card.get("accent", "cyan") == "cyan" else PALETTE["purple"]
    # background-image, not the background shorthand: the shorthand would reset
    # background-clip back to border-box and the gradient would paint a block.
    grad = (
        f"background-image: linear-gradient(90deg, {grad_from}, "
        f"{PALETTE['purple']} 55%, {PALETTE['magenta']});"
    )
    parts = []
    if card.get("headline"):
        parts.append(esc(card["headline"]))
    if card.get("headline_grad"):
        parts.append(f'<span class="grad" style="{grad}">{esc(card["headline_grad"])}</span>')
    return "<br>".join(parts)


def render_tiles(card):
    tiles = []
    for tile in card.get("tiles", []):
        color = PALETTE.get(tile.get("c", "provider"), tile.get("c", PALETTE["provider"]))
        klass = "tile hero" if tile.get("hero") else "tile"
        tiles.append(
            f'<div class="{klass}" style="--c:{color}">'
            f'<span class="sym">{esc(tile.get("sym", ""))}</span>'
            f'<span class="nm">{esc(tile.get("nm", ""))}</span></div>'
        )
    return f'<div class="grid">{"".join(tiles)}</div>'


def render_table(card):
    """A comparison table that shrinks to fit rather than overflowing the card.

    Three-column tables squeeze the feature column hard, so both the mark
    columns and the type scale down as the table gets denser.
    """
    columns = card.get("columns", [])
    rows = card.get("rows", [])
    ncols = max(len(columns), 1)
    colw = 120 if ncols <= 2 else 96
    widths = f"1fr {' '.join([f'{colw}px'] * ncols)}"

    longest = max((len(r.get("f", "")) for r in rows), default=0)
    size = 20
    if ncols >= 3:
        size = 18
    if longest > 26 or len(rows) >= 7:
        size = min(size, 17)
    pad = 8 if len(rows) >= 6 else 11

    head = "".join(
        f'<span class="col{" hl" if i == len(columns) - 1 else ""}">{esc(c)}</span>'
        for i, c in enumerate(columns)
    )
    body = []
    for row in rows:
        marks = "".join(
            f'<span class="m {"yes" if m in ("✓", "yes", True) else "no"}">'
            f'{"✓" if m in ("✓", "yes", True) else "—"}</span>'
            for m in row.get("m", [])
        )
        body.append(
            f'<div class="row" style="grid-template-columns:{widths};'
            f'font-size:{size}px;padding:{pad}px 0">'
            f'<span class="f">{esc(row.get("f", ""))}</span>{marks}</div>'
        )
    return (
        f'<div class="table"><div class="thead" style="grid-template-columns:{widths}">'
        f'<span></span>{head}</div>{"".join(body)}</div>'
    )


def layout_flex(card):
    """Width split between the copy column and the card artwork."""
    if card.get("template") == "comparison" and len(card.get("columns", [])) >= 3:
        return 1.0, 1.7
    return 1.2, 1.0


def render_diagram(card):
    blocks = []
    nodes = card.get("nodes", [])
    for i, node in enumerate(nodes):
        color = PALETTE.get(node.get("c", "provider"), node.get("c", PALETTE["provider"]))
        blocks.append(
            f'<div class="node" style="--c:{color}"><div class="t">{esc(node.get("t", ""))}</div>'
            f'<div class="s">{esc(node.get("s", ""))}</div></div>'
        )
        if i < len(nodes) - 1:
            label = card.get("link_label", "Connect")
            blocks.append(
                f'<div class="link"><span class="arrow">⇅</span>'
                f'<span class="lbl">{esc(label)}</span></div>'
            )
    return f'<div class="diagram">{"".join(blocks)}</div>'


def render_dialog(card):
    blocks = []
    for bubble in card.get("bubbles", []):
        side = "right" if bubble.get("side") == "right" else "left"
        who = f'<div class="who">{esc(bubble["who"])}</div>' if bubble.get("who") else ""
        blocks.append(f'<div class="bubble {side}">{who}{esc(bubble.get("text", ""))}</div>')
    if card.get("badge"):
        blocks.append(f'<div class="badge">{esc(card["badge"])}</div>')
    return f'<div class="chat">{"".join(blocks)}</div>'


RENDERERS = {
    "thesis": render_tiles,
    "comparison": render_table,
    "diagram": render_diagram,
    "dialog": render_dialog,
}


def render_html(card):
    template = card.get("template", "thesis")
    if template not in RENDERERS:
        raise ValueError(f"unknown card template: {template}")
    accent = PALETTE["cyan"] if card.get("accent", "cyan") == "cyan" else PALETTE["purple"]
    lede = esc(card.get("lede", "")).replace("**", "").replace("`", "")
    # Allow *bold* emphasis in the lede without permitting raw HTML.
    lede = re.sub(r"\*(.+?)\*", r"<b>\1</b>", lede)
    copy_flex, side_flex = layout_flex(card)
    side = RENDERERS[template](card).replace(
        'class="table"', f'class="table" style="flex:{side_flex}"', 1
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body>
  <div class="glow a" style="background:{accent}"></div>
  <div class="glow b"></div>
  <div class="wrap">
    <div class="copy" style="flex:{copy_flex}">
      <div class="kicker" style="color:{accent}">{esc(card.get('kicker', 'Oduist Connect'))}</div>
      <h1 style="font-size:{headline_size(card)}px">{render_headline(card)}</h1>
      <div class="lede">{lede}</div>
    </div>
    {side}
  </div>
  <div class="foot">
    <span>{esc(card.get('footer', ''))}</span>
    <span class="url">{esc(card.get('url', DEFAULT_URL))}</span>
  </div>
</body></html>
"""


CARD_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def load_card(path):
    match = CARD_RE.search(path.read_text(encoding="utf-8"))
    if not match:
        return None
    return json.loads(match.group(1))


def main():
    parser = argparse.ArgumentParser(description="Render Oduist Connect social cards.")
    parser.add_argument("ids", nargs="*", help="post id prefixes, e.g. D01 (default: all)")
    parser.add_argument("--png", action="store_true", help="also screenshot via agent-browser")
    args = parser.parse_args()

    html_dir = OUT / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    if args.png:
        (OUT / "png").mkdir(parents=True, exist_ok=True)

    paths = sorted(p for p in POSTS.glob("*.md") if not p.name.startswith("_"))
    if args.ids:
        paths = [p for p in paths if any(p.name.startswith(i) for i in args.ids)]

    rendered, skipped, failed = [], [], []
    for path in paths:
        try:
            card = load_card(path)
        except json.JSONDecodeError as exc:
            failed.append(f"{path.name}: bad JSON ({exc})")
            continue
        if card is None:
            skipped.append(path.name)
            continue
        try:
            markup = render_html(card)
        except (ValueError, KeyError) as exc:
            failed.append(f"{path.name}: {exc}")
            continue
        target = html_dir / f"{path.stem}.html"
        target.write_text(markup, encoding="utf-8")
        rendered.append(target)

    print(f"rendered {len(rendered)} HTML card(s) into {html_dir}")
    if skipped:
        print(f"skipped {len(skipped)} post(s) with no card block")
    for problem in failed:
        print(f"FAILED {problem}", file=sys.stderr)

    if args.png and rendered:
        subprocess.run(["agent-browser", "set", "viewport", "1200", "627"], check=False)
        for target in rendered:
            png = OUT / "png" / f"{target.stem}.png"
            subprocess.run(["agent-browser", "open", f"file://{target}"], check=False)
            subprocess.run(["agent-browser", "screenshot", str(png)], check=False)
        subprocess.run(["agent-browser", "close"], check=False)
        print(f"rendered {len(rendered)} PNG(s) into {OUT / 'png'}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
