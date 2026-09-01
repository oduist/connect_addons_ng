# Making and Receiving Calls

## Direction

| Direction | Description |
|-----------|-------------|
| **Incoming** | A call from an external number to your DID/extension. |
| **Outgoing** | A call you initiate to an external number. |
| **Internal** | A call between two PBX users (extension-to-extension). |

## Call Type

Separately from the direction, each call records the medium it travelled over:

| Call type | Description |
|-----------|-------------|
| **Phone** | An ordinary voice call over the telephone network or SIP. |
| **WhatsApp** | A WhatsApp voice call, in either direction. |

The call type is shown on the call form and is available as an optional
**Call Type** column in the call list — see [Call History](#call-history).

## Making Calls

### From the Phone Widget

1. Open the phone widget (phone icon in navbar)
2. Dial a number on the keypad or search for a contact
3. Click **Call**

### Click-to-Call

Click any phone number field on a partner form, lead, call, channel, or other
record to dial it directly. Caller and called numbers on individual Connect
forms use the same standard phone control. Connect list rows keep phone numbers
as plain text.

### WhatsApp Calls

Where WhatsApp calling is configured, a number also offers a **WhatsApp Call**
action next to the ordinary **Call**. It rings your own web phone first and
then places the WhatsApp leg to the destination, so the call appears in the
history with call type **WhatsApp**.

!!! note "Business-initiated WhatsApp calling is not available everywhere"
    WhatsApp restricts business-initiated calls by destination country. Where
    it is not permitted the call fails immediately and the call record's
    **Error** tab carries the provider's reason, for example *"WhatsApp Voice:
    Business-initiated calling is not available in the country"*. Nothing in
    Connect can lift that restriction. Calls **received** over WhatsApp are
    unaffected.

### Extension Dialing

Dial another user's extension number to make an internal call.

### Failed Calls

When an outgoing call cannot be connected, the phone widget shows a
notification with the reason (busy, rejected, number not found, ...).
On Telnyx, if the call was blocked because the account balance is
exhausted, a persistent red notification says so explicitly —
administrators also see the current balance and should top up the
Telnyx account to restore calling.

## In-Call Controls

| Control | Description |
|---------|-------------|
| **Mute/Unmute** | Toggle your microphone. |
| **Keypad** | Open DTMF keypad to send tones during a call (e.g., for IVR menus). |
| **Transfer** | Transfer the active call to another number or extension. |
| **Recording** | A purple badge with a white dot and **REC** starts recording; a purple stop icon means recording is active and stops it. |
| **Hang Up** | End the call. |

## Call Transfer

During an active call:

1. Click **Transfer**
2. Enter the destination number or extension
3. Confirm the transfer

The destination uses the standard phone control. The call is handed off to the
new destination after confirmation.

## Call History

Navigate to **Connect > Calls > Calls** to view all calls.

Each call record shows:

| Field | Description |
|-------|-------------|
| **Direction** | Incoming, outgoing, or internal. |
| **Call Type** | Phone or WhatsApp. Hidden by default in the list — switch it on from the column picker at the right end of the header row; the choice is remembered. |
| **Caller / Called** | Phone numbers or extension names. On an outgoing click-to-call, **Called** is the number you dialed, not the extension the system rang to reach you. |
| **Status** | Completed, busy, failed, no-answer, canceled. |
| **Duration** | Call length in human-readable format (e.g., "2m 30s"). |
| **Partner** | Linked contact, if recognized. |
| **Recording** | Inline audio player, if the call was recorded. |
| **Transcript** | Full AI-generated transcript, retained even when the audio recording is deleted. |
| **Summary** | AI-generated call summary, if transcription is enabled. |

### Partner Linking

If a call's number matches a contact in Odoo, the partner is automatically linked. If not, use the **Create Partner** button on the call record to create a new contact from the call.

## Active Calls

Connect users have a **Toggle Calls** icon (a small server icon) in the top
navbar. Click it to open a panel listing the calls currently in progress —
caller, called, the users involved, the linked partner and the direction.
Click a row to open the call record, or the partner name to jump to the
contact. The panel hides itself again after a few seconds; when nothing is
ringing or talking it simply says *No active calls*.

## Call Statuses

| Status | Meaning |
|--------|---------|
| **Completed** | Call was answered and ended normally. |
| **Busy** | Destination was busy. |
| **No Answer** | No one answered the call. |
| **Failed** | Call could not be connected (technical error). |
| **Canceled** | Caller hung up before the call was answered. |

## Voicemail

If voicemail is enabled for your account and no configured phone answers, the
caller can leave a voice message. Voicemail does not start after an answered
phone call ends. Recordings appear on the call record with an inline audio
player.

## Availability Calendar

If your administrator configured working schedules for inbound numbers,
**Connect → Availability** shows when each schedule is open or closed as a
calendar: green *Available* windows, all-day *Closed* markers, plus the
underlying working-schedule, public-holiday and special-working-day layers.
Use the search filters to toggle the layers or focus on one schedule.
