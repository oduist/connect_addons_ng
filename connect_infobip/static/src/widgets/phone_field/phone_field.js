/** @odoo-module **/
"use strict"

import {patch} from "@web/core/utils/patch"
import {PhoneField} from "@web/views/fields/phone/phone_field"
import {useService} from "@web/core/utils/hooks"

patch(PhoneField.prototype, {

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

    async _onClickInfobipWhatsappMessageButton(e) {
        e.preventDefault()
        await this.props.record.save()
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                target: "new",
                name: "Send WhatsApp Message",
                res_model: "connect.infobip.whatsapp_composer",
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
