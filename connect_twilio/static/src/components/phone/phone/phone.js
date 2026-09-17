/** @odoo-module **/
"use strict"
import {loadJS} from "@web/core/assets"
import {useService} from "@web/core/utils/hooks"
import {Recents} from "@connect_twilio/components/phone/recents/recents"
import {Favorites} from "@connect_twilio/components/phone/favorites/favorites"
import {Contacts} from "@connect_twilio/components/phone/contacts/contacts"
import {contactInitial, contactTone, dialTone, setFocus} from "@connect_twilio/js/utils"
import {Component, useState, useRef, onWillStart, onMounted, onPatched, onWillUnmount} from "@odoo/owl"
import {useDebounced} from "@web/core/utils/timing"
import {user} from "@web/core/user"

const uid = user.userId

const clamp = (value, low, high) => Math.min(Math.max(value, low), high)

// Connection diagnostics: single prefix so admins can filter the browser
// console by "[Connect Phone]" when a web phone fails to connect / call.
const LOG_PREFIX = '[Connect Phone]'
const clog = (...args) => console.log(LOG_PREFIX, ...args)
const cwarn = (...args) => console.warn(LOG_PREFIX, ...args)
const cerror = (...args) => console.error(LOG_PREFIX, ...args)

// Human-readable hints for the most common Twilio Voice error codes so the
// reason a phone won't connect is obvious straight from the console.
function explainTwilioError(error) {
    const code = error && error.code
    const hints = {
        20101: 'Invalid Access Token — check Twilio API Key/Secret and Account SID in Connect settings.',
        20104: 'Access Token expired — the token TTL elapsed; it should auto-refresh.',
        31005: 'Connection error (transport/WebSocket to Twilio failed) — check network/firewall/proxy and that wss to Twilio is allowed.',
        31009: 'Transport error — no transport available to send the message.',
        31201: 'Error acquiring microphone — no audio input device available.',
        31202: 'Microphone permission denied by the user/browser.',
        31208: 'Microphone permission prompt was dismissed — grant mic access for this site.',
        31402: 'Media acquisition failed — the browser could not get the microphone (permissions, no device, or it is used by another app). This is the #1 reason an outgoing call ends instantly.',
        31003: 'ICE connection failed — media path could not be established (NAT/firewall blocking UDP/media).',
        31000: 'General/unknown Twilio Voice error.',
        31204: 'Access Token: invalid signature.',
        31205: 'Access Token expired.',
    }
    return hints[code] || (error && error.explanation) || ''
}

export class Phone extends Component {
    static template = 'connect_twilio.phone'
    static props = {
        bus: Object,
        token_data: Object
    }

    static components = {Recents, Contacts, Favorites}

    constructor() {
        super(...arguments)
        this.bus = this.props.bus
        this.token = this.props.token_data.token
        this.edge = this.props.token_data.edge
        // Whether this user's calls are recorded by configuration. Used to
        // show the recording state as soon as a call is answered instead of
        // waiting for Twilio to list it (see applyExpectedRecordingState).
        this.recordCalls = !!this.props.token_data.record_calls
        // Shown in the header and under the favourites grid: who this phone
        // is, and what the far end sees when it calls out.
        this.exten = this.props.token_data.exten || ''
        this.outgoingCallerId = this.props.token_data.outgoing_callerid || ''
        this.callStatus = {
            NoAnswer: 'noanswer',
            Busy: 'busy',
            Rejected: 'busy',
            Answered: 'answered',
            Terminated: 'hangup',
            Canceled: 'canceled',
            Failed: 'failed'
        }
        this.tabs = {
            phone: 'phone',
            contacts: 'contacts',
            calls: 'calls',
            favorites: 'favorites',
        }
        this.status = {
            incoming: 'incoming',
            outgoing: 'outgoing',
            connecting: 'connecting',
            accepted: 'accepted',
            ended: 'ended'
        }
        this.title = 'Connect'
        this.state = useState({
            isActive: true,
            isDisplay: false,
            isDisplayLastState: false,
            isMicrophoneMute: false,
            isSoundMute: localStorage.getItem('connect_is_sound_mute') === 'true',
            isKeypad: true,
            isContacts: false,
            isFavorites: false,
            isCalls: false,
            isPartner: false,
            isForward: false,
            isCallForwarded: false,
            isDialingPanel: false,
            inCall: false,
            inIncoming: false,
            isContactList: false,
            isWhatsapp: false,
            phoneNumber: '',
            callPhoneNumber: '',
            contact_search_query: '',
            user_search_query: '',
            partnerName: '',
            partnerId: '',
            partnerUrl: '',
            partnerIconUrl: '',
            users: [],
            activeTab: this.tabs.phone,
            callDurationTime: '',
            callerId: {},
            xTransferTo: '',
            xTransferInfo: '',
            xTransferPartner: false,
            phone_status: this.status.ended,
            calls: [],
            recordingState: 'off',
            recordingBusy: false,
            recordingError: '',
            recordingPath: '',
            recordingRef: '',
            // {name, exten, sub} for the contact the typed number resolves to.
            dialMatch: null,
            // Drives the header dot: green only when Twilio has us registered.
            registered: false,
        })
        this.callDuration = 0
        this.callDurationTimerInstance = null
        this.phoneInput = useRef('connect-phone-input')

        this.user = uid
        this.sipRegistered = false
        this.lastActiveTab = this.tabs.phone
        this.session = null
        this.userAgent = null
        this.call_id = null
        this.call_popup_is_enabled = false
        this.call_popup_is_sticky = false
        this.phone_ring_volume = 70
        this.disconnect_call_sequence = '**'
        // Move Phone
        this.mousePosition = {}
        this.offset = [0, 0]
        this.isDown = false
        this.phoneRoot = useRef("phone-root")
        this.phoneHeader = useRef("phone-header")
        // BroadcastChannel
        this.bc = new BroadcastChannel("connect")
        this.contactSearch = 'all'
        this.id = Math.floor(Math.random() * 1000000)
        this.windows = [this.id]
        this.sipSessions = []
        this.suppressBroadcastChannel = false
    }

