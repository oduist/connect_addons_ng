/** @odoo-module **/
"use strict"
import {useService} from "@web/core/utils/hooks"
import {browser} from "@connect_telnyx/js/utils"

const {Component} = owl
const {useState, onMounted, onWillStart} = owl.hooks

export class PhoneSysTray extends Component {
    constructor() {
        super(...arguments)
        this.bus = this.props.bus
        this.state = useState({
            isDisplay: false,
            inCall: false,
            exception: null,
        })
        this.sound = false
        this.microphone = false
        // Odoo 15 notifications render text, not markup: keep it plain.
        this.message = 'For better user experience grant permission for: '
        this.browser = navigator.userAgent.includes("Firefox") ? browser.firefox : browser.chrome
    }

    setup() {
        this.notification = useService("notification")
        // Disable Permission Check
        // this.permissionsChecked = localStorage.getItem('connect_permissions_checked')
        this.permissionsChecked = 'true'

        onMounted(() => {
            this.bus.addEventListener('busTraySetState', ({detail: {isDisplay, inCall}}) => {
                this.state.isDisplay = isDisplay
                this.state.inCall = inCall
            })
            this.bus.addEventListener('busTraySetException', ({detail: {exception}}) => {
                this.state.exception = exception
            })
            if (this.permissionsChecked) return
            // Check sound permission
            this.testPlayer.play().then(() => {
                this.sound = true
                this.checkPermissions()
            }).catch((e) => {
                this.checkPermissions()
            })
        })

        onWillStart(async () => {
            if (this.permissionsChecked) return
            this.testPlayer = new Audio()
            this.testPlayer.src = "/connect/static/src/sounds/mute.mp3"
            this.testPlayer.volume = 0.5
            const self = this
            // Check microphone permission for Chrome
            if (this.browser === browser.chrome) {
                const permissionStatus = await navigator.permissions.query({name: 'microphone'})
                if (permissionStatus.state === "granted") {
                    this.microphone = true
                }
                // Check microphone permission for Firefox
            } else if (this.browser === browser.firefox) {
                navigator.mediaDevices
                    .getUserMedia({video: false, audio: true})
                    .then((stream) => {
                        stream.getTracks().forEach(function (track) {
                            track.stop()
                            self.microphone = true
                        })
                    })
                    .catch((err) => {
                        console.error(`you got an error: ${err}`)
                    })
            }
        })
    }

    checkPermissions() {
        if (!this.microphone || !this.sound) {
            this.notify()
        }
        localStorage.setItem('connect_permissions_checked', 'true')
    }

    notify() {
        this.message += this.sound ? '' : ' Sound;'
        this.message += this.microphone ? '' : ' Microphone;'
        this.message += ' Sound devices permissions error!'
        this.notification.add(this.message, {title: 'Connect', sticky: true, type: 'warning'})
    }

    _onClick() {
        if (this.state.exception === 'AccessTokenInvalid') {
            this.notification.add('Please reload the page to refresh the Phone!', {title: 'Connect', type: 'warning'})
        } else if (this.state.exception) {
            this.notification.add(this.state.exception, {title: 'Connect', type: 'warning'})
        } else {
            this.bus.trigger('busPhoneToggleDisplay')
        }
    }

    _onClickHangUp() {
        this.bus.trigger('busPhoneHangUp')
        this.state.isDisplay = false
        this.state.inCall = false
    }
}
PhoneSysTray.template = 'connect_telnyx.menu'
PhoneSysTray.props = {
    bus: Object
}
