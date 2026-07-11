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
        this.env.model.orm.call("connect.settings", "originate_call", args, {})
    },
})
