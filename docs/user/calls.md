# Making and Receiving Calls

## Call Types

| Type | Description |
|------|-------------|
| **Incoming** | A call from an external number to your DID/extension. |
| **Outgoing** | A call you initiate to an external number. |
| **Internal** | A call between two PBX users (extension-to-extension). |

## Making Calls

### From the Phone Widget

1. Open the phone widget (phone icon in navbar)
2. Dial a number on the keypad or search for a contact
3. Click **Call**

### Click-to-Call

Click any phone number field on a partner form, lead, or other record to dial it directly.

### Extension Dialing

Dial another user's extension number to make an internal call.

## In-Call Controls

| Control | Description |
|---------|-------------|
| **Mute/Unmute** | Toggle your microphone. |
| **Keypad** | Open DTMF keypad to send tones during a call (e.g., for IVR menus). |
| **Transfer** | Transfer the active call to another number or extension. |
| **Hang Up** | End the call. |

## Call Transfer

During an active call:

1. Click **Transfer**
2. Enter the destination number or extension
3. Confirm the transfer

The call is handed off to the new destination.

## Call History

Navigate to **Connect > Calls** to view all calls.

Each call record shows:

| Field | Description |
|-------|-------------|
| **Direction** | Incoming, outgoing, or internal. |
| **Caller / Called** | Phone numbers or extension names. |
| **Status** | Completed, busy, failed, no-answer, canceled. |
| **Duration** | Call length in human-readable format (e.g., "2m 30s"). |
| **Partner** | Linked contact, if recognized. |
| **Recording** | Inline audio player, if the call was recorded. |
| **Summary** | AI-generated call summary, if transcription is enabled. |

### Partner Linking

If a call's number matches a contact in Odoo, the partner is automatically linked. If not, use the **Create Partner** button on the call record to create a new contact from the call.

### Redial

Click the **Redial** button on any call record to call that number again.

## Call Statuses

| Status | Meaning |
|--------|---------|
| **Completed** | Call was answered and ended normally. |
| **Busy** | Destination was busy. |
| **No Answer** | No one answered the call. |
| **Failed** | Call could not be connected (technical error). |
| **Canceled** | Caller hung up before the call was answered. |

## Voicemail

If voicemail is enabled for your account and you miss a call, the caller can leave a voice message. Voicemail recordings appear on the call record with an inline audio player.
