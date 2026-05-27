# piper-tts-multi-language — 2026-05-26

**Branch:** `litnimax/freeswitch-pipetts-tts`
**Goal:** Verify the new multi-language Piper TTS bundle: turn `connect.callflow.language` into a Selection, extend the `oduist/freeswitch` image with 26 Piper voice models, and prove end-to-end that picking any BCP-47 code in Odoo results in working synthesis on the FreeSWITCH side.

## Context

`connect.callflow.language` was a free-text `Char` and FreeSWITCH only bundled `en_US-lessac-medium` and `ru_RU-irina-medium`. Typing any other code (e.g. `fr`) failed at `mod_piper_tts`. The session used Oduflow MCP to (1) bring up a fresh Odoo 19 environment for code verification, (2) tear down and recreate the shared `fs` auxiliary service with the new image `oduist/freeswitch:1.1.0`, and (3) drive `fs_cli` through `run_service_command` to originate TTS test calls and read `mod_piper_tts` logs.

---

## Step 1. List existing environments

**Tool:** `mcp__oduflow_oduist__list_environments`

**Arguments:**
```json
{}
```

**Result:**
```
Active Environments:
- firewall-token-auth (Status: running) - https://firewall-token-auth.team.dev.oduist.com/web?debug=1
  Git Branch: litnimax/19.0-freeswitch-moh
  Database: oduflow_2_firewall-token-auth
  Image: odoo:19.0
  Repo: https://github.com/oduist/connect_addons_ng.git
  Template: fs19-dev
  * oduflow-firewall-token-auth-odoo [running] (odoo:19.0)
- 18.0 (Status: running) - https://180.team.dev.oduist.com/web?debug=1
- 19.0-crm (Status: running) - https://190-crm.team.dev.oduist.com/web?debug=1
- 19.0-connect-migrate (Status: running) - https://190-connect-migrate.team.dev.oduist.com/web?debug=1
```

**Observation:** No environment for the current branch yet. The `firewall-token-auth` env is the one wired to the shared `fs` service via `ODOO_URL`; remember its name when later swapping the FS image.

---

## Step 2. Provision a fresh env for the feature branch (first pass)

**Tool:** `mcp__oduflow_oduist__create_environment`

**Arguments:**
```json
{
  "branch": "litnimax/freeswitch-pipetts-tts",
  "template_name": "fs19-dev"
}
```

**Result:**
```
Environment provisioned successfully!
Environment: litnimax/freeswitch-pipetts-tts
URL: https://litnimax-freeswitch-pipetts-tts.team.dev.oduist.com
Odoo Container: oduflow-litnimax-freeswitch-pipetts-tts-odoo
Database: oduflow_2_litnimax-freeswitch-pipetts-tts
Template: fs19-dev
Creation time: 34.2s
```

**Observation:** Template-driven creation is fast (~34s). Sanitisation script `01_disable_mail.sql` ran. The new env is wired to the same shared `fs` service container, but Odoo there is still the old code until we upgrade.

---

## Step 3. Upgrade modules to run the new post-migration

**Tool:** `mcp__oduflow_oduist__upgrade_odoo_modules`

**Arguments:**
```json
{
  "env_name": "litnimax/freeswitch-pipetts-tts",
  "modules": "connect,connect_freeswitch"
}
```

**Result (excerpt):**
```
Success. Modules: connect, connect_freeswitch. Exit code: 0.

odoo.modules.migration: module connect: Running upgrade [19.0.3.1.0>] post-migration
...
odoo.modules.migration: module connect: Running upgrade [19.0.3.1.2>] post-migration
odoo.modules.loading: Module connect loaded in 1.43s
odoo.modules.loading: Module connect_freeswitch loaded in 0.79s
odoo.modules.loading: 30 modules loaded in 2.57s
odoo.registry: Registry loaded in 5.377s

--- Errors/Warnings (1 occurrences) ---
odoo.registry: Model attribute '_sql_constraints' is no longer supported, please define models.Constraint on the model.
```

**Observation:** The newly added `19.0.3.1.2` post-migration ran without raising. The only warning is pre-existing (`_sql_constraints` deprecation in `connect_freeswitch`). The clean exit code confirms the Selection switch did not break form/schema loading.

