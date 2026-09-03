# Getting Started

## Your PBX Account

Your Connect administrator creates a PBX user account for you. Once set up, you'll see a **phone icon** in the Odoo top navigation bar — this is your phone widget.

## Phone Widget

The phone widget is a browser-based phone embedded in Odoo. Click the phone icon in the navbar to open it.

=== "Twilio"

    The phone widget uses the Twilio Voice SDK. It connects automatically when you open Odoo.

=== "FreeSWITCH"

    The phone widget uses Verto WebRTC. Look for the status badge:

    - **Green (Registered)** — Ready to make and receive calls
    - **Grey (Disconnected)** — Not connected to FreeSWITCH
    - **Red (Error)** — Connection problem

    The widget automatically reconnects if the connection drops.

    The FreeSWITCH widget follows your Odoo interface language — German,
    French, Italian and Russian translations ship with the module; other
    languages fall back to English.

=== "Telnyx"

    The phone widget uses the Telnyx WebRTC SDK and connects automatically
    when you open Odoo. If the browser suspends a background tab, the phone
    reconnects when you return without interrupting Odoo with an error dialog.

### Widget Tabs

| Tab | Description |
|-----|-------------|
| **Keypad** | Dial pad for entering phone numbers. |
| **Contacts** | Search and call Odoo contacts by name. |
| **Calls** | Recent call history with duration and timestamps. |
| **Favorites** | Quick-dial saved numbers. |

## Making Your First Call

1. Click the phone icon in the navbar
2. Enter a phone number on the keypad (or select a contact)
3. Click the **Call** button
4. Use the in-call controls:
    - **Mute** — Toggle your microphone
    - **Keypad** — Send DTMF tones during a call
    - **Transfer** — Transfer the call to another number
    - **Hang up** — End the call

## Receiving Calls

When someone calls you:

1. A notification appears with the caller's name and number (if recognized)
2. Click **Accept** to answer or **Decline** to reject
3. If you don't answer, the call goes to voicemail (if enabled)

## Click-to-Call

Click any phone number field in Odoo (on partner forms, leads, etc.) to instantly dial that number from the phone widget.

## Navigation

| Menu | What You'll Find |
|------|------------------|
| **Connect > Calls > Calls** | All your call history |
| **Connect > Twilio > Messages > Messages** | SMS and WhatsApp messages |
| **Connect > Calls > Recordings** | Call recordings with playback |

## Partner Integration

When you receive a call from a known contact, Connect automatically links the call to their partner record. You can see call and message counts as smart buttons on the partner form.

If a call comes from an unknown number, you can click **Create Partner** on the call record to create a new contact.
