# Messages (SMS & WhatsApp)

## Viewing Messages

Navigate to **Twilio > Messages > Messages** to see all SMS and WhatsApp messages.

Each message shows:

| Field | Description |
|-------|-------------|
| **Direction** | Arrow icon indicating incoming or outgoing. |
| **From / To** | Phone numbers. |
| **Body** | Message text. |
| **Status** | Delivery status with icon. |
| **Partner** | Linked contact. |
| **Media** | Inline image/audio player for MMS content. |

## Sending SMS

### From the SMS Composer

1. Open a partner or contact record
2. Click **Send SMS** in the action menu
3. Select an **Outgoing Number** (your Connect caller IDs)
4. Enter the message text
5. Click **Send**

The message is sent via your configured telephony provider and tracked in Connect.

## Sending WhatsApp Messages (Twilio only)

### From a Partner Record

1. Open a partner form
2. Use the WhatsApp composer action
3. Select a **WhatsApp sender** number
4. Choose a **message template** (required for first contact or after 24-hour window)
5. Fill in template variables if needed
6. Click **Send**

!!! info "24-Hour Contact Window"
    WhatsApp requires you to use an approved message template for the first message or when contacting someone after 24 hours of inactivity. Within the 24-hour window after a customer's last message, you can send free-form text.

## Message Statuses

| Status | Meaning |
|--------|---------|
| **Draft** | Message created but not yet sent. |
| **Queued** | Message queued for delivery. |
| **Sending** | Message is being transmitted. |
| **Sent** | Message sent to the carrier. |
| **Delivered** | Message delivered to the recipient's device. |
| **Read** | Recipient read the message (WhatsApp only). |
| **Failed** | Message could not be sent. |
| **Undeliverable** | Carrier could not deliver the message. |

## Retrying Failed Messages

If a message fails, click the **Retry** button on the message record to attempt resending.

## Incoming Messages

Incoming SMS and WhatsApp messages are automatically:

1. Recorded in **Twilio > Messages > Messages**
2. Linked to the partner (if the sender's number matches a contact)
3. Optionally, a new partner can be auto-created (see Message Configuration in admin guide)

Geographic information (city, state, ZIP, country) may be available for incoming SMS messages.
