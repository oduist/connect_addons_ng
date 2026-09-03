/** @odoo-module **/
"use strict"
import {loadJS} from "@web/core/assets"
import {useService} from "@web/core/utils/hooks"
import {Calls} from "@connect/components/calls/calls"
import {Favorites} from "@connect_telnyx/components/phone/favorites/favorites"
import {Contacts} from "@connect_telnyx/components/phone/contacts/contacts"
import {dialTone, setFocus} from "@connect_telnyx/js/utils"
import session from "web.session"
import core from "web.core"

const {Component} = owl
const {useState, useRef, onWillStart, onMounted} = owl.hooks
const _t = core._t

const uid = session.uid

// Odoo 15 has no @web/core/utils/timing useDebounced helper.
function debounce(fn, delay) {
    let timeout
    return function (...args) {
        clearTimeout(timeout)
        timeout = setTimeout(() => fn.apply(this, args), delay)
    }
}

// Thin adapter exposing a Twilio-Device-like session API on top of a
// TelnyxRTC Call, so the phone logic ported from connect_twilio stays
// close to the original.
class TelnyxSession {
    constructor(call) {
        this.call = call
        this.handlers = {}
        this.accepted = false
        this.ended = false
        this.customParameters = new Map()
        const headers = (call.options && call.options.customHeaders) || []
        for (const header of headers) {
            const name = (header.name || '').replace(/^[xX]-/, '')
            this.customParameters.set(name, header.value)
        }
        const remoteNumber = call.options ? (call.options.remoteCallerNumber || '') : ''
        this.parameters = {From: remoteNumber}
    }

    on(event, callback) {
        this.handlers[event] = callback
    }

    _emit(event, data) {
        if (this.handlers[event]) this.handlers[event](data)
    }

    accept() {
        this.call.answer()
    }

    reject() {
        this.call.hangup()
    }

    disconnect() {
        this.call.hangup()
    }

    mute(flag = true) {
        if (flag) {
            this.call.muteAudio()
        } else {
            this.call.unmuteAudio()
        }
    }

    unmute() {
        this.call.unmuteAudio()
    }

    sendDigits(key) {
        this.call.dtmf(key)
    }

    sendDTMF(sequence) {
        this.call.dtmf(sequence)
    }

    refer(destination) {
        console.warn('Transfer is not supported by the Telnyx web phone yet.', destination)
    }
}

export class Phone extends Component {

    constructor() {
        super(...arguments)
        this.bus = this.props.bus
        this.token = this.props.token_data.token
        this.sipDomain = this.props.token_data.sip_domain
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
        this.title = 'Connect Phone'
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
            isTransfer: false,
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
        this.attended_transfer_sequence = '*7'
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
        // TelnyxRTC call id -> TelnyxSession adapter
        this.telnyxSessions = {}
        this.lastTokenRefresh = 0
    }

    setup() {
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

        // Errors are shown even when call popups are switched off: a call
        // that fails silently looks like a broken phone.
        this.notifyError = (message) => {
            this.notification.add(message, {
                title: 'Connect', sticky: true, type: 'danger'})
        }

        this.debounceEnterPhoneNumber = debounce((ev) => {
            this._onEnterPhoneNumber(ev)
        }, 400)

        onWillStart(async () => {
            await loadJS('/connect_telnyx/static/src/lib/telnyx-webrtc.js')

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
                self.offset = [
                    phoneRoot.offsetLeft - e.clientX,
                    phoneRoot.offsetTop - e.clientY
                ]
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
                    const px = self.mousePosition.x + self.offset[0]
                    const py = self.mousePosition.y + self.offset[1]
                    const cx = document.documentElement.clientWidth
                    const cy = document.documentElement.clientHeight

                    let left = px < 10 ? 0 : px
                    left = left + 310 > cx ? cx - 300 : left
                    let top = py < 10 ? 0 : py
                    top = top + 530 > cy ? cy - 520 : top

                    phoneRoot.style.left = left + "px"
                    phoneRoot.style.top = top + "px"
                }
            }, true)
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
                            self.userAgent.connect()
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
                    this.state.isCallForwarded = true
                    if (self.session) {
                        this.session.sendDTMF(`${this.attended_transfer_sequence}${params.phoneNumber}#`)
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
    }

