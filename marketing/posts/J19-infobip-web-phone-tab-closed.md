---
id: J19
title: Infobip web phone misses calls when the tab is closed
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_infobip/docs/admin/infobip-setup.md]
---

## Post

"My Infobip web phone missed three calls and never even rang." 🔕

Not a bug, and not something a setting will fix. The Infobip JS SDK has **no push wake-up**: the browser receives inbound calls only while a tab with the web phone is open. Close the tab, quit the browser, or shut the laptop, and there is nothing left listening. The call is offered to a client that isn't there.

The documented answer is to stop relying on the browser alone. On **Connect → Users → Infobip Phone**, add an **External Phone** in E.164 with its own priority and ring timeout. Odoo rings destinations by priority, and the mobile picks up whatever the browser can't.

Unrouted or exhausted calls hear a spoken message and are hung up — configure the fallback before someone notices.

How do you cover agents who close their browser? 👇

#Odoo #Infobip #WebRTC

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Infobip",
  "headline": "No tab open,",
  "headline_grad": "no incoming call.",
  "lede": "The JS SDK has no push wake-up. Add an *External Phone* ring step so the mobile catches what the browser can't.",
  "columns": ["Web phone", "External"],
  "rows": [
    {"f": "Tab with the web phone is open", "m": ["✓", "✓"]},
    {"f": "Tab closed", "m": ["—", "✓"]},
    {"f": "Browser quit or laptop asleep", "m": ["—", "✓"]},
    {"f": "Agent away from the desk", "m": ["—", "✓"]},
    {"f": "Works with no extra configuration", "m": ["✓", "—"]}
  ],
  "footer": "Ring priority and timeouts run on the Infobip platform, not in Odoo"
}
```

## Notes

The plan called this "background tab". The doc says the tab must be **open** —
it does not claim a backgrounded tab misses calls, so the post is written around
a closed tab / closed browser instead. Do not add a foreground/background claim.