    setup() {
        super.setup()
        this.orm = useService('orm')
        this.action = useService('action')
        this.notification = useService("notification")

        this.notify = (message, {title = 'Connect', sticky = null, type = 'info'}) => {
            if (sticky === null) {
                sticky = this.call_popup_is_sticky
            }
            if (this.call_popup_is_enabled) {
                this.notification.add(message, {title, sticky, type})
            }
        }

        this.debounceEnterPhoneNumber = useDebounced((ev) => {
            this._onEnterPhoneNumber(ev)
        }, 400)

        onWillStart(async () => {
            await loadJS('/connect_twilio/static/src/lib/twilio.min.js')

            // EVENTS
            this.bus.addEventListener('busPhoneMakeCall', ({detail}) => this.prepareCall(detail))

            this.bus.addEventListener('busPhoneMakeForward', ({detail}) => this._busPhoneMakeForward(detail))

            this.bus.addEventListener('busPhoneToggleDisplay', ({detail}) => this._busPhoneToggleDisplay(detail))

            this.bus.addEventListener('busPhoneHangUp', ({detail}) => this._busPhoneHangUp(detail))

            window.addEventListener("beforeunload", (event) => {
                if (this.session) {
                    event = event || window.event
                    const message = "You're in call! Are you sure you want to close?"
                    if (event) {
                        event.returnValue = message
                    }
                    return message
                }
            })

            window.addEventListener("unload", (event) => {
                if (this.session) {
                    const params = {id: this.id, action: 'pop'}
                    this.bc.postMessage({event: 'tbcSipSession', params})
                    this.bc.postMessage({event: "tbcCloseTab", params: {id: this.id}})
                    this.session.disconnect()
                }
            })
        })

        onMounted(() => {
            this.initUserAgent()

            const phoneRoot = this.phoneRoot.el
            this.phoneHeader.el.addEventListener("mousedown", function (e) {
                self.isDown = true
                // Measured, not read off offsetLeft: the panel is zoomed, so
                // its own coordinates and the pointer's are not the same
                // scale, and the two only agree at the start of a drag by
                // accident.
                const rect = phoneRoot.getBoundingClientRect()
                self.offset = [rect.left - e.clientX, rect.top - e.clientY]
            }, true)

            document.addEventListener("mouseup", function () {
                self.isDown = false
            }, true)

            document.addEventListener("mousemove", function (event) {
                if (self.isDown) {
                    event.preventDefault()
                    self.mousePosition = {
                        x: event.clientX,
                        y: event.clientY
                    }
                    self._moveTo(
                        self.mousePosition.x + self.offset[0],
                        self.mousePosition.y + self.offset[1],
                    )
                }
            }, true)

            // A window the panel fits in can be resized out from under it,
            // and the panel's own height follows the window, so the clamp has
            // to run again rather than only while the pointer is down.
            this._onViewportResize = () => this._keepOnScreen()
            window.addEventListener("resize", this._onViewportResize)
            // BroadcastChannel Events
            const self = this
            this.bc.onmessage = ({data: {event, params}}) => {
                return
                // console.log('tbc.onMessage', {event, params})
                const localStartCall = () => {
                    if (self.session) return
                    // console.log('tbcStartCall -> ... INIT')
                    const {callerId, isPartner} = params
                    self.state.isPartner = isPartner
                    self.state.callerId = callerId

                    self.state.inIncoming = true
                    self.state.isDialingPanel = true
                    self.startCall()
                }
                if (event === 'tbcStartCall') {
                    // console.log('tbcStartCall', params)
                    if (!self.session && !self.state.inIncoming) {
                        self.state.isDisplayLastState = self.state.isDisplay
                    }
                    localStartCall()
                    if (self.id === self.windows.at(-1) && !self.session) {
                        const ringParams = {id: self.sipSessions[0]}
                        self.bc.postMessage({event: "tbcRing", params: ringParams})
                    }
                } else if (event === 'tbcAnswerCall') {
                    // console.log('tbcAnswerCall', params)
                    if (self.session && params.id === self.id) {
                        self.session.accept()
                    }
                    localStartCall()
                    self.state.inIncoming = false
                    self.state.phone_status = self.status.accepted
                    if (self.session) {
                        setTimeout(() => {
                            localStartCall()
                            self.state.inIncoming = false
                            self.state.phone_status = self.status.accepted
                        }, 500)
                    }

                } else if (event === "tbcEndCall") {
                    // console.log("tbcEndCall")
                    if (self.session) {
                        self.suppressBroadcastChannel = true
                        self.session.disconnect()
                    }
                    self.state.phone_status = self.status.ended
                    self.endCall().then()
                } else if (event === 'tbcNewTab') {
                    // console.log('tbcNewTab', params)
                    self.windows.push(params.id)
                    if (self.session) {
                        const syncParams = self.getJsonCallData()
                        self.bc.postMessage({event: "tbcSync", params: syncParams})
                    }
                } else if (event === 'tbcCloseTab') {
                    // console.log('tbcCloseTab', params)
                    const index = self.windows.indexOf(params.id)
                    if (index > -1) {
                        self.windows.splice(index, 1)
                        if (self.id === self.windows.at(-1)) {
                            self.userAgent.register()
                        }
                    }
                } else if (event === 'tbcDtmf') {
                    // console.log('tbcDtmf', params)
                    if (self.session) {
                        self.sendDTMF(params.key)
                    }
                } else if (event === 'tbcTransfer') {
                    // console.log('tbcTransfer', params)
                    if (self.session) {
                        self.session.refer(params.phoneNumber)
                    }
                } else if (event === 'tbcForward') {
                    // console.log('tbcForward', params)
                    // Unreachable: this whole handler returns above, and
                    // forwarding is a REST redirect now
                    // (connect.channel.forward_softphone_call). The '*7'
                    // feature code never meant anything to Twilio.
                    this.state.isCallForwarded = true
                    if (self.session) {
                        this.session.sendDTMF(`*7${params.phoneNumber}#`)
                    }
                } else if (event === 'tbcMicrophoneMute') {
                    // console.log('tbcMicrophoneMute')
                    if (self.session) {
                        if (params.mute === true) {
                            self.session.mute()
                        } else {
                            self.session.unmute()
                        }
                    }
                    self.state.isMicrophoneMute = params.mute
                } else if (event === 'tbcSoundMute') {
                    // console.log('tbcSoundMute')
                    self.state.isSoundMute = params.mute
                    self.setIncomingVolume()
                } else if (event === 'tbcRecordingState') {
                    self._applyRecordingResult(params)
                } else if (event === 'tbcCancelForward') {
                    // console.log('tbcCancelForward')
                    self._cancelForward()
                } else if (event === 'tbcSync') {
                    // console.log('tbcSync', params)
                    if (self.state.inCall === false) {
                        self.state.callerId = params.callerId
                        self.state.isPartner = params.isPartner
                        self.state.inCall = true
                        self.state.phone_status = params.phoneStatus
                        self.startCall()
                    }
                } else if (event === 'tbcSipSession') {
                    // console.log('tbcSipSession', params)
                    const {action} = params
                    if (action === 'push') {
                        self.sipSessions.push(params.id)
                    } else if (action === 'clear') {
                        self.sipSessions = []
                    } else if (action === 'pop') {
                        const index = self.sipSessions.indexOf(params.id)
                        if (index > -1) {
                            self.sipSessions.splice(index, 1)
                        }
                        if (self.sipSessions.length === 0) {
                            self.state.phone_status = self.status.ended
                            self.endCall().then()
                        }
                    }
                } else if (event === 'tbcRing') {
                    // if (params.id === self.id) self.incomingPlayer.play().catch()
                }
            }
            this.bc.postMessage({event: "tbcNewTab", params: {id: this.id}})
        })

        onPatched(() => {
            // A hidden panel is `display: none` and measures zero, so a window
            // resized while it was away could not be answered then. Answer it
            // the moment it comes back.
            if (this.state.isDisplay && !this._wasDisplayed) {
                this._keepOnScreen()
            }
            this._wasDisplayed = this.state.isDisplay
        })

        onWillUnmount(() => {
            window.removeEventListener("resize", this._onViewportResize)
        })
    }

