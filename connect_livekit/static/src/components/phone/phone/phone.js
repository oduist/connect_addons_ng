/** @odoo-module **/
"use strict"
import {Component, useState, useRef, onMounted, onWillUnmount} from "@odoo/owl"
import {useService} from "@web/core/utils/hooks"
import {loadJS} from "@web/core/assets"

const LIB_URL = '/connect_livekit/static/lib/livekit-client.umd.min.js'

export class LivekitPhone extends Component {
    static template = 'connect_livekit.phone'
    static props = {
        bus: Object,
        config: Object,
    }

    setup() {
        this.orm = useService("orm")
        this.busService = useService("bus_service")
        this.notification = useService("notification")
        this.audioRef = useRef("lkAudio")
        this.state = useState({
            display: false,
            // idle | dialing | ringing | in-call
            status: 'idle',
            number: '',
            peer: '',
            roomName: '',
            muted: false,
        })
        this.room = null
        this.ringtone = new Audio('/connect_livekit/static/src/sounds/incoming-call.mp3')
        this.ringtone.loop = true
        this.ringback = new Audio('/connect_livekit/static/src/sounds/outgoing-call.mp3')
        this.ringback.loop = true

        onMounted(() => {
            this.props.bus.addEventListener('busLivekitPhoneToggle', () => {
                this.state.display = !this.state.display
            })
            this.busService.subscribe('connect_livekit.call', (payload) => {
                this.onBusCall(payload || {})
            })
            this.busService.start()
        })
        onWillUnmount(() => {
            this.stopSounds()
            if (this.room) {
                this.room.disconnect()
            }
        })
    }

    stopSounds() {
        this.ringtone.pause()
        this.ringtone.currentTime = 0
        this.ringback.pause()
        this.ringback.currentTime = 0
    }

    setTrayState() {
        this.props.bus.trigger('busLivekitTrayState', {
            inCall: this.state.status !== 'idle',
        })
    }

    async onBusCall(payload) {
        const action = payload.action
        if (action === 'join') {
            // Click-to-call: the SIP leg is dialing, join the room now.
            this.state.display = true
            this.state.peer = payload.name || payload.number || ''
            this.stopSounds()
            this.ringback.play().catch(() => {})
            await this.joinRoom(payload.room_name, 'dialing')
        } else if (action === 'ring') {
            if (this.state.status !== 'idle') {
                return // busy: leave the caller to other ring targets
            }
            this.state.display = true
            this.state.status = 'ringing'
            this.state.roomName = payload.room_name
            this.state.peer = payload.partner_name || payload.number || ''
            this.ringtone.play().catch(() => {})
            this.setTrayState()
        } else if (action === 'hangup') {
            if (payload.room_name === this.state.roomName) {
                if (this.state.status === 'ringing') {
                    this.reset()
                }
            }
        }
    }

    async ensureLib() {
        if (!window.LivekitClient) {
            await loadJS(LIB_URL)
        }
        return window.LivekitClient
    }

    async joinRoom(roomName, status) {
        const lk = await this.ensureLib()
        const data = await this.orm.call(
            'connect.user', 'get_livekit_room_token', [roomName])
        if (this.room) {
            await this.room.disconnect()
        }
        this.room = new lk.Room()
        this.room
            .on(lk.RoomEvent.TrackSubscribed, (track) => {
                if (track.kind === 'audio') {
                    // The remote party answered.
                    this.stopSounds()
                    this.state.status = 'in-call'
                    this.setTrayState()
                    const media = track.attach()
                    if (this.audioRef.el) {
                        this.audioRef.el.appendChild(media)
                    }
                }
            })
            .on(lk.RoomEvent.TrackUnsubscribed, (track) => {
                track.detach().forEach((m) => m.remove())
            })
            .on(lk.RoomEvent.Disconnected, () => {
                this.reset()
            })
            .on(lk.RoomEvent.ParticipantDisconnected, () => {
                // 1:1 call: the far end left, terminate.
                if (this.room && this.room.remoteParticipants.size === 0) {
                    this.hangup()
                }
            })
        this.state.roomName = roomName
        this.state.status = status || 'in-call'
        this.setTrayState()
        await this.room.connect(this.props.config.ws_url, data.token)
        await this.room.localParticipant.setMicrophoneEnabled(true)
        this.state.muted = false
    }

    onNumberKeydown(ev) {
        if (ev.key === 'Enter') {
            this.dial()
        }
    }

    async dial() {
        const number = (this.state.number || '').trim()
        if (!number || this.state.status !== 'idle') {
            return
        }
        this.state.status = 'dialing'
        this.state.peer = number
        this.setTrayState()
        try {
            // The backend creates the room, dials the SIP leg and pushes
            // the 'join' bus action back to this user.
            await this.orm.call('connect.settings', 'originate_call', [number])
        } catch (e) {
            this.reset()
            throw e
        }
    }

    async accept() {
        this.stopSounds()
        try {
            await this.joinRoom(this.state.roomName, 'in-call')
        } catch (e) {
            this.notification.add(String(e.message || e), {
                title: 'LiveKit Phone', type: 'warning'})
            this.reset()
        }
    }

    async decline() {
        const roomName = this.state.roomName
        this.reset()
        if (roomName) {
            await this.orm.call(
                'connect.user', 'livekit_hangup_room', [roomName])
        }
    }

    async hangup() {
        const roomName = this.state.roomName
        const room = this.room
        this.room = null
        this.reset()
        if (room) {
            await room.disconnect()
        }
        if (roomName) {
            try {
                await this.orm.call(
                    'connect.user', 'livekit_hangup_room', [roomName])
            } catch (e) {
                console.warn('LiveKit hangup failed', e)
            }
        }
    }

    async toggleMute() {
        if (!this.room) {
            return
        }
        const enabled = this.room.localParticipant.isMicrophoneEnabled
        await this.room.localParticipant.setMicrophoneEnabled(!enabled)
        this.state.muted = enabled
    }

    reset() {
        this.stopSounds()
        this.state.status = 'idle'
        this.state.peer = ''
        this.state.roomName = ''
        this.state.muted = false
        if (this.audioRef.el) {
            this.audioRef.el.innerHTML = ''
        }
        this.setTrayState()
    }

    close() {
        this.state.display = false
    }
}
