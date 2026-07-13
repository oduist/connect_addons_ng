# AI Voice Agents

An AI voice agent answers a normal phone number or internal extension and holds
a spoken conversation in real time. Depending on its configuration, it can
answer questions, collect information, end the call, or transfer you to a
person.

## Calling An Agent

Every AI agent has its own extension number. Dial the extension from any phone
registered on the PBX, or call a public number that an administrator has routed
to the agent.

Speak normally after the greeting. You do not need to wait for a long reply to
finish: start speaking and the agent will stop its playback and listen to the
new turn.

## Transfers

If a human transfer is configured, ask to speak with a person. The agent will
transfer the same call to the configured extension. If transfer is unavailable,
the agent should say so rather than disconnecting you.

## Call History And Recordings

Calls to AI agents appear in **Connect -> Calls** like any other call. When
recording is enabled, the conversation is recorded and shows up under
**Recordings** on the call form, where the standard transcription and
summarization tools apply.

Dograh agents may also expose the full workflow-level transcript in the Dograh
dashboard. Ask your administrator for access.

## What The Agent Can Do

The agent's behavior, including greetings, questions, business logic and API
calls, is controlled by the agent configuration selected by your administrator.
