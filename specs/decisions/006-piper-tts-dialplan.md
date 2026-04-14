# ADR-006: Use Piper TTS in generated dialplan

**Status:** Accepted
**Date:** 2026-03-18

## Context

ADR-004 added mod_piper_tts to the FreeSWITCH Docker image, providing local neural TTS with English and Russian voice models. However, the dialplan generation code in `connect_freeswitch` still used the generic `say:'text'` syntax for IVR prompts in `play_and_get_digits`. The `say:` prefix uses whatever TTS engine FreeSWITCH defaults to, which may not be piper.

## Decision

Use the explicit `speak:piper|{lang}|{text}` syntax in generated dialplan XML instead of `say:'{text}'`.

The callflow's `language` field (e.g., `en-US`) is mapped to piper's short language code (e.g., `en`) by taking the part before the hyphen. This matches the `<model language="en" .../>` entries in `piper_tts.conf.xml`.

## Example output

Before:
```
play_and_get_digits 1 1 3 5000 # say:'Welcome, press 1 for sales' say:'Invalid input' cf_digit_1 ^(1)$
```

After:
```
play_and_get_digits 1 1 3 5000 # speak:piper|en|Welcome, press 1 for sales speak:piper|en|Invalid input cf_digit_1 ^(1)$
```

## Consequences

- IVR prompts now use high-quality neural TTS voices
- Language must have a corresponding model in `piper_tts.conf.xml` or FreeSWITCH will error
- Currently shipped models: `en` (English) and `ru` (Russian)
