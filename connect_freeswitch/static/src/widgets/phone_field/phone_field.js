/** @odoo-module **/
"use strict"

import {patch} from "@web/core/utils/patch"
import {PhoneField} from "@web/views/fields/phone/phone_field"

patch(PhoneField.prototype, {

    get actionButtons() {
        // Odoo 20: web.FormPhoneField template anchors are gone; the field
        // renders an action-button list instead. Route the standard Call
        // button through the Connect click-to-call dispatcher.
        const buttons = super.actionButtons
        if (buttons.length) {
            buttons[0] = {...buttons[0], href: undefined, onSelected: (ev) => this._onClickCallButton(ev)}
        }
        return buttons
    },


    setup() {
        super.setup()
    },

    _onClickCallButton(e) {
        e.preventDefault()
        const {resModel, resId} = this.props.record.model.config
        const args = [this.props.record.data[this.props.name], resModel, resId]
        this.env.model.orm.call("connect.settings", "originate_call", args, {})
    },
})