    // ------------------------------------------------------------ position

    /**
     * Where the panel may sit, in viewport coordinates.
     *
     * The whole of it has to stay in the window. Both far edges are worked
     * out from its measured size rather than from constants: the panel is
     * only ever positioned from its top-left corner, and its height follows
     * the window through `max-height`. The constants this replaces described
     * a 300x520 panel that has not existed since the redesign, which is why
     * the phone could be dragged 80px past the right edge and 180px past the
     * bottom one.
     */
    _clampToViewport(left, top) {
        const rect = this.phoneRoot.el.getBoundingClientRect()
        const cx = document.documentElement.clientWidth
        const cy = document.documentElement.clientHeight
        return [
            clamp(left, 0, Math.max(0, cx - rect.width)),
            clamp(top, 0, Math.max(0, cy - rect.height)),
        ]
    }

    /**
     * Move the panel to a position measured on screen.
     *
     * `left`/`top` resolve in the panel's own coordinates, which the zoom
     * scales afterwards, so the zoom has to be divided back out -- otherwise
     * the panel lands short of the pointer, by more the further it is dragged.
     */
    _moveTo(left, top) {
        const el = this.phoneRoot.el
        const [x, y] = this._clampToViewport(left, top)
        const zoom = parseFloat(getComputedStyle(el).zoom) || 1
        el.style.left = (x / zoom) + "px"
        el.style.top = (y / zoom) + "px"
    }

    /**
     * Put the panel back inside the window if something moved it out.
     *
     * A panel that has never been dragged is still parked on `bottom: 0` with
     * no `left`/`top` of its own, and nothing can push that off screen, so it
     * is left alone -- writing coordinates would only pin it where it happens
     * to be.
     */
    _keepOnScreen() {
        const el = this.phoneRoot.el
        if (!el || (!el.style.left && !el.style.top)) {
            return
        }
        const rect = el.getBoundingClientRect()
        if (!rect.width || !rect.height) {
            // Hidden: `display: none` measures zero, and clamping against
            // that would move the panel to the top-left corner.
            return
        }
        this._moveTo(rect.left, rect.top)
    }


    // ====================================================================
    // What the panel is showing
    //
    // Exactly one body screen is live at a time, and the ground follows from
    // it. Incoming wins over everything -- a ringing phone is the only thing
    // worth looking at -- and the after-call summary is checked before the
    // in-call screens so the 100ms during which endCall() still reports
    // inCall does not flash the call screen back up.
    // ====================================================================

    get screen() {
        const s = this.state
        if (s.inIncoming) return 'incoming'
        if (s.isForward) return 'forward'
        if (s.inCall && s.isKeypad) return 'dtmf'
        if (s.inCall) return 'incall'
        if (s.isCalls) return 'recents'
        if (s.isFavorites) return 'favorites'
        if (s.isContactList) return 'contacts'
        return 'keypad'
    }

    /** The three screens the dial input belongs to. */
    get showDialField() {
        const screen = this.screen
        return screen === 'keypad' || screen === 'contacts' || screen === 'dtmf'
    }

    /** The two screens the search results belong to. */
    get showContacts() {
        const screen = this.screen
        return screen === 'contacts' || screen === 'forward'
    }

    /**
     * True on the screens that belong to a live call.
     *
     * The panel is one light ground throughout; this no longer picks a
     * colour, it only says "a call is on" -- which is what suppresses the tab
     * bar, because during a call there is nowhere else to go.
     */
    get isCallScreen() {
        return ['incoming', 'forward', 'dtmf', 'incall'].includes(this.screen)
    }

    get headerTitle() {
        switch (this.screen) {
            case 'incoming': return 'Incoming'
            case 'forward': return 'Forward to'
            case 'dtmf':
            case 'incall': return 'On a call'
            default: return this.title
        }
    }

    get headerSub() {
        if (this.screen === 'incall' || this.screen === 'dtmf') {
            return this.state.callDurationTime ? `· ${this.state.callDurationTime}` : ''
        }
        if (this.screen === 'incoming' || this.screen === 'forward') return ''
        return this.exten ? `· ext ${this.exten}` : ''
    }

    get headerDotClass() {
        if (this.screen === 'incoming') return 'o_csp_dot_ring'
        if (this.isCallScreen) return 'o_csp_dot_on'
        return this.state.registered ? 'o_csp_dot_on' : ''
    }

    /** Who is on the line, for the screens that keep the call in a strip. */
    get liveCallName() {
        const callerId = this.state.callerId || {}
        return callerId.partnerName || callerId.phoneNumber || ''
    }

    get stageAvatar() {
        // false when there is nobody to take a picture from; the template
        // falls back to a coloured initial rather than a missing image.
        return this.state.callerId.partnerIconUrl || false
    }

    /** Label the stage tile falls back to when there is no avatar. */
    get stageLabel() {
        const callerId = this.state.callerId || {}
        return callerId.partnerName || callerId.phoneNumber || ''
    }

    initial(text) {
        return contactInitial(text)
    }

    tone(text) {
        return contactTone(text)
    }

    /** The number the far end sees; shown under the favourites grid. */
    get callerId() {
        return this.outgoingCallerId || this.exten || ''
    }

    // ====================================================================
    // The live match under the dial field
    // ====================================================================

    /**
     * Name what the user is typing, as they type it. One row is enough: the
     * full result list is a click away on the same screen, and a second line
     * of detail under a half-typed number is noise.
     */
    async _updateDialMatch(query) {
        const trimmed = (query || '').trim()
        if (!trimmed) {
            this.state.dialMatch = null
            return
        }
        const [pbxUsers, partners] = await Promise.all([
            // Same reason as the colleague list: the connect.user record rule
            // would otherwise resolve only the caller's own extension.
            this.orm.call("connect.user", "search_directory", [trimmed, 1]),
            this.orm.searchRead(
                "res.partner",
                ['|', ['phone_mobile_search', '=ilike', `%${trimmed}%`],
                 ['name', '=ilike', `%${trimmed}%`]],
                ['name', 'function'],
                {order: 'name asc', limit: 1},
            ),
        ])
        // The query may have moved on while these were in flight.
        if (this.state.phoneNumber.trim() !== trimmed) return
        if (pbxUsers.length) {
            this.state.dialMatch = {name: pbxUsers[0].name, exten: pbxUsers[0].exten_number}
        } else if (partners.length) {
            this.state.dialMatch = {name: partners[0].name, sub: partners[0].function || ''}
        } else {
            this.state.dialMatch = null
        }
    }

    // ====================================================================
    // Messaging from the keypad
    // ====================================================================