    _busPhoneToggleDisplay() {
        this.state.isDisplayLastState = !this.state.isDisplay
        this.toggleDisplay()
    }

    async _busPhoneHangUp() {
        await this._onClickEndCall()
    }

    async _busPhoneMakeForward(phoneNumber) {
        if (this.session) {
            // TODO: fix forward
            // this.session.sendDTMF(`${this.attended_transfer_sequence}${phoneNumber}#`)
        }
        this.bc.postMessage({event: "tbcForward", params: {phoneNumber}})
        this.state.isDialingPanel = true
        // this.state.isCallForwarded = true
        this.state.isForward = false
        this.state.isContacts = false
    }

    async prepareCall(props) {
        if (!this.state.inCall) {
            this.state.isContactList = false
            this.state.callPhoneNumber = props.phone
            await this.searchPartner(props.phone)
            this.makeCall(props)
        }
    }

    async setCallStatus(status) {
        const currentCallStatus = this.callStatus[status] ? this.callStatus[status] : this.callStatus.Failed
        this.notify(currentCallStatus.toUpperCase(), {sticky: false})
    }

    async updateToken() {
        // TelnyxRTC has no in-place token update: fetch a fresh login
        // token and re-initialize the client.
        const now = (new Date()).getTime()
        if (now - this.lastTokenRefresh < 10000) {
            return
        }
        this.lastTokenRefresh = now
        const {token} = await this.orm.call('connect.user', 'get_telnyx_client_token')
        if (token) {
            this.token = token
            if (this.userAgent) {
                try {
                    await this.userAgent.disconnect()
                } catch (error) {
                    console.warn('Telnyx client disconnect failed:', error)
                }
            }
            this.sipRegistered = false
            this.initUserAgent()
        }
    }

    initUserAgent() {
        const self = this
        if (!self.state.isActive) {
            return
        }

        const options = {
            login_token: self.token,
            ringbackFile: '/connect_telnyx/static/src/sounds/outgoing-call.mp3',
        }
        if (!self.state.isSoundMute) {
            options.ringtoneFile = '/connect_telnyx/static/src/sounds/incoming-call.mp3'
        }
        self.userAgent = new TelnyxWebRTC.TelnyxRTC(options)
        self.userAgent.remoteElement = 'connect-telnyx-remote-audio'
        self.userAgent.enableMicrophone()

        self.userAgent.on('telnyx.ready', () => {
            self.sipRegistered = true
        })

        self.userAgent.on('telnyx.error', (error) => {
            console.error('Telnyx client error:', error)
            const message = self.getTelnyxErrorMessage(error)
            if (message) {
                self.notifyError(message)
            }
            if (self.state.inCall && !self.session) {
                self.endCall()
            }
            // An unusable microphone is not fixed by a fresh token.
            if (error && error.recoverable !== false) {
                self.updateToken().catch((refreshError) => {
                    console.error('Telnyx token refresh failed:', refreshError)
                })
            }
        })

        self.userAgent.on('telnyx.notification', (notification) => {
            self._onTelnyxNotification(notification)
        })

        self.userAgent.connect().catch((error) => {
            console.error('Telnyx client connect failed:', error)
        })
    }

    _onTelnyxNotification(notification) {
        if (notification.type !== 'callUpdate' || !notification.call) {
            return
        }
        const call = notification.call
        const session = this.telnyxSessions[call.id]
        switch (call.state) {
            case 'ringing':
                if (call.direction === 'inbound' && !session) {
                    this._handleIncoming(call).then()
                }
                break
            case 'active':
                if (session && !session.accepted) {
                    session.accepted = true
                    session._emit('accept', call)
                }
                break
            case 'hangup':
            case 'destroy':
                if (session && !session.ended) {
                    session.ended = true
                    delete this.telnyxSessions[call.id]
                    if (session.accepted) {
                        session._emit('disconnect', call)
                    } else {
                        if (call.direction === 'outbound') {
                            this._notifyCallFailure(call).catch(() => {})
                        }
                        session._emit('cancel', call)
                    }
                }
                break
        }
    }

