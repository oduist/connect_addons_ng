# Call Flows & VoiceML Apps

## Call flows

**Connect ▸ VoiceTel ▸ Call Flows** builds IVR menus and ring groups without
writing markup.

| Section | Fields |
|---------|--------|
| **General** | Name, language and voice for `<Say>`, **Record Calls**, **Gather Input** |
| **Gather Settings** | Input type (DTMF, speech, both), timeout, number of digits, speech hints |
| **Prompt Message** | Spoken before the menu; **Invalid Input Message** when no choice matches |
| **Choices** | Digits (or a spoken phrase) → extension |
| **Ring Users** | Users rung at once; each rings on every device registered with their SIP credential |
| **Voicemail** | Prompt recorded when nobody answers |

Assign an extension with the **Extension** button, or route a number to the
call flow.

Speech recognition and the `voice` names depend on the TTS/STT engines
configured on the VoiceML account.

## VoiceML apps

**Connect ▸ VoiceTel ▸ VoiceML Apps** holds custom voice applications. Each
app is mirrored as an Application on the VoiceML account whose voice URL
points at `/voicetel/webhook/voiceml/<id>`.

| Type | Content |
|------|---------|
| **VoiceML** | Raw markup, rendered as a Jinja2 template with the request parameters (`From`, `To`, `CallSid`, …). |
| **Python** | A script that builds the markup with the Twilio helper classes (`VoiceResponse`, `Dial`, `Gather`, …) and assigns it to `self.voiceml`. |
| **model.method** | Calls `model.method(request, params)` on an Odoo model. The **SIP Domain Calls** app is one: it routes every call placed from a registered device. |

VoiceML accepts the full Twilio voice verb set except `<Pay>`; `<Dial>`
supports `<Number>`, `<Sip>`, `<Client>`, `<Conference>`, `<Queue>` and
`<Application>`. Only `<Sip>` to the tenant domain reaches registered
devices.

!!! note "The SIP Domain Calls app is required"
    Every tenant SIP domain points at it. If it is deleted it is recreated
    the next time a domain is saved or synced.