    _onClickSendSms() {
        const number = this.state.phoneNumber
        if (!number) return
        this.action.doAction({
            type: 'ir.actions.act_window',
            target: 'new',
            name: 'Send SMS',
            res_model: 'sms.composer',
            views: [[false, 'form']],
            context: {
                default_composition_mode: 'numbers',
                default_numbers: number,
            },
        })
    }

    _onClickSendWhatsapp() {
        const number = this.state.phoneNumber
        if (!number) return
        this.action.doAction({
            type: 'ir.actions.act_window',
            target: 'new',
            name: 'Send WhatsApp Message',
            res_model: 'connect.whatsapp_composer',
            views: [[false, 'form']],
            context: {default_phone: number},
        })
    }

    /** Leave the forward picker without dropping the call. */
    _onClickForwardBack() {
        this.state.isForward = false
        this.state.isContacts = false
        this.state.isContactList = false
        // Tell the picker it is over. Without this its contact mode stays on,
        // so reopening it neither clears the last search nor takes focus
        // again -- the mode never changed, so nothing reacts to it.
        this.bus.trigger('busContactSetState', {})
        this._onClickDialingPanel()
    }

    _busPhoneToggleDisplay() {
        this.state.isDisplayLastState = !this.state.isDisplay
        this.toggleDisplay()
    }

    async _busPhoneHangUp() {
        await this._onClickEndCall()
    }

    /**
     * Blind-transfer the live call.
     *
     * The server moves the other party's leg; this leg then drops on its own
     * when Twilio tears the bridge down, which is what ends the call here.
     * Nothing is changed on screen until the server has accepted the
     * transfer, so a failure leaves the user on the call rather than on a
     * panel that claims the transfer happened.
     */
    async _busPhoneMakeForward(phoneNumber) {
        const number = (phoneNumber || '').trim()
        if (!number) {
            this.notification.add('That contact has no number to forward to.',
                {title: 'Connect', type: 'warning'})
            return
        }
        try {
            await this.orm.call('connect.channel', 'forward_softphone_call', [{
                provider: 'twilio',
                channel_sid: this.getLiveChannelSid(),
                number,
            }])
        } catch (error) {
            cerror('Forwarding the call failed:', error)
            this.notification.add(error.message || String(error),
                {title: 'Forward', type: 'danger'})
            return
        }
        this.bc.postMessage({event: "tbcForward", params: {phoneNumber: number}})
        this.state.isForward = false
        this.state.isContacts = false
        this.state.isDialingPanel = true
        this.notify('Forwarded to {}'.replace('{}', number),
            {sticky: false, type: 'success'})
        // Leave the call ourselves rather than waiting to be dropped. On an
        // inbound call Twilio kills our leg as soon as the customer is
        // redirected away, but on an outbound one our leg is the one running
        // the <Dial>: that Dial simply completes and the leg lives on, which
        // would strand the agent on a call with nobody.
        await this._onClickEndCall()
    }

    async prepareCall(props) {
        // Every dial converges here -- the keypad, the contact and favourite
        // lists, the recent list, click-to-call from a form -- so this is the
        // one place worth refusing an empty number. Twilio accepts a call with
        // an empty To, rings nobody, and leaves a blank row in the ledger; the
        // user is owed an explanation instead.
        const phone = (props && props.phone ? String(props.phone) : '').trim()
        if (!phone) {
            cwarn('Refusing to place a call with no number.', props)
            this.notification.add('That contact has no number to call.',
                {title: 'Connect', type: 'warning'})
            return
        }
        if (!this.state.inCall) {
            this.state.isContactList = false
            this.state.callPhoneNumber = phone
            await this.searchPartner(phone)
            this.makeCall({...props, phone})
        }
    }

    async setCallStatus(status) {
        const currentCallStatus = this.callStatus[status] ? this.callStatus[status] : this.callStatus.Failed
        this.notify(currentCallStatus.toUpperCase(), {sticky: false})
    }

    getLiveChannelSid() {
        if (!this.session) {
            return ''
        }
        if (this.session.parameters && this.session.parameters.CallSid) {
            return this.session.parameters.CallSid
        }
        if (
            this.session.customParameters
            && typeof this.session.customParameters.get === 'function'
            && this.session.customParameters.get('CallSid')
        ) {
            return this.session.customParameters.get('CallSid')
        }
        return ''
    }

    _recordingPayload() {
        return {
            provider: 'twilio',
            channel_sid: this.getLiveChannelSid(),
        }
    }

    _applyRecordingResult(result) {
        if (!result) {
            return
        }
        this.state.recordingState = result.state || 'off'
        this.state.recordingRef = result.recording_ref || ''
        this.state.recordingPath = result.recording_path || ''
        this.state.recordingError = result.error || ''
        this.state.recordingBusy = ['starting', 'stopping'].includes(this.state.recordingState)
    }

    _broadcastRecordingState() {
        this.bc.postMessage({
            event: 'tbcRecordingState',
            params: {
                state: this.state.recordingState,
                recording_ref: this.state.recordingRef,
                recording_path: this.state.recordingPath,
                error: this.state.recordingError,
            },
        })
    }

    // Both inputs this needs arrive after "accept", not with it: the Twilio SDK
    // fills in the CallSid asynchronously, and the connect.channel row is
    // created by the Twilio webhook, which races the event. A single attempt
    // therefore samples a state that is legitimately not ready yet, and because
    // nothing re-syncs afterwards the result sticks for the whole call -- with
    // no CallSid isRecordingButtonDisabled() is true, so the button sits greyed
    // out through a call that the Record Calls option is recording. Retry until
    // the answer is real, and give up only once the call is over.
    // Show what the configuration says straight away, so the button is right
    // from the first frame of the call rather than after a round trip. Twilio
    // cannot answer this early: with <Dial record="record-from-answer"> the
    // recording does not exist until the far end picks up, so the API would
    // report "off" for the whole ring. syncRecordingState() then confirms it,
    // or corrects it if recording never actually started.
    applyExpectedRecordingState() {
        this.state.recordingState = this.recordCalls ? 'on' : 'off'
        this.state.recordingBusy = false
        this.state.recordingError = ''
        this._broadcastRecordingState()
    }

