# AI Voice Agents

An AI voice agent answers a normal phone number or internal extension and holds
a spoken conversation in real time. Depending on its configuration, it can
answer questions, collect information, end the call, or transfer you to a
person.

## Calling An Agent

Every AI agent has its own extension number. Dial the extension from any phone
registered on the PBX, or call a public number that an administrator has routed
to the agent.

For Telnyx, the internal address is
`sip:<extension>@<company-subdomain>.sip.telnyx.com`. No external phone number
is required for that SIP/WebRTC call.

Speak normally after the greeting. You do not need to wait for a long reply to
finish: start speaking and the agent will stop its playback and listen to the
new turn.

## Transfers

If a human transfer is configured, ask to speak with a person. The agent will
first ask why you are calling and collect the relevant context. It then briefs
the employee privately and bridges the same call. During that private briefing,
the caller hears transfer progress or ringback. If the employee's SIP/WebRTC
phone is not registered or transfer is otherwise unavailable, the agent offers
to register the request rather than disconnecting you.

A personal receptionist transfers to its manager. A company receptionist may
replace an IVR and route to configured departments such as Sales, Quality, or
the Director.

## Caller Recognition

When exactly one Odoo contact has the caller's phone number, the agent may use
that contact's name but must ask the caller to confirm it. If several contacts
share the number, the agent does not guess a name.

## Conversation Language

An administrator can configure the agent to use the language of the single
contact matched by phone. The first greeting is then prepared in that Odoo
contact language, and the agent may follow the caller if they clearly switch
to another language. Unknown or ambiguous callers start in the agent's
fallback language.

The contact language is maintained on the Odoo contact. A multilingual agent
also needs automatic or multilingual speech recognition and a TTS voice that
can actually speak the required languages; changing only the prompt does not
make an English-only voice multilingual.

## Call History And Recordings

Calls to AI agents appear in **Connect -> Calls** like any other call. When
recording is enabled, the conversation is recorded and shows up under
**Recordings** on the call form.

For a Telnyx AI agent, the same recording contains the downloaded audio, the
Telnyx conversation transcript, and the Telnyx insight summary. Since the
transcript is already complete, Odoo does not send that audio to OpenAI for a
second transcription.

Dograh agents may also expose the full workflow-level transcript in the Dograh
dashboard. Ask your administrator for access.

## What The Agent Can Do

The agent's behavior, including greetings, questions, business logic and API
calls, is controlled by the agent configuration selected by your administrator.