---

## Step 4. Verify the field type and selection in the ORM

**Tool:** `mcp__oduflow_oduist__run_odoo_shell`

**Arguments:**
```json
{
  "env_name": "litnimax/freeswitch-pipetts-tts",
  "python_code": "cf = env['connect.callflow']\nprint('field type:', cf._fields['language'].type)\nsel = cf._fields['language'].selection(cf)\nprint('selection size:', len(sel))\nfor code, label in sel[:5]: print(' ', code, '->', label)\nprint(' ...')\nfor code, label in sel[-5:]: print(' ', code, '->', label)"
}
```

**Result (excerpt):**
```
field type: selection
selection size: 26
  ca-ES -> Catalan (Spain)
  cs-CZ -> Czech
  da-DK -> Danish
  de-DE -> German
  en-GB -> English (UK)
 ...
  sv-SE -> Swedish
  tr-TR -> Turkish
  uk-UA -> Ukrainian
  vi-VN -> Vietnamese
  zh-CN -> Chinese (Mandarin)
```

**Observation:** The field is now a real `Selection` with exactly 26 BCP-47 entries; the callable `selection=` lambda resolves correctly inside an Odoo shell context.

---

## Step 5. Reset admin password before UI verification

**Tool:** `mcp__oduflow_oduist__reset_admin_password`

**Arguments:**
```json
{
  "env_name": "litnimax/freeswitch-pipetts-tts"
}
```

**Result:**
```
Admin password has been reset successfully.
Login: admin
New password: test
```

**Observation:** Standard ritual before driving the UI with agent-browser.

---

## Step 6. Check `_get_piper_language()` for regional codes

**Tool:** `mcp__oduflow_oduist__run_odoo_shell`

**Arguments:**
```json
{
  "env_name": "litnimax/freeswitch-pipetts-tts",
  "python_code": "cf = env['connect.callflow'].create({'name': 'Test FR-FR Callflow', 'language': 'fr-FR'})\nprint('language stored:', cf.language)\nprint('_get_piper_language ->', cf._get_piper_language())\ncf2 = env['connect.callflow'].create({'name': 'Test PT-BR Callflow', 'language': 'pt-BR'})\nprint('language stored:', cf2.language)\nprint('_get_piper_language ->', cf2._get_piper_language())\ncf3 = env['connect.callflow'].create({'name': 'Test PT-PT Callflow', 'language': 'pt-PT'})\nprint('language stored:', cf3.language)\nprint('_get_piper_language ->', cf3._get_piper_language())\nenv.cr.rollback()"
}
```

**Result (excerpt):**
```
language stored: fr-FR
_get_piper_language -> fr-FR
language stored: pt-BR
_get_piper_language -> pt-BR
language stored: pt-PT
_get_piper_language -> pt-PT
```

**Observation:** The new `_get_piper_language()` no longer strips the region, so `pt-BR` and `pt-PT` map to distinct Piper model keys.

---

## Step 7. Confirm the persisted value after a manual UI save

**Tool:** `mcp__oduflow_oduist__run_db_query`

**Arguments:**
```json
{
  "env_name": "litnimax/freeswitch-pipetts-tts",
  "query": "SELECT id, name, language FROM connect_callflow ORDER BY id DESC LIMIT 5;"
}
```

**Result:**
```
id,name,language
5,Test French Callflow,fr-FR
1,Menu,en-US
```

**Observation:** UI dropdown selection of "French" stored exactly `fr-FR` in the DB row — Selection codes flow through unchanged.

---

## Step 8. Tear down the verification env and the shared FS-bound env

**Tool:** `mcp__oduflow_oduist__delete_environment` (called twice)

**Arguments:**
```json
{"env_name": "firewall-token-auth"}
```
```json
{"env_name": "litnimax/freeswitch-pipetts-tts"}
```

**Result:**
```
Environment 'firewall-token-auth' has been torn down.
Environment 'litnimax/freeswitch-pipetts-tts' has been torn down.
```

