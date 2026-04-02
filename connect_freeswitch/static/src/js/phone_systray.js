/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";


export class PhoneDialpad extends Component {
    static template = "connect_freeswitch.PhoneDialpad";
    static props = {
        close: Function,
        vertoClient: { type: Object, optional: true },
        state: String,
        callState: String,
        callerName: { type: String, optional: true },
        callerNumber: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            number: "",
            muted: false,
            callDuration: 0,
        });

        this.numberInput = useRef("numberInput");
        this.durationInterval = null;

        onMounted(() => {
            this.numberInput.el?.focus();
        });

        onWillUnmount(() => {
            this._stopDurationTimer();
        });
    }

    onInputKeydown(ev) {
        if (ev.key === "Enter") {
            this.onCall();
        }
    }

    get isConnected() {
        return this.props.state === "registered" || this.props.state === "reconnecting";
    }

    get isCallActive() {
        return ["calling", "ringing", "active"].includes(this.props.callState);
    }

    get isIncoming() {
        return this.props.callState === "incoming";
    }

    onKeyPress(digit) {
        if (this.props.callState === "active") {
            this.props.vertoClient?.sendDTMF(digit);
        } else if (this.props.callState === "idle") {
            this.state.number += digit;
        }
    }

    onBackspace() {
        this.state.number = this.state.number.slice(0, -1);
    }

    onClear() {
        this.state.number = "";
    }

    async onCall() {
        if (!this.state.number || !this.props.vertoClient) return;

        try {
            await this.props.vertoClient.call(this.state.number);
            this._startDurationTimer();
        } catch (error) {
            console.error("Call failed:", error);
        }
    }

    async onAnswer() {
        if (!this.props.vertoClient) return;

        try {
            await this.props.vertoClient.answer();
            this._startDurationTimer();
        } catch (error) {
            console.error("Answer failed:", error);
        }
    }

    async onHangup() {
        if (!this.props.vertoClient) return;

        await this.props.vertoClient.hangup();
        this._stopDurationTimer();
        this.state.callDuration = 0;
    }

    onToggleMute() {
        if (this.props.vertoClient) {
            this.state.muted = this.props.vertoClient.toggleMute();
        }
    }

    _startDurationTimer() {
        this.state.callDuration = 0;
        this._stopDurationTimer();
        this.durationInterval = setInterval(() => {
            this.state.callDuration++;
        }, 1000);
    }

    _stopDurationTimer() {
        if (this.durationInterval) {
            clearInterval(this.durationInterval);
            this.durationInterval = null;
        }
    }

    formatDuration(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    getStateText() {
        switch (this.props.state) {
            case "disconnected": return "Disconnected";
            case "connecting": return "Connecting...";
            case "reconnecting": return "Reconnecting...";
            case "registered": return "Ready";
            case "error": return "Error";
            default: return this.props.state;
        }
    }

    getCallStateText() {
        switch (this.props.callState) {
            case "idle": return "";
            case "calling": return "Calling...";
            case "ringing": return "Ringing...";
            case "active": return this.formatDuration(this.state.callDuration);
            case "incoming": return "Incoming call";
            default: return this.props.callState;
        }
    }
}


export class PhoneSystray extends Component {
    static template = "connect_freeswitch.PhoneSystray";
    static props = {
        bus: Object,
        displayMode: String,
    };

    setup() {
        this.state = useState({
            vertoState: "disconnected",
            callState: "idle",
        });

        this._onStateChanged = ({ detail }) => {
            this.state.vertoState = detail.vertoState;
        };
        this._onCallStateChanged = ({ detail }) => {
            this.state.callState = detail.callState;
        };

        onMounted(() => {
            this.props.bus.addEventListener("phoneStateChanged", this._onStateChanged);
            this.props.bus.addEventListener("phoneCallStateChanged", this._onCallStateChanged);
        });

        onWillUnmount(() => {
            this.props.bus.removeEventListener("phoneStateChanged", this._onStateChanged);
            this.props.bus.removeEventListener("phoneCallStateChanged", this._onCallStateChanged);
            this.props.bus.trigger("phoneNavigated");
        });
    }

    toggleDialpad() {
        this.props.bus.trigger("phoneToggle");
    }

    getIconClass() {
        switch (this.state.vertoState) {
            case "registered":
                return this.state.callState !== "idle" ? "text-success" : "";
            case "connecting":
            case "reconnecting":
                return "text-warning";
            case "error":
                return "text-danger";
            default:
                return "text-muted";
        }
    }
}