    // The "accept" event fires when THIS leg reaches Twilio, not when the far
    // end picks up (a call that rings out unanswered still reports accepted).
    // With <Dial record="record-from-answer"> the recording only starts once
    // the callee answers, so the wait is however long the phone rings -- no
    // short fixed window can cover it. Poll at a low rate for the first
    // minute, and only overwrite the configured state once Twilio has a real
    // answer, so the button never flickers back to idle during the ring.
    async syncRecordingState({attempts = 40, delay = 1500} = {}) {
        for (let attempt = 0; attempt < attempts; attempt++) {
            if (attempt) {
                await new Promise((resolve) => setTimeout(resolve, delay))
            }
            // The call may have ended while we were waiting; endCall() owns the
            // reset in that case, so leave its state alone.
            if (this.state.phone_status !== this.status.accepted) {
                return
            }
            if (!this.getLiveChannelSid()) {
                continue
            }
            try {
                const result = await this.orm.call(
                    'connect.channel',
                    'get_softphone_recording_state',
                    [this._recordingPayload()]
                )
                // "off" with no reference is not an answer yet, it is Twilio
                // saying the recording has not appeared -- which is the normal
                // case for the whole ring. Applying it would undo the
                // configured state we showed at accept, so keep looking
                // instead; the tail below corrects it if it never shows up.
                const serverState = (result && result.state) || 'off'
                const settled = serverState !== 'off' || (result && result.recording_ref)
                if (!settled) {
                    continue
                }
                this._applyRecordingResult(result)
                this._broadcastRecordingState()
                return
            } catch (error) {
                // "Active call was not found" just means the webhook has not
                // landed yet, so keep trying and only surface the last failure.
                if (attempt < attempts - 1) {
                    continue
                }
                console.warn('Recording state sync failed:', error)
                this.state.recordingState = 'error'
                this.state.recordingError = error.message || String(error)
                this._broadcastRecordingState()
                return
            }
        }
        if (this.state.phone_status !== this.status.accepted) {
            return
        }
        // Out of attempts without Twilio ever reporting a recording.
        if (!this.getLiveChannelSid()) {
            this.state.recordingState = 'off'
            this.state.recordingError = 'Call SID unavailable'
            this._broadcastRecordingState()
            return
        }
        // We had a CallSid and Twilio consistently said nothing is recording,
        // so if we optimistically showed "on" from the configuration, that
        // guess was wrong (recording never started) -- correct it now.
        if (this.state.recordingState === 'on' && !this.state.recordingRef) {
            this.state.recordingState = 'off'
            this._broadcastRecordingState()
        }
    }

    isRecordingOn() {
        return this.state.recordingState === 'on' || this.state.recordingState === 'starting'
    }

    isRecordingButtonDisabled() {
        return this.state.recordingBusy || !this.getLiveChannelSid()
    }

    getRecordingTitle() {
        if (!this.getLiveChannelSid()) {
            return 'Recording unavailable'
        }
        if (this.state.recordingBusy) {
            return this.state.recordingState === 'starting' ? 'Starting recording' : 'Stopping recording'
        }
        if (this.state.recordingState === 'error') {
            return this.state.recordingError || 'Recording error'
        }
        return this.isRecordingOn() ? 'Stop Recording' : 'Start Recording'
    }

    getRecordingIconClass() {
        if (this.state.recordingState === 'error') {
            return 'fa fa-exclamation-triangle'
        }
        if (this.state.recordingBusy) {
            return 'fa fa-spinner fa-spin'
        }
        return this.isRecordingOn() ? 'fa fa-stop-circle' : 'fa fa-dot-circle-o'
    }

    async _onClickRecordingToggle() {
        if (this.isRecordingButtonDisabled()) {
            return
        }
        const action = this.isRecordingOn() ? 'stop_softphone_recording' : 'start_softphone_recording'
        this.state.recordingBusy = true
        this.state.recordingState = this.isRecordingOn() ? 'stopping' : 'starting'
        this._broadcastRecordingState()
        try {
            const result = await this.orm.call(
                'connect.channel',
                action,
                [this._recordingPayload()]
            )
            this._applyRecordingResult(result)
            this._broadcastRecordingState()
        } catch (error) {
            this.state.recordingState = 'error'
            this.state.recordingError = error.message || String(error)
            this.state.recordingBusy = false
            this._broadcastRecordingState()
            this.notify(this.state.recordingError, {title: 'Recording', sticky: false, type: 'danger'})
        }
    }

    async updateToken() {
        const result = await this.orm.call('connect.user', 'get_client_token')
        const {token, error} = result || {}
        if (error) {
            cerror('get_client_token returned an error:', error)
            return
        }
        if (token) {
            clog('Fetched a fresh access token — updating device.')
            this.userAgent.updateToken(token)
        } else {
            cerror('get_client_token returned no token — the phone cannot connect. Likely the user is not Client Enabled or Twilio username/domain/TwiML app are missing.')
        }
    }

