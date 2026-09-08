---
id: K12
title: AWS key rotation for S3 recording storage
status: draft
language: en
platforms: [linkedin]
publish_date:
postiz_post_id:
published_url:
sources: [connect_s3/docs/setup.md]
---

## Post

Rotating an AWS access key is one click in AWS. It's the four steps *after* it that decide whether you still have call recordings tomorrow. 🔑

When Twilio writes recordings straight into your own S3 bucket, the key is stored in three places at once. Twilio also cannot update a stored credential's key — so rotation means replace, not edit:

1️⃣ Create a new access key for the IAM user in AWS
2️⃣ Enter it in Odoo (Connect ▸ Configuration ▸ S3 Storage)
3️⃣ Press **RECREATE TWILIO CREDENTIAL** — Odoo deletes the old credential and creates a new one, so AWS keys never get pasted into the Twilio Console
4️⃣ Re-select the new credential in the Twilio Console (Voice ▸ Recordings ▸ Settings) — **until you do, Twilio keeps pointing at the old SID and uploads fail**

Step 4 is the one everybody skips. Put it in the runbook, not in your memory.

Bonus: the IAM policy is scoped to your bucket prefix and contains no `iam:*` permissions at all.

How often do you actually rotate cloud storage keys? Honestly. 👇

#Odoo #AWS #S3 #Twilio #SecOps

## Card

```json
{
  "template": "diagram",
  "kicker": "Oduist Connect · S3 Storage",
  "headline": "Rotate the key",
  "headline_grad": "in three places.",
  "lede": "Twilio cannot update a stored credential's key — *rotation is replace, then re-select.* Skip the last step and uploads fail silently.",
  "nodes": [
    {"t": "AWS IAM", "s": "new access key, prefix-scoped policy", "c": "memory"},
    {"t": "Odoo", "s": "RECREATE TWILIO CREDENTIAL", "c": "app"},
    {"t": "Twilio Console", "s": "re-select the new credential SID", "c": "provider"}
  ],
  "link_label": "step",
  "footer": "Recordings land in your bucket · Odoo only configures and reads back"
}
```

## Notes

Twilio's recording-storage setting has no public API, so step 4 is manual by
design — not an oversight in the module.
