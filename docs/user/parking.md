# Call Parking

Parking is a way to put an active call on hold at a shared slot that any
other operator can pick up from their own phone. It's different from a
private hold because any extension in the office can retrieve the
parked call.

## Parking a call

You can park a call from three places:

### From the Verto phone widget

1. While connected, open the phone widget and switch to the **Parking**
   tab.
2. Click any **empty** slot (green). The far end is moved to that slot
   and the slot card starts showing the caller's number / name.
3. Announce the slot over a loudspeaker or messenger — "Call for John on
   701".

### From the `connect.call` form

1. Open the active call record in Odoo.
2. Click **Park** in the header. The call goes into the first free
   slot; the slot number is shown next to the call status.

### From a hardware SIP phone

If you have a DSS (speed-dial) button programmed for a slot extension
(e.g. `701`), press it while the call is active to park the far side on
that slot. The button's BLF lamp turns red / busy to indicate the slot
is occupied.

## Retrieving a parked call

Parked calls can be retrieved from the same three places:

- **Verto widget → Parking tab:** click the occupied slot (yellow) — your
  phone rings and, when you answer, you're connected to the parked
  party.
- **Hardware SIP phone:** press the DSS button for the occupied slot.
  Your phone is called back and bridged to the parked party.
- **Admin form (debug):** open the slot record under
  *Connect → FreeSWITCH → Parking Slots* and press **Unpark**.

## Tips

- Each slot's BLF lamp updates in near real time for every subscribing
  phone in the office, so anyone can tell at a glance which slots are
  busy.
- If no one retrieves a parked call, `mod_valet_parking`'s default
  behaviour is to keep the caller on hold indefinitely. Operators
  should treat parking as a short-lived hand-off, not as a parking lot
  for abandoned calls.
- The number of slots is set by the admin. The default is six (701–706),
  sized to fit the Parking tab without scrolling.
