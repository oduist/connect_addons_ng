/** @odoo-module **/
"use strict"
import {loadJS} from "@web/core/assets"
import {useService} from "@web/core/utils/hooks"
import {Calls} from "@connect_vonage/components/phone/calls/calls"
import {Favorites} from "@connect_vonage/components/phone/favorites/favorites"
import {Contacts} from "@connect_vonage/components/phone/contacts/contacts"
import {dialTone, setFocus} from "@connect_vonage/js/utils"
import {Component, useState, useRef, onWillStart, onMounted} from "@odoo/owl"
import {useDebounced} from "@web/core/utils/timing"
import {user} from "@web/core/user"

const uid = user.userId

// Thin adapter exposing a Twilio-Device-like session API on top of a
// Vonage Client SDK call, so the phone logic ported from connect_twilio
// stays close to the original. The Client SDK dispatches call events at
// the client level (by callId); initUserAgent() routes them into the
// active session (ADR-036). Remote audio is handled by the SDK itself.
class VonageSession {
    constructor(client, callId, from) {
        this.client = client
        this.callId = callId
        this.handlers = {}
        this.accepted = false
        this.ended = false
        // The Client SDK carries no custom call parameters; caller data
        // is resolved server-side from the From number.
        this.customParameters = new Map()
        this.parameters = {From: from || ''}
    }

    on(event, callback) {
        this.handlers[event] = callback
    }

    _emit(event, data) {
        if (this.handlers[event]) this.handlers[event](data)
    }

    _markAccepted(data) {
        if (!this.accepted && !this.ended) {
            this.accepted = true
            this._emit('accept', data)
        }
    }

    _remoteEnd(data) {
        if (!this.ended) {
            this.ended = true
            this._emit(this.accepted ? 'disconnect' : 'cancel', data)
        }
    }

    accept() {
        this.client.answer(this.callId).then(() => {
            this._markAccepted()
        }).catch((e) => {
            console.error('Vonage answer error:', e)
            this._remoteEnd(e)
        })
    }

    reject() {
        this.client.reject(this.callId).catch((e) => console.warn(e))
        this._remoteEnd()
    }

    disconnect() {
        this.client.hangup(this.callId).catch((e) => console.warn(e))
    }

    mute(flag = true) {
        if (flag) {
            this.client.mute(this.callId)
        } else {
            this.client.unmute(this.callId)
        }
    }

    unmute() {
        this.client.unmute(this.callId)
    }

    sendDigits(key) {
        this.client.sendDTMF(this.callId, key)
    }

    sendDTMF(sequence) {
        this.client.sendDTMF(this.callId, sequence)
    }

    refer(destination) {
        console.warn('Transfer is not supported by the Vonage web phone yet.', destination)
    }
}

// The vendored UMD bundle exposes the SDK as the vonageClientSDK global.
function getVonageSdkApi() {
    const ns = window.vonageClientSDK || window.VonageClientSDK || window
    return {
        VonageClient: ns.VonageClient,
    }
}

export class Phone extends Component {
    static template = 'connect_vonage.phone'
    static props = {
        bus: Object,
        token_data: Object
    }

    static components = {Calls, Contacts, Favorites}

    constructor() {
        super(...arguments)
        this.bus = this.props.bus
        this.token = this.props.token_data.token
        this.tokenTtl = this.props.token_data.ttl || 3600
        this.username = this.props.token_data.username
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
        this.lastTokenRefresh = 0
        this.tokenRefreshTimer = null
        this.ringtoneAudio = null
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
            await loadJS('/connect_vonage/static/src/lib/vonageClientSDK.min.js')

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
                        // The Vonage session persists per tab; nothing to
                        // re-register when another tab closes.
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
        const now = (new Date()).getTime()
        if (now - this.lastTokenRefresh < 10000) {
            return
        }
        this.lastTokenRefresh = now
        const token_data = await this.orm.call('connect.user', 'get_client_token')
        if (token_data.token) {
            this.token = token_data.token
            this.tokenTtl = token_data.ttl || this.tokenTtl
            if (this.userAgent && typeof this.userAgent.refreshSession === 'function') {
                try {
                    await this.userAgent.refreshSession(this.token)
                    this.sipRegistered = true
                    this._scheduleTokenRefresh()
                    return
                } catch (e) {
                    console.warn('refreshSession failed, re-creating session:', e)
                }
            }
            // No in-place refresh available: re-create the session.
            if (this.userAgent && typeof this.userAgent.deleteSession === 'function') {
                try {
                    await this.userAgent.deleteSession()
                } catch (e) {
                    console.warn(e)
                }
            }
            this.initUserAgent()
        }
    }