    async _notifyCallFailure(call) {
        // Explain why an outbound call never got connected (ADR-040):
        // without this, a billing-blocked Telnyx account looks exactly
        // like a random call drop.
        const cause = call.cause || ''
        if (['ORIGINATOR_CANCEL', 'NORMAL_CLEARING', 'PURGE'].includes(cause)) {
            // The user hung up before the answer — nothing to explain.
            return
        }
        const sipCode = call.sipCode ? String(call.sipCode) : ''
        const causeMessages = {
            USER_BUSY: 'The number you dialed is busy.',
            CALL_REJECTED: 'The call was rejected.',
            UNALLOCATED_NUMBER: 'Number not found or not routable.',
            INVALID_NUMBER_FORMAT: 'Invalid number format.',
            NO_ANSWER: 'No answer.',
            NO_USER_RESPONSE: 'No answer.',
        }
        const message = causeMessages[cause] ||
            `Call failed: ${cause}${sipCode ? ` (SIP ${sipCode})` : ''}`
        this.notification.add(message, {title: 'Call failed', type: 'warning'})
        if (sipCode === '404' || cause === 'UNALLOCATED_NUMBER') {
            // The ambiguous "not found" case: confirm against the account
            // balance server-side before blaming the dialed number.
            const res = await this.orm.call(
                'connect.settings', 'telnyx_check_call_failure', [],
                {cause, sip_code: sipCode})
            if (res && res.balance_blocked) {
                this.notification.add(res.message, {
                    title: 'Calls blocked', type: 'danger', sticky: true,
                })
            }
        }
    }

