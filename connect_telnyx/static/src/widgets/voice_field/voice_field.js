/** @odoo-module **/
"use strict"

import {AutoComplete} from "@web/core/autocomplete/autocomplete"
import {_t} from "@web/core/l10n/translation"
import {registry} from "@web/core/registry"
import {useService} from "@web/core/utils/hooks"
import {Component, onWillStart, onWillUnmount, useEffect, useState} from "@odoo/owl"
import {standardFieldProps} from "@web/views/fields/standard_field_props"

export class TelnyxVoiceField extends Component {
    static template = "connect_telnyx.TelnyxVoiceField"
    static components = {AutoComplete}
    static props = {
        ...standardFieldProps,
        languageField: {type: String},
        providerField: {type: String},
        speedField: {type: String, optional: true},
        textField: {type: String, optional: true},
    }

    setup() {
        this.orm = useService("orm")
        this.state = useState({displayValue: this.rawValue, revision: 0, playing: false})
        this.audio = null
        onWillStart(() => this.loadDisplayValue())
        onWillUnmount(() => this.stopSample())
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
        return this.props.record.data[this.props.languageField] || ""
    }

    get provider() {
        return this.props.record.data[this.props.providerField] || ""
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
            this.props.record.resModel, "telnyx_get_voice_label", [voiceId]
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
            this.props.record.resModel,
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

    stopSample() {
        if (this.audio) {
            this.audio.pause()
            this.audio = null
        }
        this.state.playing = false
    }

    /**
     * Play a Telnyx sample of the selected voice. Telnyx validates the voice
     * and the speed here exactly as it does for the assistant greeting, so an
     * unusable combination is reported while the form is still open.
     */
    async playSample() {
        if (this.state.playing || !this.rawValue) {
            return
        }
        this.stopSample()
        this.state.playing = true
        const speed = this.props.speedField
            ? this.props.record.data[this.props.speedField] || 1.0
            : 1.0
        const text = this.props.textField
            ? this.props.record.data[this.props.textField] || false
            : false
        let result
        try {
            result = await this.orm.call(
                this.props.record.resModel,
                "telnyx_preview_voice",
                [this.rawValue, speed, text]
            )
        } catch (error) {
            this.state.playing = false
            throw error
        }
        this.audio = new Audio(`data:audio/mpeg;base64,${result.audio}`)
        this.audio.addEventListener("ended", () => this.stopSample())
        this.audio.addEventListener("error", () => this.stopSample())
        try {
            await this.audio.play()
        } catch {
            // Autoplay policies can refuse playback without a user gesture.
            this.stopSample()
        }
    }
}

export const telnyxVoiceField = {
    component: TelnyxVoiceField,
    displayName: _t("Telnyx Voice"),
    supportedTypes: ["char"],
    supportedOptions: [
        {
            label: _t("Language filter field"),
            name: "language_field",
            type: "field",
            availableTypes: ["selection"],
        },
        {
            label: _t("Provider filter field"),
            name: "provider_field",
            type: "field",
            availableTypes: ["selection"],
        },
        {
            label: _t("Voice speed field"),
            name: "speed_field",
            type: "field",
            availableTypes: ["float"],
        },
        {
            label: _t("Sample text field"),
            name: "text_field",
            type: "field",
            availableTypes: ["char", "text"],
        },
    ],
    extractProps: ({options}) => ({
        languageField: options.language_field || "telnyx_system_voice_language",
        providerField: options.provider_field || "telnyx_system_voice_provider",
        speedField: options.speed_field || "",
        textField: options.text_field || "",
    }),
}

registry.category("fields").add("telnyx_voice", telnyxVoiceField)
