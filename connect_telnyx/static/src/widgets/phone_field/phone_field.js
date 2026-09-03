/** @odoo-module **/
"use strict"

// Odoo 15 variant (ADR-062): the OWL field component API is 16+; on 15 the
// phone widget is the legacy basic_fields.FieldPhone. Rebind its readonly
// link so a click originates the call through Odoo instead of tel: — the
// core connect.settings.originate_call dispatches by the user's
// click-to-call provider. The inline WhatsApp composer button of the 19.0
// branch has no clean legacy counterpart and is not ported.
import basic_fields from "web.basic_fields"

basic_fields.FieldPhone.include({
    events: Object.assign({}, basic_fields.FieldPhone.prototype.events, {
        'click': '_onClickConnectCall',
    }),

    _onClickConnectCall(ev) {
        if (this.mode !== 'readonly' || !this.value) {
            return
        }
        ev.preventDefault()
        this._rpc({
            model: 'connect.settings',
            method: 'originate_call',
            args: [this.value, this.model, this.res_id],
        })
    },
})
