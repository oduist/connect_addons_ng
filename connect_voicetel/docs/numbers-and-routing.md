# Numbers & Call Routing

## Numbers

**Connect ▸ VoiceTel ▸ Numbers** lists the phone numbers of the VoiceML
account, imported by the account sync. Each number has a **Destination**:

| Destination | Behaviour |
|-------------|-----------|
| **User** | Rings the user's devices (see the user's ring timeout and voicemail). |
| **CallFlow** | Plays an IVR menu or a ring group. |
| **VoiceML** | Executes a VoiceML app. |

Saving a number pushes its voice URL (`/voicetel/webhook/number`), status
callback and SMS URL (`/voicetel/webhook/message`) to the account. **Ignored**
numbers are left alone by the sync.

Numbers are added and removed on the VoiceML account; run the account sync
to reflect changes. A number removed from the account is removed from Odoo
with a notification.

## Extensions

**Connect ▸ VoiceTel ▸ Extensions** maps short numbers to destinations
(**User**, **Call Flow** or **VoiceML** app). A destination has exactly one
extension; a number already in use is refused with the name of the extension
holding it.

Extensions are dialed from registered devices and the browser phone: a call
to `101` from a device on the tenant domain is routed by the SIP domain's app
to extension 101. Click-to-call to a short number works the same way.

## Outgoing caller IDs

**Connect ▸ VoiceTel ▸ Outgoing Caller IDs** holds:

- **DID Number** entries, synced from the account's own numbers (always
  usable);
- **CallerID** entries, external numbers that must be verified first.

Create a CallerID entry with the number in E.164 form and press
**Validate**. VoiceML calls the number and asks for the **validation code**
shown on the form; once entered, the status callback marks the entry
**validated**. Only a validated caller ID can be the **Default**.

The default caller ID is used for outbound calls of users without an
outgoing caller ID of their own, and for ring groups reached from a SIP
device.
