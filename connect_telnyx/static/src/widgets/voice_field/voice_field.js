/** @odoo-module **/
"use strict"

// Odoo 15 variant (ADR-062): the OWL field registry is 16+; the
// telnyx_voice widget is implemented as a legacy AbstractField with a
// jQuery UI autocomplete (the same machinery the legacy many2one uses)
// plus the Telnyx sample-playback button of the 19.0 branch.
import AbstractField from "web.AbstractField"
import fieldRegistry from "web.field_registry"
import core from "web.core"

const _t = core._t

const TelnyxVoiceField = AbstractField.extend({
    className: 'o_field_telnyx_voice',
    supportedFieldTypes: ['char'],
    events: Object.assign({}, AbstractField.prototype.events, {
        'click .o_telnyx_voice_play': '_onClickPlay',
    }),

    init() {
        this._super(...arguments)
        const options = this.nodeOptions || {}
        this.languageField = options.language_field || 'telnyx_system_voice_language'
        this.providerField = options.provider_field || 'telnyx_system_voice_provider'
        this.speedField = options.speed_field || ''
        this.textField = options.text_field || ''
        this.displayValue = ''
        this.audio = null
        this.playing = false
    },

    willStart() {
        return Promise.all([this._super(...arguments), this._loadDisplayValue()])
    },

    destroy() {
        this._stopSample()
        this._super(...arguments)
    },

    async _loadDisplayValue() {
        if (!this.value) {
            this.displayValue = ''
            return
        }
        const option = await this._rpc({
            model: this.model,
            method: 'telnyx_get_voice_label',
            args: [this.value],
        })
        this.displayValue = this._formatOption(option)
    },

    _formatOption(option) {
        if (!option || !option.details || option.details === option.label) {
            return (option && option.label) || ''
        }
        return `${option.label} - ${option.details}`
    },

    async _loadOptions(search) {
        const language = this.recordData[this.languageField] || ''
        const provider = this.recordData[this.providerField] || ''
        if (!language || !provider) {
            return []
        }
        const options = await this._rpc({
            model: this.model,
            method: 'telnyx_get_voice_options',
            args: [language, provider, search || '', 80],
        })
        const self = this
        return options.map((option) => ({
            label: self._formatOption(option),
            value: self._formatOption(option),
            option,
        }))
    },

    _renderReadonly() {
        this.$el.empty()
        $('<span/>').text(this.displayValue || this.value || '').appendTo(this.$el)
        if (this.value) {
            this._appendPlayButton()
        }
    },

    _renderEdit() {
        this.$el.empty()
        const placeholder = (!this.recordData[this.languageField] ||
                !this.recordData[this.providerField])
            ? _t("Choose a language and provider first")
            : _t("Search voices by name, gender, or Telnyx ID")
        this.$input = $('<input type="text" class="o_input"/>')
            .attr('placeholder', placeholder)
            .val(this.displayValue || this.value || '')
            .appendTo(this.$el)
        const self = this
        this.$input.autocomplete({
            source: function (request, response) {
                self._loadOptions(request.term).then(response).catch(() => response([]))
            },
            select: function (ev, ui) {
                self._selectOption(ui.item)
                return false
            },
            minLength: 0,
            delay: 300,
        })
        this.$input.on('focus', function () {
            self.$input.autocomplete('search',
                self.$input.val() === (self.displayValue || '') ? '' : self.$input.val())
        })
        this.$input.on('blur', function () {
            // An unselected free-text input is not a voice id: restore the
            // last selected label, as the 19.0 widget does.
            self.$input.val(self.displayValue || '')
        })
        if (this.value) {
            this._appendPlayButton()
        }
    },

    _selectOption(item) {
        if (!item.option) {
            return
        }
        this.displayValue = item.label
        this.$input.val(item.label)
        this._setValue(item.option.value)
    },

    _appendPlayButton() {
        $('<button type="button" class="btn btn-link o_telnyx_voice_play" ' +
          'title="Play a sample of this voice"><i class="fa fa-play"/></button>')
            .appendTo(this.$el)
    },

    _stopSample() {
        if (this.audio) {
            this.audio.pause()
            this.audio = null
        }
        this.playing = false
    },

    /**
     * Play a Telnyx sample of the selected voice. Telnyx validates the voice
     * and the speed here exactly as it does for the assistant greeting, so an
     * unusable combination is reported while the form is still open.
     */
    async _onClickPlay(ev) {
        ev.preventDefault()
        if (this.playing || !this.value) {
            return
        }
        this._stopSample()
        this.playing = true
        const speed = this.speedField
            ? this.recordData[this.speedField] || 1.0
            : 1.0
        const text = this.textField
            ? this.recordData[this.textField] || false
            : false
        let result
        try {
            result = await this._rpc({
                model: this.model,
                method: 'telnyx_preview_voice',
                args: [this.value, speed, text],
            })
        } catch (error) {
            this.playing = false
            throw error
        }
        this.audio = new Audio(`data:audio/mpeg;base64,${result.audio}`)
        this.audio.addEventListener('ended', () => this._stopSample())
        this.audio.addEventListener('error', () => this._stopSample())
        try {
            await this.audio.play()
        } catch (e) {
            // Autoplay policies can refuse playback without a user gesture.
            this._stopSample()
        }
    },
})

fieldRegistry.add('telnyx_voice', TelnyxVoiceField)

export default TelnyxVoiceField
