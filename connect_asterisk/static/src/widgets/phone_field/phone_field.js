/** @odoo-module **/
"use strict"

import {patch} from "@web/core/utils/patch"
import {PhoneField} from "@web/views/fields/phone/phone_field"
import {registry} from "@web/core/registry"

patch(PhoneField.prototype, {
    setup() {
        super.setup()
        this.mainPhone = registry.category("main_components").get('mainPhone', null)
    },

    _onClickCallButton(e) {
        e.preventDefault()
        const {resModel, resId} = this.props.record.model.config
        const phone = this.props.record.data[this.props.name]
        if (this.mainPhone) {
            // The JsSIP web phone is active: place the call from the
            // browser (SIP over WSS directly to Asterisk).
            this.mainPhone.props.bus.trigger('busPhoneMakeCall', {
                phone, resModel, resId,
            })
        } else {
            // No web phone: server-side click-to-call via AMI Originate
            // (rings the user's desk phone first).
            this.env.model.orm.call(
                "connect.settings", "originate_call",
                [phone, resModel, resId], {})
        }
    },
})
