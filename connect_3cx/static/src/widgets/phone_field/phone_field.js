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
        return buttons
    },


    setup() {
        super.setup()
        this.threecxAction = useService("action")
    },

    async _onClickCallButton(e) {
        e.preventDefault()
        const {resModel, resId} = this.props.record.model.config
        const args = [this.props.record.data[this.props.name], resModel, resId]
        // The core dispatcher routes by the user's click-to-call provider.
        // The 3CX provider returns an ir.actions.act_url opening the 3CX
        // Web Client dial URL; other providers originate server-side and
        // return a plain truthy value, which is ignored here.
        const result = await this.env.model.orm.call(
            "connect.settings", "originate_call", args, {})
        if (result && typeof result === "object" && result.type) {
            this.threecxAction.doAction(result)
        }
    },
})
