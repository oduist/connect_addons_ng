# Messaging (SMS)

## Sending

Messages are sent through the core **Send SMS** composer. When a user's
**Messaging provider** is VoiceTel (or VoiceTel is the only messaging module
installed), the composer offers the account's numbers as **Outgoing
CallerID** and sends through the VoiceML Messages API.

The sent message is logged under **Connect ▸ VoiceTel ▸ Messages** and in
the chatter of the record it was sent from. Delivery receipts
(`sent`, `delivered`, `undelivered`, `failed`) arrive on the message webhook
and update the message status; a failed message can be retried.

## Receiving

Every synced number has its SMS webhook set to `/voicetel/webhook/message`.
An inbound message:

1. is stored as an incoming message, linked to the partner matching the
   sender number;
2. is threaded under the last message exchanged with that number, when the
   record it belongs to still exists;
3. otherwise creates a record according to **Message Configuration** (per
   number: destination model and default values; the partner by default);
4. is posted to the chatter of the target record.

MMS attachments are kept as the message's media URL.

## Configuration

**Connect ▸ VoiceTel ▸ Messages ▸ Message Configuration** (administrators)
defines, per number, which model receives new conversations and the default
values of the created record.

## Not supported

WhatsApp senders and content templates are a Twilio feature and are not part
of the VoiceTel module.
