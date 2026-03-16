/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { VertoClient } from "./verto_client";


class PhoneDialpad extends Component {
    static template = "connect_freeswitch.PhoneDialpad";
    static props = {
        close: Function,
        vertoClient: { type: Object, optional: true },
        state: String,
        callState: String,
    };

    setup() {
        this.state = useState({
            number: "",
            muted: false,
            callDuration: 0,
            incomingCallerName: "",
            incomingCallerNumber: "",
        });

        this.durationInterval = null;
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
    static components = { PhoneDialpad };
    static props = {};

    setup() {
        this.orm = useService("orm");

        this.state = useState({
            enabled: false,
            showDialpad: false,
            vertoState: "disconnected",
            callState: "idle",
            config: null,
        });

        this.vertoClient = null;

        onWillStart(async () => {
            await this.loadConfig();
        });

        onMounted(() => {
            if (this.state.enabled) {
                this.connect();
            }
        });

        onWillUnmount(() => {
            this.disconnect();
        });
    }

    async loadConfig() {
        try {
            const config = await this.orm.call("connect.settings", "get_webrtc_config", []);

            if (config.enabled) {
                this.state.enabled = true;
                this.state.config = config;
            }
        } catch (error) {
            console.error("[Phone] Failed to load config:", error);
        }
    }

    async connect() {
        if (!this.state.config || this.vertoClient) return;

        this.vertoClient = new VertoClient({
            socketUrl: this.state.config.socketUrl,
            login: this.state.config.login,
            password: this.state.config.password,
            callerName: this.state.config.callerName,
            callerNumber: this.state.config.callerNumber,
            onStateChange: (state) => {
                this.state.vertoState = state;
            },
            onCallStateChange: (state) => {
                this.state.callState = state;
                if (state === "incoming") {
                    this.state.showDialpad = true;
                }
            },
            onError: (error) => {
                console.error("[Phone] Verto error:", error);
            }
        });

        try {
            await this.vertoClient.connect();
        } catch (error) {
            console.error("[Phone] Connection failed:", error);
        }
    }

    disconnect() {
        if (this.vertoClient) {
            this.vertoClient.disconnect();
            this.vertoClient = null;
        }
    }

    toggleDialpad() {
        this.state.showDialpad = !this.state.showDialpad;

        if (this.state.showDialpad && !this.vertoClient && this.state.enabled) {
            this.connect();
        }
    }

    closeDialpad() {
        this.state.showDialpad = false;
    }

    getIconClass() {
        if (!this.state.enabled) return "text-muted";

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

registry.category("systray").add("connect_freeswitch.PhoneSystray", {
    Component: PhoneSystray,
}, { sequence: 50 });