    _scheduleTokenRefresh() {
        // Session tokens hard-expire (1h TTL): refresh proactively at ~80%.
        if (this.tokenRefreshTimer) {
            clearTimeout(this.tokenRefreshTimer)
            this.tokenRefreshTimer = null
        }
        if (!this.tokenTtl) {
            return
        }
        this.tokenRefreshTimer = setTimeout(() => {
            this.lastTokenRefresh = 0
            this.updateToken().then()
        }, Math.floor(this.tokenTtl * 1000 * 0.8))
    }

    initUserAgent() {
        const self = this
        if (!self.state.isActive) {
            return
        }
        const api = getVonageSdkApi()
        if (!api.VonageClient) {
            console.error('Vonage Client SDK is not loaded')
            return
        }
        self.userAgent = new api.VonageClient()

        self.userAgent.createSession(self.token).then((sessionId) => {
            console.log('Vonage session created:', sessionId)
            self.sipRegistered = true
        }).catch((e) => {
            console.error('Vonage createSession error:', e)
            self.sipRegistered = false
        })

        self.userAgent.on('sessionError', (reason) => {
            console.warn('Vonage session error:', reason)
            self.sipRegistered = false
            self.updateToken().then()
        })

        self.userAgent.on('callInvite', (callId, from, channelType) => {
            if (self.session === null) {
                self._handleIncoming(callId, from).then()
            } else {
                self.userAgent.reject(callId).catch((e) => console.warn(e))
            }
        })

        self.userAgent.on('callInviteCancel', (callId, reason) => {
            if (self.session && self.session.callId === callId) {
                self.session._remoteEnd(reason)
            }
        })

        self.userAgent.on('callHangup', (callId, callQuality, reason) => {
            if (self.session && self.session.callId === callId) {
                self.session._remoteEnd(reason)
            }
        })

        self.userAgent.on('legStatusUpdate', (callId, legId, status) => {
            const answered = String(status).toLowerCase() === 'answered'
            if (answered && self.session && self.session.callId === callId) {
                self.session._markAccepted()
            }
        })

        self._scheduleTokenRefresh()
    }

    _playRingtone() {
        if (this.state.isSoundMute) {
            return
        }
        if (!this.ringtoneAudio) {
            this.ringtoneAudio = new Audio('/connect_vonage/static/src/sounds/incoming-call.mp3')
            this.ringtoneAudio.loop = true
        }
        this.ringtoneAudio.play().catch(() => {})
    }

    _stopRingtone() {
        if (this.ringtoneAudio) {
            this.ringtoneAudio.pause()
            this.ringtoneAudio.currentTime = 0
        }
    }

    async _handleIncoming(callId, from) {
        const self = this
        const session = new VonageSession(self.userAgent, callId, from)

        {
            self.state.isContactList = false
            let phoneNumber = session.customParameters.get('From')
            phoneNumber = phoneNumber ? phoneNumber : session.parameters.From
            const callCallerName = session.customParameters.get('CallerName')
            const callPartnerId = session.customParameters.get('Partner')
            const autoAnswer = session.customParameters.get('autoAnswer')

            if (self.session === null) {
                self.session = session
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
                self._stopRingtone()
                self.createCallCounter(phoneNumber)
                self.state.phone_status = self.status.accepted
                await self.setCallStatus("Answered")
            })
            session.on("disconnect", async function (data) {
                // console.log('incoming -> ended: ', data)
                self._stopRingtone()
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
                self._stopRingtone()
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
                self._stopRingtone()
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
            } else {
                self._playRingtone()
            }
        }
    }

    setIncomingVolume() {
        // The ringtone is played by this component (the SDK has no
        // ringtone option); the mute preference applies immediately.
        if (this.state.isSoundMute) {
            this._stopRingtone()
        }
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

        // serverCall() hits the application answer_url with from_user and
        // this custom data; connect.user.on_client_call builds the
        // outbound NCCO (ADR-036).
        let callId
        try {
            callId = await self.userAgent.serverCall(
                {to: phoneNumber.replace('+', '')})
        } catch (e) {
            console.error('Vonage serverCall error:', e)
            self.state.phone_status = self.status.ended
            await self.endCall()
            return
        }
        self.session = new VonageSession(self.userAgent, callId, phoneNumber)

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