    async _handleIncoming(call) {
        const self = this
        const session = new TelnyxSession(call)

        {
            self.state.isContactList = false
            let phoneNumber = session.customParameters.get('From')
            phoneNumber = phoneNumber ? phoneNumber : session.parameters.From
            const callCallerName = session.customParameters.get('CallerName')
            const callPartnerId = session.customParameters.get('Partner')
            const autoAnswer = session.customParameters.get('autoAnswer')

            if (self.session === null) {
                self.session = session
                self.telnyxSessions[call.id] = session
                self.sipSessions.push(self.id)
                const params = {id: self.id, action: 'push'}
                self.bc.postMessage({event: 'tbcSipSession', params})
            } else {
                session.reject()
                return
            }

            self.state.callPhoneNumber = phoneNumber

            if (callPartnerId && callPartnerId !== 'false') {
                self.state.isPartner = true
                self.state.callerId = {
                    partnerId: parseInt(callPartnerId),
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
        }
    }

    setIncomingVolume() {
        // TelnyxRTC configures the ringtone at client construction time;
        // the mute preference is applied on the next client init.
    }

    getJsonCallData() {
        return {
            id: this.session ? this.id : this.sipSessions[0],
            isPartner: this.state.isPartner,
            phoneStatus: this.state.phone_status,
            callerId: JSON.parse(JSON.stringify(this.state.callerId)),
        }
    }

    getTelnyxErrorMessage(error) {
        // The client reports call failures wrapped in an envelope:
        // {error, callId, sessionId, recoverable}.
        while (error && error.error) {
            error = error.error
        }
        const name = error && (error.name || error.code)
        if (name === 'MEDIA_MICROPHONE_PERMISSION_DENIED' || name === 42001
                || name === 'NotAllowedError') {
            return _t(
                "The browser did not grant access to the microphone. Allow it " +
                "for this site (an insecure http:// page never gets it) and " +
                "call again.")
        }
        if (name === 'NotFoundError') {
            return _t("No microphone was found on this device.")
        }
        const description = error && (error.description || error.message)
        return description
            ? _.str.sprintf(_t("Phone error: %s"), description)
            : _t("The phone call could not be started.")
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

        // Route the call through the domain's SIP subdomain so Odoo keeps
        // control of the routing (extensions, caller ID) — ADR-032.
        let destination = phoneNumber
        if (self.sipDomain && !phoneNumber.startsWith('sip:')) {
            destination = `sip:${phoneNumber}@${self.sipDomain}`
        }
        let call
        try {
            call = self.userAgent.newCall({
                destinationNumber: destination,
                audio: true,
                video: false,
            })
        } catch (error) {
            // Without this the widget stays stuck in the "in call" state
            // and the user sees nothing at all — the usual case being a
            // microphone the browser refuses to hand over.
            console.error('Telnyx call could not be started:', error)
            self.notifyError(self.getTelnyxErrorMessage(error))
            await self.endCall()
            return
        }
        self.session = new TelnyxSession(call)
        self.telnyxSessions[call.id] = self.session

        self.session.on("accept", async function () {
            // console.log('outgoing -> accepted: ', data)
            self.createCallCounter(phoneNumber)
            self.state.phone_status = self.status.accepted
            await self.setCallStatus("Answered")
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
        this.state.isTransfer = false
        this.state.isForward = false
        this.state.isCallForwarded = false
        this.state.isMicrophoneMute = false
        this.state.isPartner = false
        this.state.isWhatsapp = false
        this.state.callerId = {}
        this.state.phoneNumber = ''
        this.state.xPhoneInfoDisplay = ''
        this.phoneInput.el.value = this.state.phoneNumber
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
            this.state.isPartner = false
            const pbxUser = await this.getUser(phoneNumber)
            if (pbxUser) {
                this.state.callerId = this.computeUserData(pbxUser, phoneNumber)
            } else {
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
            partnerId: user.id,
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
            this.phoneInput.el.value = this.state.phoneNumber
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
        this.state.isTransfer = false
        this.state.isForward = false
        this.state.isCalls = false
        this.state.isKeypad = false
        this.state.isDialingPanel = true
    }

    _onClickKeypad(ev) {
        this.state.activeTab = this.tabs.phone
        this.state.isContacts = false
        this.state.isTransfer = false
        this.state.isForward = false
        this.state.isCalls = false
        this.state.isKeypad = true
        this.state.isDialingPanel = false
        setFocus(this.phoneInput.el)
    }

    _onClickTransfer(ev) {
        if (this.state.isTransfer) return
        this.state.isForward = false
        this.state.isKeypad = false
        this.state.isDialingPanel = false
        this.state.isContacts = true
        this.state.isTransfer = true
        this.bus.trigger('busContactSetState', {isTransfer: true, isContactMode: true})
    }

    _onClickForward(ev) {
        if (this.state.isForward) return
        this.state.isTransfer = false
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
        if (this.state.inCall) {
            if (this.session) {
                this.sendDTMF(ev.target.textContent)
            } else {
                this.bc.postMessage({event: "tbcDtmf", params: {key: ev.target.textContent}})
            }
        } else {
            this.state.phoneNumber += ev.target.textContent
            this.phoneInput.el.value = this.state.phoneNumber
        }
        this.phoneInput.el.focus()
    }

    _onClickBackSpace(ev) {
        setFocus(this.phoneInput.el)
        this.state.phoneNumber = this.state.phoneNumber.slice(0, -1)
        this.phoneInput.el.value = this.state.phoneNumber
        if (this.state.isContactList) {
            this.bus.trigger('busContactSearchQuery', {searchQuery: this.phoneInput.el.value})
        }
        if (this.state.phoneNumber === '') this.state.isContactList = false
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
Phone.template = 'connect_telnyx.phone'
Phone.props = {
    bus: Object,
    token_data: Object
}
Phone.components = {Calls, Contacts, Favorites}
