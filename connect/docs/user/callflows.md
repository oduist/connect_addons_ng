# Call Flows (IVR)

Call flows define how incoming calls are handled — either as an IVR menu (interactive voice response) or a ring group.

!!! note
    Call flows are configured by administrators. This section describes what callers experience and how the features work.

## IVR Menus

An IVR plays a voice prompt and waits for the caller to press a digit or speak a choice.

**Example:**

> "Thank you for calling. Press 1 for Sales, Press 2 for Support, or Press 0 to speak with an operator."

The caller presses a digit, and the call is routed to the corresponding extension (a user, another callflow, etc.).

### How It Works

1. The caller dials your phone number
2. A voice prompt plays the menu options
3. The caller presses a digit (DTMF) or speaks a keyword
4. The call is routed to the matching extension
5. If the input is invalid, an error message plays and the prompt repeats

### Input Types

| Type | Description |
|------|-------------|
| **DTMF** | Caller presses digits on their phone keypad. |
| **Speech** | Caller speaks a keyword (e.g., "sales", "support"). |
| **Both** | Accept either DTMF or speech input. |

## Ring Groups

A ring group rings multiple users simultaneously. The first user to answer gets the call.

The **Prompt Message** remains available when **Gather Input** is disabled. In
that mode it is played once as a greeting before the users are rung; no keypad
or speech input is collected. Enabling Gather Input turns the same prompt into
the introduction to the IVR choices. When enabled, **Gather Settings** and
**Invalid Input Message** appear together in one row above the prompt.

**Example:**

> Three sales representatives are in a ring group. When a customer calls the sales number, all three phones ring at once. The first rep to pick up handles the call.

### Features

- **Simultaneous ring** — All users in the group are called at the same time
- **Timeout** — If no one answers within the configured timeout, the call can go to voicemail or another destination
- **Recording** — Ring group calls can be recorded

## Multi-Level IVR

Call flows can chain together. An IVR choice can route to another call flow, creating multi-level menus:

> "Press 1 for Sales" → "Press 1 for New Customers, Press 2 for Existing Customers"

## Voicemail

Call flows can have voicemail enabled. When enabled with a voicemail prompt, the caller can leave a callflow-level voicemail after the callflow cannot connect them:

- **Standalone callflow** — if the callflow has no gather choices, ring users, or queue fallback, the voicemail prompt is played and the caller is recorded.
- **Ring group** — if no ring user answers, the callflow can play its voicemail prompt and record the caller.
- **IVR menu** — if the caller does not make a choice before the timeout, the callflow can record voicemail after any configured ring-user or queue fallback.

Invalid IVR input still follows the invalid-input message and retry flow. It does not immediately trigger voicemail.

Callflow voicemail takes precedence inside callflows. Direct calls to a user keep that user's voicemail behavior. In FreeSWITCH, FS Queue voicemail is configured separately on the queue timeout settings.

The voicemail greeting can be customized per call flow. The voicemail prompt must be set for callflow voicemail to trigger.

## FS Queues (FreeSWITCH-only)

When the `connect_freeswitch` module is installed, call flows can route calls into an **FS Queue** — a hold area where the caller hears Music-on-Hold while agents are being rung. The first agent to answer takes the call.

A queue can be used in several ways:

- **Directly as an extension destination** — give the queue an extension number, then dialing it enters the queue. *(The extension is optional and only needed for direct dialing.)*
- **As an IVR choice** — any IVR menu option can point to a queue.
- **As the "no choice" default of an IVR** — if the caller doesn't press anything, the call is transferred into the queue.
- **As a fallback for a ring group** — if nobody in the ring group answers, the call is moved into the queue before voicemail.

Used as an IVR or ring-group destination, a queue needs **no extension of its own** — it is reached automatically.

### What the caller experiences

1. A brief "please hold" (the queue answers and starts Music-on-Hold).
2. Music-on-Hold plays while agent phones ring in the background.
3. As soon as any agent answers, the call is connected to them.
4. If no agent answers within the configured timeout, the caller is hung up, sent to voicemail, or transferred to a fallback extension, depending on how the queue is set up.

### Admin configuration summary

FS Queues are configured under **Connect → FreeSWITCH → FIFO Queues**. Each queue defines:

- member users and/or endpoint agents,
- max wait time,
- Music-on-Hold source,
- whether to announce the caller's position,
- what to do on timeout (hangup, voicemail, transfer).

Changes to a queue's agents or wait time take effect on the **next call automatically** — no restart or manual step.
