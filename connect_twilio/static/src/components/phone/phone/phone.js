/** @odoo-module **/
"use strict"
import {loadJS} from "@web/core/assets"
import {useService} from "@web/core/utils/hooks"
import {Calls} from "@connect/components/calls/calls"
import {Favorites} from "@connect_twilio/components/phone/favorites/favorites"
import {Contacts} from "@connect_twilio/components/phone/contacts/contacts"
import {dialTone, setFocus} from "@connect_twilio/js/utils"
import {Component, useState, useRef, onWillStart, onMounted} from "@odoo/owl"
import {useDebounced} from "@web/core/utils/timing"
import {user} from "@web/core/user"

const uid = user.userId

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

    static components = {Calls, Contacts, Favorites}

    constructor() {
        super(...arguments)
        this.bus = this.props.bus
        this.token = this.props.token_data.token
        this.edge = this.props.token_data.edge
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
            recordingState: 'off',
            recordingBusy: false,
            recordingError: '',
            recordingPath: '',
            recordingRef: '',
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

    getRecordingChannelSid() {
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
            channel_sid: this.getRecordingChannelSid(),
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

    async syncRecordingState() {
        const channelSid = this.getRecordingChannelSid()
        if (!channelSid) {
            this.state.recordingState = 'off'
            this.state.recordingError = 'Call SID unavailable'
            return
        }
        try {
            const result = await this.orm.call(
                'connect.channel',
                'get_softphone_recording_state',
                [this._recordingPayload()]
            )
            this._applyRecordingResult(result)
            this._broadcastRecordingState()
        } catch (error) {
            console.warn('Recording state sync failed:', error)
            this.state.recordingState = 'error'
            this.state.recordingError = error.message || String(error)
        }
    }

    isRecordingOn() {
        return this.state.recordingState === 'on' || this.state.recordingState === 'starting'
    }

    isRecordingButtonDisabled() {
        return this.state.recordingBusy || !this.getRecordingChannelSid()
    }

    getRecordingTitle() {
        if (!this.getRecordingChannelSid()) {
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
            clog('Device REGISTERED — web phone is connected to Twilio (identity:', self.userAgent.identity, ', edge:', self.userAgent.edge, ')')
        })
        self.userAgent.on('unregistered', () => {
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

            if (callPartnerId !== 'false') {
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
                await self.syncRecordingState()
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
            await self.syncRecordingState()
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