    initUserAgent() {
        const self = this
        if (!self.state.isActive) {
            cwarn('Web phone is not active (state.isActive is false) — device will not be initialized.')
            return
        }

        // Log what we start with: a missing/empty token means the server
        // (connect.user.get_client_token) refused — usually client not
        // enabled, or username/domain/TwiML app missing in Connect settings.
        clog('Initializing Twilio Device', {
            tokenPresent: !!self.token,
            tokenLength: self.token ? String(self.token).length : 0,
            edge: self.edge,
        })
        if (!self.token) {
            cerror('No Twilio access token — cannot connect. Check the user is Client Enabled and that Twilio username/domain/TwiML app are configured.')
        }

        // logLevel: 2 = "info" (loglevel scale: 0 trace, 1 debug, 2 info,
        // 3 warn, 4 error, 5 silent). At info the Twilio SDK itself logs
        // registration and connection lifecycle so "registered"/"connecting"
        // messages are visible when diagnosing a phone that won't connect.
        self.userAgent = new Twilio.Device(self.token, {
            edge: self.edge,
            logLevel: 2,
            codecPreferences: ["opus", "pcmu"]
        })

        // Device lifecycle: these tell you exactly how far the connection got.
        self.userAgent.on('registering', () => {
            clog('Device registering… (edge:', self.userAgent.edge, ')')
        })
        self.userAgent.on('registered', () => {
            self.state.registered = true
            clog('Device REGISTERED — web phone is connected to Twilio (identity:', self.userAgent.identity, ', edge:', self.userAgent.edge, ')')
        })
        self.userAgent.on('unregistered', () => {
            self.state.registered = false
            cwarn('Device UNREGISTERED — web phone is no longer connected to Twilio. If it flaps, the same user identity is likely registered in another tab/device.')
        })

        this.setIncomingVolume()
        self.userAgent.on('tokenWillExpire', () => {
            clog('Access token is about to expire — refreshing token…')
            self.updateToken().then()
        })

        self.userAgent.on('error', (error) => {
            // Always surface the full error with a decoded reason.
            cerror('Device error:', {
                name: error && error.name,
                code: error && error.code,
                message: error && error.message,
                reason: explainTwilioError(error),
            }, error)
            if (error.name === 'AccessTokenExpired') {
                clog('AccessTokenExpired — refreshing token…')
                self.updateToken().then()
            } else if (error.name === 'AccessTokenInvalid') {
                cerror('AccessTokenInvalid — the phone cannot connect. Verify Twilio API Key/Secret/Account SID in Connect settings.')
                self.bus.trigger('busTraySetException', {exception: error.name})
            }
        })
        let lastTime = (new Date()).getTime()
        // HANDLE RTCSession
        self.userAgent.on("incoming", async function (session) {
            self.state.isContactList = false
            let phoneNumber = session.customParameters.get('From')
            phoneNumber = phoneNumber ? phoneNumber : session.parameters.From
            if (phoneNumber.startsWith("whatsapp:")) {
                phoneNumber = phoneNumber.replace(/^whatsapp:/, "")
                self.state.isWhatsapp = true
            }
            const callCallerName = session.customParameters.get('CallerName')
            const callPartnerId = session.customParameters.get('Partner')
            const autoAnswer = session.customParameters.get('autoAnswer')

            if (self.session === null) {
                self.session = session
                self.sipSessions.push(self.id)
                const params = {id: self.id, action: 'push'}
                self.bc.postMessage({event: 'tbcSipSession', params})
            } else {
                let isPartner = false
                let callerId = {phoneNumber}
                session.reject()
                return
            }

            self.state.callPhoneNumber = phoneNumber

            // Treat the caller as a known partner only when a real numeric
            // Partner id was supplied. A missing/empty/'false'/non-numeric
            // value (e.g. a code path that omits the parameter) must fall
            // through to searchPartner() so the contact is resolved by number
            // instead of rendering NaN / the raw number in the name slot.
            const callPartnerIdInt = parseInt(callPartnerId)
            if (callPartnerId && callPartnerId !== 'false' && !Number.isNaN(callPartnerIdInt)) {
                self.state.isPartner = true
                self.state.callerId = {
                    partnerId: callPartnerIdInt,
                    partnerName: callCallerName,
                    partnerIconUrl: self.computePartnerIconUrl(callPartnerId),
                    partnerUrl: self.computePartnerUrl(callPartnerId),
                    phoneNumber,
                }
            } else {
                self.state.callerId = {phoneNumber}
                await self.searchPartner(phoneNumber)
            }

            self.state.isDisplayLastState = self.state.isDisplay
            if (!self.state.isDisplay) {
                self.toggleDisplay()
            }
            const params = self.getJsonCallData()
            self.bc.postMessage({event: "tbcStartCall", params})

            self.state.inIncoming = true
            self.state.isDialingPanel = true
            self.startCall()
            // incoming call here
            session.on("accept", async function (data) {
                // console.log('incoming -> accept: ', data)
                self.createCallCounter(phoneNumber)
                self.state.phone_status = self.status.accepted
                await self.setCallStatus("Answered")
                // Show the configured recording state immediately, then let the
                // Twilio sync confirm or correct it in the background.
                self.applyExpectedRecordingState()
                // Not awaited: it polls for up to a minute and must not hold up
                // the rest of the accept handler; it updates state reactively.
                self.syncRecordingState()
            })
            session.on("disconnect", async function (data) {
                // console.log('incoming -> ended: ', data)
                self.state.phone_status = self.status.ended
                await self.setCallStatus("Canceled")
                await self.endCall()
                self.session = null
                if (self.suppressBroadcastChannel) {
                    self.suppressBroadcastChannel = false
                } else {
                    self.bc.postMessage({event: "tbcEndCall"})
                }
            })
            session.on("cancel", async function (data) {
                // console.log('incoming -> failed: ', data)
                self.state.phone_status = self.status.ended
                await self.setCallStatus("Canceled")
                const index = self.sipSessions.indexOf(self.id)
                self.sipSessions.splice(index, 1)
                const params = {id: self.id, action: 'pop'}
                self.bc.postMessage({event: 'tbcSipSession', params})
                self.session = null
                await self.endCall()
            })
            session.on("reject", async function (data) {
                // console.log('incoming -> reject')
                self.state.phone_status = self.status.ended
                await self.setCallStatus("Rejected")
                const index = self.sipSessions.indexOf(self.id)
                self.sipSessions.splice(index, 1)
                const params = {id: self.id, action: 'pop'}
                self.bc.postMessage({event: 'tbcSipSession', params})
                self.session = null
                await self.endCall()
            })

            if (autoAnswer === 'yes') {
                // console.log('Auto Answer')
                session.accept()
                self.state.phone_status = self.status.accepted
                self.state.inIncoming = false
                self.startCall()
            }
        })

        clog('Calling device.register()…')
        self.userAgent.register().then(() => {
            clog('device.register() resolved (registration accepted).')
        }).catch((error) => {
            cerror('device.register() FAILED — web phone did not connect:', {
                name: error && error.name,
                code: error && error.code,
                message: error && error.message,
                reason: explainTwilioError(error),
            }, error)
        })
    }

    setIncomingVolume() {
        this.userAgent.audio.incoming(!this.state.isSoundMute)
    }

    getJsonCallData() {
        return {
            id: this.session ? this.id : this.sipSessions[0],
            isPartner: this.state.isPartner,
            phoneStatus: this.state.phone_status,
            callerId: JSON.parse(JSON.stringify(this.state.callerId)),
        }
    }

    async makeCall(props) {
        const self = this
        let phoneNumber = props.phone
        if (phoneNumber.length > 8 && phoneNumber[0] !== '+') {
            phoneNumber = `+${phoneNumber}`
        }
        self.startCall()

        const syncParams = self.getJsonCallData()
        self.bc.postMessage({event: "tbcSync", params: syncParams})

        const params = {
            To: phoneNumber,
            Called: phoneNumber,
        }

        // A call needs microphone access (getUserMedia). If the device is not
        // registered, or the mic can't be acquired, connect() throws here —
        // this is the most common "call ends instantly" failure.
        clog('Placing outgoing call', {
            to: phoneNumber,
            deviceState: self.userAgent && self.userAgent.state,
        })
        if (self.userAgent && self.userAgent.state !== 'registered') {
            cwarn('Placing a call while device is not "registered" (state:', self.userAgent && self.userAgent.state, ') — the call may fail.')
        }
        try {
            self.session = await self.userAgent.connect({params})
        } catch (error) {
            cerror('Failed to start outgoing call — connect() threw:', {
                name: error && error.name,
                code: error && error.code,
                message: error && error.message,
                reason: explainTwilioError(error),
            }, error)
            self.state.phone_status = self.status.ended
            await self.setCallStatus('Failed')
            await self.endCall()
            self.session = null
            return
        }

        // Surface call-level errors (e.g. media/ICE failures) during the call.
        self.session.on("error", function (error) {
            cerror('Call error:', {
                name: error && error.name,
                code: error && error.code,
                message: error && error.message,
                reason: explainTwilioError(error),
            }, error)
        })

        self.session.on("accept", async function () {
            // console.log('outgoing -> accepted: ', data)
            self.createCallCounter(phoneNumber)
            self.state.phone_status = self.status.accepted
            await self.setCallStatus("Answered")
            // Show the configured recording state immediately, then let the
            // Twilio sync confirm or correct it in the background.
            self.applyExpectedRecordingState()
            // Not awaited: it polls for up to a minute and must not hold up
            // the rest of the accept handler; it updates state reactively.
            self.syncRecordingState()
            const params = self.getJsonCallData()
            self.bc.postMessage({event: "tbcAnswerCall", params})
        })
        self.session.on("disconnect", async function () {
            // console.log('outgoing -> ended: ', data)
            self.state.phone_status = self.status.ended
            await self.setCallStatus('Disconnect')
            await self.endCall()
            self.session = null
            if (self.suppressBroadcastChannel) {
                self.suppressBroadcastChannel = false
            } else {
                self.bc.postMessage({event: "tbcEndCall"})
            }
        })
        self.session.on("cancel", async function () {
            // console.log('outgoing -> ended: ', data)
            self.state.phone_status = self.status.ended
            await self.setCallStatus('Cancel')
            await self.endCall()
            self.session = null
            if (self.suppressBroadcastChannel) {
                self.suppressBroadcastChannel = false
            } else {
                self.bc.postMessage({event: "tbcEndCall"})
            }
        })
    }

