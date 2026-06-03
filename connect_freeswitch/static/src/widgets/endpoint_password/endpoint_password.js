/** @odoo-module **/
"use strict"

import {Component, useState} from "@odoo/owl"
import {registry} from "@web/core/registry"
import {useService} from "@web/core/utils/hooks"
import {_t} from "@web/core/l10n/translation"
import {standardFieldProps} from "@web/views/fields/standard_field_props"

/**
 * Read-only display for an auto-generated SIP endpoint password.
 *
 * The value is masked by default; a Show/Hide toggle reveals it in plaintext
 * (useful when typing it into a mobile device without copy/paste) and a Copy
 * button puts it on the clipboard without revealing it.
 */
export class EndpointPasswordField extends Component {
    static template = "connect_freeswitch.EndpointPasswordField"
    static props = {...standardFieldProps}

    setup() {
        this.notification = useService("notification")
        this.state = useState({revealed: false})
    }

    get value() {
        return this.props.record.data[this.props.name] || ""
    }

    toggleReveal() {
        this.state.revealed = !this.state.revealed
    }

    async copyToClipboard() {
        if (!this.value) {
            return
        }
        try {
            await navigator.clipboard.writeText(this.value)
            this.notification.add(_t("Password copied to clipboard"), {type: "success"})
        } catch {
            this.notification.add(_t("Could not access the clipboard"), {type: "warning"})
        }
    }
}

export const endpointPasswordField = {
    component: EndpointPasswordField,
    displayName: _t("Endpoint Password"),
    supportedTypes: ["char"],
}

registry.category("fields").add("endpoint_password", endpointPasswordField)