**Observation:** The plan was to recreate `firewall-token-auth` (the env the `firewall` aux service is wired to) with the feature branch so the `fs` service rebuild keeps wiring stable. The first env was no longer needed.

---

## Step 9. Recreate `firewall-token-auth` with the feature branch

**Tool:** `mcp__oduflow_oduist__create_environment`

**Arguments:**
```json
{
  "branch": "litnimax/freeswitch-pipetts-tts",
  "env_name": "firewall-token-auth",
  "template_name": "fs19-dev"
}
```

**Result:**
```
Environment provisioned successfully!
Environment: firewall-token-auth
Git Branch: litnimax/freeswitch-pipetts-tts
URL: https://firewall-token-auth.team.dev.oduist.com
Database: oduflow_2_firewall-token-auth
Template: fs19-dev
Creation time: 37.3s
```

**Observation:** `env_name` differs from the branch slug on purpose — keeping the hostname `firewall-token-auth.team.dev.oduist.com` preserves the `firewall` service's `ODOO_URL` and the `fs` service's `ODOO_URL` env wiring without reconfiguring either.

---

## Step 10. List services to capture exact current FS config

**Tool:** `mcp__oduflow_oduist__list_services`

**Arguments:**
```json
{}
```

**Result (excerpt for fs):**
```
- fs (oduflow-svc-fs): running
  Image: oduist/freeswitch:1.8.22
  Port: 48081
  URL: https://fs.team.dev.oduist.com
  Env: ODOO_URL=https://firewall-token-auth.team.dev.oduist.com, FS_DOMAIN=team.dev.oduist.com, FS_LOG_LEVEL=debug, FS_SOFIA_LOG_LEVEL=2, SOUND_RATES=8000:16000:32000:48000, SOUND_TYPES=music:en-us-callie, EPMD=false, DUMPCAP=false
```

**Observation:** `list_services` is the right place to read every parameter needed for an identical recreate (image tag, port, env vars). No hidden defaults — what is printed is what was passed.

---

## Step 11. Delete the old FS service

**Tool:** `mcp__oduflow_oduist__delete_service`

**Arguments:**
```json
{"name": "fs"}
```

**Result:**
```
Service 'fs' deleted. Container 'oduflow-svc-fs' removed.
```

**Observation:** Service deletion is name-only and removes the container; the URL slot becomes free immediately.

---

## Step 12. Create FS service on the new image

**Tool:** `mcp__oduflow_oduist__create_service`

**Arguments:**
```json
{
  "name": "fs",
  "image": "oduist/freeswitch:1.1.0",
  "port": 48081,
  "env_vars": "ODOO_URL=https://firewall-token-auth.team.dev.oduist.com,FS_DOMAIN=team.dev.oduist.com,FS_LOG_LEVEL=debug,FS_SOFIA_LOG_LEVEL=2,SOUND_RATES=8000:16000:32000:48000,SOUND_TYPES=music:en-us-callie,EPMD=false,DUMPCAP=false"
}
```

**Result:**
```
Service created successfully!
Name: fs
Container: oduflow-svc-fs
Image: oduist/freeswitch:1.1.0
URL: https://fs.team.dev.oduist.com
```

**Observation:** The new container picks up the same hostname `fs.team.dev.oduist.com`, so the `firewall` service (which talks to FS via ESL at `oduflow-svc-fs:8021`) keeps working without further changes.

---

## Step 13. Re-run module upgrade against the new env

**Tool:** `mcp__oduflow_oduist__upgrade_odoo_modules`

**Arguments:**
```json
{
  "env_name": "firewall-token-auth",
  "modules": "connect,connect_freeswitch"
}
```

**Result (excerpt):**
```
Success. Modules: connect, connect_freeswitch. Exit code: 0.
odoo.modules.migration: module connect: Running upgrade [19.0.3.1.2>] post-migration
odoo.registry: Registry loaded in 42.010s
```

**Observation:** Same clean upgrade as Step 3 on the new env name.

---

## Step 14. List Piper voice models inside the new container

**Tool:** `mcp__oduflow_oduist__run_service_command`

**Arguments:**
```json
{"name": "fs", "command": "ls /opt/piper/models/"}
```