    startCall() {
        this.state.inCall = true
        this.state.isDialingPanel = true
        this.state.isContacts = false
        this.state.isFavorites = false
        this.state.isCalls = false
        this.state.isDisplay = true
        this.state.isKeypad = false
        this.bus.trigger('busTrayState', {isDisplay: this.state.isDisplay, inCall: this.state.inCall})
    }

    async endCall() {
        this.state.isDisplay = this.state.isDisplayLastState
        this.state.isContactList = false
        this.state.isDialingPanel = false
        this.state.inIncoming = false
        this.state.isKeypad = this.lastActiveTab === this.tabs.phone
        this.state.isContacts = this.lastActiveTab === this.tabs.contacts
        this.state.isFavorites = this.lastActiveTab === this.tabs.favorites
        this.state.isCalls = this.lastActiveTab === this.tabs.calls
        this.state.isForward = false
        this.state.isCallForwarded = false
        this.state.isMicrophoneMute = false
        this.state.isPartner = false
        this.state.isWhatsapp = false
        this.state.callerId = {}
        this.state.phoneNumber = ''
        this.state.dialMatch = null
        this.state.xPhoneInfoDisplay = ''
        if (this.phoneInput.el) {
            this.phoneInput.el.value = this.state.phoneNumber
        }
        this.bus.trigger('busTrayState', {isDisplay: this.state.isDisplay, inCall: this.state.inCall})
        this.state.activeTab = this.lastActiveTab
        if (this.lastActiveTab === this.tabs.calls) {
            this.getCalls()
        }
        const self = this
        setTimeout(() => self.state.inCall = false, 100)

        this.destroyCallCounter()
        this.sipSessions = []
        this.state.xTransferTo = ''
        this.state.xTransferInfo = ''
        this.state.xTransferPartner = false
        this.state.recordingState = 'off'
        this.state.recordingBusy = false
        this.state.recordingError = ''
        this.state.recordingPath = ''
        this.state.recordingRef = ''
    }

    _openPartner(id) {
        this.action.doAction({
            res_id: id,
            res_model: 'res.partner',
            target: 'current',
            type: 'ir.actions.act_window',
            views: [[false, 'form']],
        })
    }

    async searchPartner(phoneNumber) {
        const partner = await this.getPartner(phoneNumber)
        if (partner) {
            this.state.isPartner = true
            this.state.callerId = this.computePartnerData(partner, phoneNumber)
        } else {
            const pbxUser = await this.getUser(phoneNumber)
            if (pbxUser) {
                // An internal call: no partner matches the extension, but the
                // colleague behind it has one, so there is still a contact to
                // open and nothing to create.
                this.state.callerId = this.computeUserData(pbxUser, phoneNumber)
                this.state.isPartner = !!this.state.callerId.partnerId
            } else {
                this.state.isPartner = false
                this.state.callerId = {phoneNumber}
            }
        }
        return partner
    }

    async getPartner(phoneNumber) {
        const partner = await this.orm.call("res.partner", 'api_get_partner', [phoneNumber])
        return partner.id ? partner : false
    }

    computePartnerData(partner, phoneNumber) {
        return {
            partnerId: partner.id,
            partnerName: partner.name,
            partnerIconUrl: this.computePartnerIconUrl(partner.id),
            partnerUrl: this.computePartnerUrl(partner.id),
            phoneNumber: phoneNumber,
        }
    }

    computePartnerUrl(partnerId) {
        return `/web#id=${partnerId}&model=res.partner&view_type=form`
    }

    computePartnerIconUrl(partnerId) {
        return `/web/image?model=res.partner&field=avatar_128&id=${partnerId}`
    }

    async getUser(phoneNumber) {
        return await this.orm.call("connect.user", 'get_user_by_exten_number', [phoneNumber])
    }

    computeUserData(user, phoneNumber) {
        return {
            // The colleague's own contact, from get_user_by_exten_number.
            // This field used to hold the connect.user id, which would have
            // opened an unrelated contact had anything followed it.
            partnerId: user.partner_id || false,
            partnerName: user.name,
            partnerIconUrl: this.computeUserIconUrl(user.user[0]),
            phoneNumber: phoneNumber,
        }
    }

    computeUserIconUrl(userId) {
        return `/web/image?model=res.users&field=avatar_128&id=${userId}`
    }

    createCallCounter(phoneNumber) {
        const self = this
        self.callDuration = 0
        self.state.callDurationTime = '00:00:00'
        self.callDurationTimerInstance = setInterval(() => {
            self.callDuration += 1
            if (self.state.callerId.phoneNumber === phoneNumber) {
                self.state.callDurationTime = new Date((self.callDuration) * 1000).toISOString().substring(11, 19)
            }
        }, 1000)
    }

    destroyCallCounter() {
        const self = this
        self.state.callDurationTime = ''
        clearInterval(self.callDurationTimerInstance)
    }

    setLastActiveTab() {
        this.lastActiveTab = this.state.activeTab
    }

    toggleDisplay() {
        if (this.state.isActive) {
            this.state.isDisplay = !this.state.isDisplay
            if (this.state.inCall) {
                this.state.isKeypad = false
                this.state.isDialingPanel = true
                this.state.isContacts = false
                this.state.isCalls = false
                this.state.activeTab = this.tabs.phone
                this.bus.trigger('busTraySetState', {isDisplay: this.state.isDisplay, inCall: this.state.inCall})
            } else {
                setFocus(this.phoneInput.el)
            }
        } else {
            this.notify('Missing configs! Check "User / Preferences"!', {sticky: false})
        }
    }

    getCalls() {
        this.bus.trigger('busCallsGetCalls')
    }

    _onClickMakeCall(ev) {
        if (this.state.phoneNumber) {
            this.state.callPhoneNumber = this.state.phoneNumber.replace(/\(|\)|-| /gm, '')
            this.state.phoneNumber = ''
            this.state.dialMatch = null
            if (this.phoneInput.el) {
                this.phoneInput.el.value = this.state.phoneNumber
            }
            this.prepareCall({phone: this.state.callPhoneNumber})
        } else {
            this.notify("The phone call has no number!", {sticky: false})
        }
    }

    _onClickContactCall(phoneNumber) {
        this.prepareCall({phone: phoneNumber})
    }

