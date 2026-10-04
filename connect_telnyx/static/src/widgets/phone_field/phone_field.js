/** @odoo-module **/
"use strict"

import {patch} from "@web/core/utils/patch"
import {PhoneField} from "@web/views/fields/phone/phone_field"
import {useService} from "@web/core/utils/hooks"

patch(PhoneField.prototype, {

    get actionButtons() {
        // Odoo 20: web.FormPhoneField template anchors are gone; the field
        // renders an action-button list instead. Route the standard Call
        // button through the Connect click-to-call dispatcher.
        const buttons = super.actionButtons
        if (buttons.length) {
            buttons[0] = {...buttons[0], href: undefined, onSelected: (ev) => this._onClickCallButton(ev)}
        }
        if (this.value) {
            buttons.push({icon: "phone", name: "WhatsApp Message", onSelected: (ev) => this._onClickTelnyxWhatsappMessageButton(ev)})
        }
        return buttons
    },


    setup() {
        super.setup()
        this.action = useService("action")
    },

    _onClickCallButton(e) {
        e.preventDefault()
        const {resModel, resId} = this.props.record.model.config
        const args = [this.props.record.data[this.props.name], resModel, resId]
        // The core connect.settings.originate_call dispatches by the
        // user's click-to-call provider.
        this.env.model.orm.call("connect.settings", "originate_call", args, {})
    },

    async _onClickTelnyxWhatsappMessageButton(e) {
        e.preventDefault()
        await this.props.record.save()
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                target: "new",
                name: "Send WhatsApp Message",
                res_model: "connect.telnyx.whatsapp_composer",
                views: [[false, "form"]],
                context: {
                    active_model: this.props.record.resModel,
                    active_id: this.props.record.resId,
                    default_phone: this.props.record.data[this.props.name],
                },
            },
            {
                onClose: () => {
                    this.props.record.load()
                    this.props.record.model.notify()
                },
            }
        )
    },
})
