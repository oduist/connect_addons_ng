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

Call flows can have voicemail enabled. If no one answers (ring group) or the caller doesn't make a valid choice (IVR), they can leave a voicemail message.

The voicemail greeting can be customized per call flow.