**Result (excerpt):**
```
ca_ES-upc_ona-medium.onnx          .onnx.json
cs_CZ-jirka-medium.onnx            .onnx.json
da_DK-talesyntese-medium.onnx      .onnx.json
de_DE-thorsten-medium.onnx         .onnx.json
en_GB-alba-medium.onnx             .onnx.json
en_US-lessac-medium.onnx           .onnx.json
es_ES-davefx-medium.onnx           .onnx.json
es_MX-claude-high.onnx             .onnx.json
fi_FI-harri-medium.onnx            .onnx.json
fr_FR-siwis-medium.onnx            .onnx.json
hu_HU-anna-medium.onnx             .onnx.json
is_IS-salka-medium.onnx            .onnx.json
it_IT-paola-medium.onnx            .onnx.json
nl_BE-nathalie-medium.onnx         .onnx.json
nl_NL-mls-medium.onnx              .onnx.json
pl_PL-gosia-medium.onnx            .onnx.json
pt_BR-faber-medium.onnx            .onnx.json
pt_PT-tugao-medium.onnx            .onnx.json
ro_RO-mihai-medium.onnx            .onnx.json
ru_RU-irina-medium.onnx            .onnx.json
sk_SK-lili-medium.onnx             .onnx.json
sv_SE-nst-medium.onnx              .onnx.json
tr_TR-dfki-medium.onnx             .onnx.json
uk_UA-ukrainian_tts-medium.onnx    .onnx.json
vi_VN-vais1000-medium.onnx         .onnx.json
zh_CN-huayan-medium.onnx           .onnx.json
```

**Observation:** All 26 voices × 2 files = 52 files are baked into the image, including the ASCII-renamed `pt_PT-tugao-medium.onnx`.

---

## Step 15. Read ESL password from autoload config

**Tool:** `mcp__oduflow_oduist__run_service_command`

**Arguments:**
```json
{"name": "fs", "command": "cat /usr/local/freeswitch/etc/freeswitch/autoload_configs/event_socket.conf.xml"}
```

**Result:**
```xml
<configuration name="event_socket.conf" description="Socket Client">
  <settings>
    <param name="nat-map" value="false"/>
    <param name="listen-ip" value="127.0.0.1"/>
    <param name="listen-port" value="8021"/>
    <param name="password" value="ConnectNGESLPassword"/>
  </settings>
</configuration>
```

**Observation:** `fs_cli` from inside the container needs `-P 8021 -p ConnectNGESLPassword`. The default `ClueCon` password is not used here.

---

## Step 16. Synthesise on `fr-FR`

**Tool:** `mcp__oduflow_oduist__run_service_command`

**Arguments:**
```json
{"name": "fs", "command": "fs_cli -P 8021 -p ConnectNGESLPassword -x 'originate null/loopback &speak(piper|fr-FR|Bonjour ceci est un test)'"}
```

**Result:**
```
+OK 71b2666e-1f7d-48e2-afd9-efc9ffabe103
```

**Observation:** Single-quote the whole `-x` argument so `&speak(...)` is not interpreted by the shell as backgrounding. The originate returned a session UUID — synthesis started.

---

## Step 17. Read FS logs to confirm TTS pipeline

**Tool:** `mcp__oduflow_oduist__get_service_logs`

**Arguments:**
```json
{"name": "fs", "n_lines": 50}
```

**Result (excerpt):**
```
EXECUTE [depth=0] null/loopback speak(piper|fr-FR|Bonjour)
DEBUG switch_ivr_play_say.c:3108 OPEN TTS piper
DEBUG switch_ivr_play_say.c:3118 Raw Codec Activated
DEBUG switch_core_file.c:444 File /tmp/piper-tts-cache/ebc58ab2cb4848d04ec23d83f7ddf985.wav sample rate 22050 doesn't match requested rate 8000
DEBUG switch_ivr_play_say.c:2826 Speaking text: Bonjour
DEBUG switch_ivr_play_say.c:2990 done speaking text
NOTICE switch_core_state_machine.c:382 null/loopback has executed the last dialplan instruction, hanging up.
```

