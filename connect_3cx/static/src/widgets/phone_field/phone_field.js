/** @odoo-module **/
"use strict"

import {patch} from "@web/core/utils/patch"
import {PhoneField} from "@web/views/fields/phone/phone_field"
import {useService} from "@web/core/utils/hooks"

patch(PhoneField.prototype, {

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
