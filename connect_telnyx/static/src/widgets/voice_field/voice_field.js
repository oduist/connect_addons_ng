/** @odoo-module **/
"use strict"

import {AutoComplete} from "@web/core/autocomplete/autocomplete"
import {_t} from "@web/core/l10n/translation"
import {registry} from "@web/core/registry"
import {useService} from "@web/core/utils/hooks"
import {Component, onWillStart, useEffect, useState} from "@odoo/owl"
import {standardFieldProps} from "@web/views/fields/standard_field_props"

export class TelnyxVoiceField extends Component {
    static template = "connect_telnyx.TelnyxVoiceField"
    static components = {AutoComplete}
    static props = {...standardFieldProps}

    setup() {
        this.orm = useService("orm")
        this.state = useState({displayValue: this.rawValue, revision: 0})
        onWillStart(() => this.loadDisplayValue())
        useEffect(
            (voiceId) => {
                if (voiceId !== this.state.voiceId) {
                    this.loadDisplayValue()
                }
            },
            () => [this.rawValue]
        )
    }

    get rawValue() {
        return this.props.record.data[this.props.name] || ""
    }

    get language() {
        return this.props.record.data.telnyx_system_voice_language || ""
    }

    get provider() {
        return this.props.record.data.telnyx_system_voice_provider || ""
    }

    get placeholder() {
        if (!this.language || !this.provider) {
            return _t("Choose a language and provider first")
        }
        return _t("Search voices by name, gender, or Telnyx ID")
    }

    get sources() {
        return [{
            placeholder: _t("Loading voices..."),
            options: (search) => this.loadOptions(search),
        }]
    }

    async loadDisplayValue() {
        const voiceId = this.rawValue
        this.state.voiceId = voiceId
        if (!voiceId) {
            this.state.displayValue = ""
            this.state.revision++
            return
        }
        const option = await this.orm.call(
            "connect.settings", "telnyx_get_voice_label", [voiceId]
        )
        if (this.rawValue === voiceId) {
            this.state.displayValue = this.formatOption(option)
            this.state.revision++
        }
    }

    async loadOptions(search) {
        if (!this.language || !this.provider) {
            return []
        }
        const options = await this.orm.call(
            "connect.settings",
            "telnyx_get_voice_options",
            [this.language, this.provider, search, 80]
        )
        return options.map((option) => ({
            label: this.formatOption(option),
            onSelect: () => this.selectOption(option),
        }))
    }

    formatOption(option) {
        if (!option?.details || option.details === option.label) {
            return option?.label || ""
        }
        return `${option.label} - ${option.details}`
    }

    async selectOption(option) {
        this.state.displayValue = this.formatOption(option)
        this.state.voiceId = option.value
        await this.props.record.update({[this.props.name]: option.value})
    }

    resetUnselectedInput({inputValue}) {
        if (inputValue !== this.state.displayValue) {
            this.state.revision++
        }
    }
}

export const telnyxVoiceField = {
    component: TelnyxVoiceField,
    displayName: _t("Telnyx Voice"),
    supportedTypes: ["char"],
}

registry.category("fields").add("telnyx_voice", telnyxVoiceField)