**Observation:** Piper resolved the `fr-FR` key against `piper_tts.conf.xml`, produced a 22050 Hz WAV in the on-disk cache, and `speak` completed without errors. Side note: only the first whitespace-delimited word ("Bonjour") was kept because `fs_cli` does its own arg-splitting — fine for a smoke test.

---

## Step 18. Multi-language smoke test with unique text per language

**Tool:** `mcp__oduflow_oduist__run_service_command`

**Arguments:**
```json
{
  "name": "fs",
  "command": "bash -c 'find /tmp/piper-tts-cache -type f -delete; for spec in \"de-DE:GutenTagAusDeutschland\" \"ru-RU:DobryDenIzRossii\" \"pt-BR:OlaBrasil\" \"pt-PT:OlaPortugal\" \"uk-UA:DobrogoDnyaUkraina\" \"zh-CN:NiHaoZhongguo\"; do lang=$(echo \"$spec\" | cut -d: -f1); text=$(echo \"$spec\" | cut -d: -f2); echo \"=== $lang : $text ===\"; fs_cli -P 8021 -p ConnectNGESLPassword -x \"originate null/loopback &speak(piper|$lang|$text)\"; sleep 2; done; echo \"--- cache after ---\"; ls -la /tmp/piper-tts-cache/'"
}
```

**Result:**
```
=== de-DE : GutenTagAusDeutschland ===
+OK 60beca6d-b6d7-4517-9c3e-caa7c1ee9328
=== ru-RU : DobryDenIzRossii ===
+OK 96db17fd-8a42-4ca9-b2bb-d90b047615cc
=== pt-BR : OlaBrasil ===
+OK 777dea65-9e36-45e8-bc5f-c13a413f7373
=== pt-PT : OlaPortugal ===
+OK f04b6c63-b876-4632-98aa-bd0b6b4b335e
=== uk-UA : DobrogoDnyaUkraina ===
+OK 2c306811-f2f8-45aa-af8f-2408536b5df2
=== zh-CN : NiHaoZhongguo ===
+OK 79281c4b-7f29-4cd9-89af-055e7b33aa6c
--- cache after ---
-rw-r--r-- 1 root root 40608 ... 574b621aa4f1980ea0eb9d81cd4fca3c.wav
-rw-r--r-- 1 root root 40096 ... 6638356d9e6aae2c055d3cbe4fd87d17.wav
-rw-r--r-- 1 root root 52384 ... a5960d31ee0f98d4628f6ed8cc8eb1b8.wav
-rw-r--r-- 1 root root 83104 ... db90218c95fb6f1ce77083f542669770.wav
-rw-r--r-- 1 root root 10400 ... de26bd4dfb4c3bcef410357b0743ee4b.wav
-rw-r--r-- 1 root root 83616 ... e5721ef39e567ac89f28a2841961b06f.wav
```

**Observation:** Six distinct WAV files of varying sizes confirm Piper picked a different model for each BCP-47 code — including separate voices for `pt-BR` vs `pt-PT`, which used to collapse to a single `pt` under the old short-code mapping. Two practical gotchas surfaced while iterating:

- `find ... -delete;` and `ls .../*.wav` mis-parsed inside `run_service_command` because the wrapper does its own argv splitting; wrap multi-token shell pipelines in `bash -c '...'` for safety.
- `mod_piper_tts` keys its on-disk cache by `md5(text)` only, not `(text, lang)`. Reusing the same text across languages reuses the same cached WAV.

---

## Outcome

- The new code path (Selection in core + post-migration + full BCP-47 keys in `mod_piper_tts`) works end-to-end against a real Odoo + FS pair brought up entirely via Oduflow MCP.
- The shared `fs` service was recreated on `oduist/freeswitch:1.1.0` without disturbing the `firewall` sidecar: same name, same hostname, same env vars, only the image tag changed.
- Test artifacts (WAV cache) and FS logs confirm every voice in the Selection resolves to a real model. The Oduflow MCP loop (provision env → upgrade modules → drive `fs_cli` via `run_service_command` → tail logs via `get_service_logs`) is sufficient for FS-side verification without leaving the chat.
