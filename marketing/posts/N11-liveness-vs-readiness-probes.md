---
id: N11
title: Liveness vs readiness — two health endpoints
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_freeswitch/docs/admin/firewall.md, specs/decisions/017-firewall-healthz-real-check.md]
---

## Post

Wire a dependency check to a liveness probe and you've built a machine that kills your container every time an upstream hiccups. While the upstream is recovering. In a loop. 🔁

That failure mode is why our SIP firewall service exposes **two** health endpoints, not one:

🫀 `/healthz` — process-level liveness. No auth, returns 200 for as long as the service is up, and it does **not** care whether Odoo is reachable. This is the one you give the orchestrator
🩺 `/firewall/healthz` — dependency-aware readiness. Returns `{"status":"ok","odoo":true,"esl":true}` with 200, or 503 with the individual flags when Odoo or the FreeSWITCH ESL connection is down. This is the one you give Uptime Kuma or a blackbox exporter
📊 `/firewall/api/heartbeat` — the rich JSON for the dashboard, and the only one that needs credentials

Liveness answers "should I restart this?". Readiness answers "should I page someone?". They are different questions and they deserve different URLs.

Do you split them, or run one endpoint and hope? 👇

#Kubernetes #Docker #SRE #Odoo #Observability

## Card

```json
{
  "template": "comparison",
  "kicker": "Oduist Connect · Firewall service",
  "headline": "Two questions.",
  "headline_grad": "Two endpoints.",
  "lede": "*Liveness must not flap when a dependency is down* — otherwise the orchestrator restarts you while the upstream recovers.",
  "columns": ["/healthz", "readiness"],
  "rows": [
    {"f": "Auth required", "m": ["—", "—"]},
    {"f": "Checks Odoo reachability", "m": ["—", "✓"]},
    {"f": "Checks FreeSWITCH ESL", "m": ["—", "✓"]},
    {"f": "Can return 503", "m": ["—", "✓"]},
    {"f": "Wire to orchestrator probe", "m": ["✓", "—"]},
    {"f": "Wire to external monitoring", "m": ["—", "✓"]}
  ],
  "footer": "Readiness path is /firewall/healthz · the authenticated heartbeat feeds the dashboard"
}
```

## Notes

Both health endpoints are unauthenticated by design; only the rich heartbeat JSON
needs a Bearer token or basic auth. See ADR-017.