    _onClickPhone(ev) {
        this.state.activeTab = this.tabs.phone
        this.setLastActiveTab()
        if (this.state.inCall) {
            this.state.isKeypad = false
            this.state.isDialingPanel = true
        } else {
            this.state.isKeypad = true
            this.state.isDialingPanel = false
        }
        this.state.isContacts = false
        this.state.isCalls = false
        this.state.isFavorites = false
        setFocus(this.phoneInput.el)
    }

    _onClickContacts(ev) {
        this.state.activeTab = this.tabs.contacts
        this.setLastActiveTab()
        this.bus.trigger('busContactSetState', {isContact: true, isContactMode: true})
        this.state.isKeypad = false
        this.state.isContacts = true
        this.state.isContactList = false
        this.state.isFavorites = false
        this.state.isCalls = false
        this.state.isDialingPanel = false
    }

    _onClickFavorites(ev) {
        this.state.activeTab = this.tabs.favorites
        this.setLastActiveTab()
        this.state.isKeypad = false
        this.state.isContacts = false
        this.state.isContactList = false
        this.state.isFavorites = true
        this.state.isCalls = false
        this.state.isDialingPanel = false
    }

    _onClickHistory(ev) {
        this.state.activeTab = this.tabs.calls
        this.setLastActiveTab()
        this.state.isKeypad = false
        this.state.isContacts = false
        this.state.isContactList = false
        this.state.isFavorites = false
        this.state.isCalls = true
        this.state.isDialingPanel = false
        this.getCalls()
    }

    _onClickDialingPanel(ev) {
        this.state.activeTab = this.tabs.phone
        this.state.isContacts = false
        this.state.isForward = false
        this.state.isCalls = false
        this.state.isKeypad = false
        this.state.isDialingPanel = true
    }

    _onClickKeypad(ev) {
        this.state.activeTab = this.tabs.phone
        this.state.isContacts = false
        this.state.isForward = false
        this.state.isCalls = false
        this.state.isKeypad = true
        this.state.isDialingPanel = false
        // Start from an empty field: what belongs here now is the tones sent
        // on this call, not the number that started it.
        this.state.phoneNumber = ''
        this.state.dialMatch = null
        if (this.phoneInput.el) {
            this.phoneInput.el.value = ''
        }
        setFocus(this.phoneInput.el)
    }

    _onClickForward(ev) {
        if (this.state.isForward) return
        this.state.isKeypad = false
        this.state.isDialingPanel = false
        this.state.isForward = true
        this.state.isContacts = true
        this.bus.trigger('busContactSetState', {isForward: true, isContactMode: true})
    }

    _onClickMicrophoneMute(ev) {
        if (this.session) {
            if (this.state.isMicrophoneMute) {
                this.session.mute(false)
            } else {
                this.session.mute(true)
            }
        }
        this.state.isMicrophoneMute = !this.state.isMicrophoneMute
        this.bc.postMessage({event: "tbcMicrophoneMute", params: {mute: this.state.isMicrophoneMute}})
    }

    _onClickSoundMute(ev) {
        this.state.isSoundMute = !this.state.isSoundMute
        localStorage.setItem('connect_is_sound_mute', `${this.state.isSoundMute}`)
        this.bc.postMessage({event: "tbcSoundMute", params: {mute: this.state.isSoundMute}})
        this.setIncomingVolume()
    }


    async _onClickEndCall(ev) {
        if (this.session) {
            this.suppressBroadcastChannel = true
            this.session.disconnect()
        }
        this.bc.postMessage({event: "tbcEndCall"})
        this.state.phone_status = this.status.ended
        await this.endCall()
        if (this.lastActiveTab === this.tabs.phone) {
            setFocus(this.phoneInput.el)
        }
    }

    _onClickAcceptIncoming(ev) {
        if (this.session) {
            this.session.accept()
        }
        const params = this.getJsonCallData()
        this.bc.postMessage({event: "tbcAnswerCall", params})
        this.state.phone_status = this.status.accepted
        this.state.inIncoming = false
        this.startCall()
    }

    async _onClickRejectIncoming(ev) {
        if (this.session) {
            this.suppressBroadcastChannel = true
            this.session.reject()
        }
        this.bc.postMessage({event: "tbcEndCall"})
        this.state.inIncoming = false
        await this.endCall()
        if (this.lastActiveTab === this.tabs.phone) {
            setFocus(this.phoneInput.el)
        }
    }

    _onClickClose(ev) {
        this.state.isDisplayLastState = !this.state.isDisplay
        this.toggleDisplay()
    }

    _onClickKeypadButton(ev) {
        const key = ev.currentTarget.textContent.trim().charAt(0)
        if (this.state.inCall) {
            if (this.session) {
                this.sendDTMF(key)
            } else {
                this.bc.postMessage({event: "tbcDtmf", params: {key}})
            }
            this.state.phoneNumber += key
            if (this.phoneInput.el) {
                this.phoneInput.el.value = this.state.phoneNumber
            }
        } else {
            this.state.phoneNumber += key
            if (this.phoneInput.el) {
                this.phoneInput.el.value = this.state.phoneNumber
            }
            this._updateDialMatch(this.state.phoneNumber)
        }
        if (this.phoneInput.el) {
            this.phoneInput.el.focus()
        }
    }

    _onClickBackSpace(ev) {
        setFocus(this.phoneInput.el)
        this.state.phoneNumber = this.state.phoneNumber.slice(0, -1)
        if (this.phoneInput.el) {
            this.phoneInput.el.value = this.state.phoneNumber
        }
        if (this.state.isContactList) {
            this.bus.trigger('busContactSearchQuery', {searchQuery: this.state.phoneNumber})
        }
        if (this.state.phoneNumber === '') this.state.isContactList = false
        this._updateDialMatch(this.state.phoneNumber)
    }

    sendDTMF(key) {
        const validDTMF = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '#']
        if (validDTMF.includes(key)) {
            // dialTone(key)
            this.session.sendDigits(key)
        }
    }


    _onEnterPhoneNumber(ev) {
        if (this.state.inCall) {
            this.sendDTMF(ev.key)
        } else {
            if (ev.key === "Enter") {
                this._onClickMakeCall()
            } else {
                this.state.phoneNumber = this.phoneInput.el.value
                this.state.isContactList = this.state.phoneNumber !== ''
                this.bus.trigger('busContactSetState', {isContact: true})
                this.bus.trigger('busContactSearchQuery', {searchQuery: this.phoneInput.el.value})
                this._updateDialMatch(this.state.phoneNumber)
            }
        }
    }

    _createPartner() {
        const context = {
            default_phone: this.state.callerId.phoneNumber,
            call_id: this.call_id,
            default_name: `Partner ${this.state.callerId.phoneNumber}`
        }
        this.action.doAction({
            context,
            res_model: 'res.partner',
            target: 'new',
            type: 'ir.actions.act_window',
            views: [[false, 'form']],
        })
    }

    _cancelForward() {
        this.state.isCallForwarded = false
        if (this.session) {
            this.session.sendDTMF(this.disconnect_call_sequence)
        } else {
            this.bc.postMessage({event: "tbcCancelForward"})
        }
    }
}
