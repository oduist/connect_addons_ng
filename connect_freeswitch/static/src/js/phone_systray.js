/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";


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
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            number: "",
            muted: false,
            callDuration: 0,
            recordingState: "off",
            recordingBusy: false,
            recordingError: "",
            recordingPath: "",
        });

        this.numberInput = useRef("numberInput");
        this.durationInterval = null;
        this.lastRecordingCallId = null;

        onMounted(() => {
            this.numberInput.el?.focus();
            this._syncRecordingForProps(this.props);
        });

        onWillUpdateProps((nextProps) => {
            this._syncRecordingForProps(nextProps);
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

    getRecordingCallId(vertoClient = this.props.vertoClient) {
        if (!vertoClient || typeof vertoClient.getCallId !== "function") {
            return "";
        }
        return vertoClient.getCallId();
    }

    _recordingPayload(vertoClient = this.props.vertoClient) {
        return {
            provider: "freeswitch",
            call_id: this.getRecordingCallId(vertoClient),
            recording_path: this.state.recordingPath,
        };
    }

    _applyRecordingResult(result) {
        if (!result) return;
        this.state.recordingState = result.state || "off";
        this.state.recordingPath = result.recording_path || "";
        this.state.recordingError = result.error || "";
        this.state.recordingBusy = ["starting", "stopping"].includes(this.state.recordingState);
    }

    _syncRecordingForProps(props) {
        const callId = this.getRecordingCallId(props.vertoClient);
        if (props.callState !== "active") {
            this.lastRecordingCallId = null;
            this.state.recordingState = "off";
            this.state.recordingBusy = false;
            this.state.recordingError = "";
            this.state.recordingPath = "";
            return;
        }
        if (callId && callId !== this.lastRecordingCallId) {
            this.lastRecordingCallId = callId;
            this.syncRecordingState(props.vertoClient);
        }
    }

    async syncRecordingState(vertoClient = this.props.vertoClient) {
        const callId = this.getRecordingCallId(vertoClient);
        if (!callId) {
            this.state.recordingState = "off";
            this.state.recordingError = _t("Call UUID unavailable");
            return;
        }
        try {
            const result = await this.orm.call(
                "connect.channel",
                "get_softphone_recording_state",
                [this._recordingPayload(vertoClient)]
            );
            this._applyRecordingResult(result);
        } catch (error) {
            console.warn("Recording state sync failed:", error);
            this.state.recordingState = "error";
            this.state.recordingError = error.message || String(error);
        }
    }

    isRecordingOn() {
        return this.state.recordingState === "on" || this.state.recordingState === "starting";
    }

    isRecordingButtonDisabled() {
        return this.state.recordingBusy || !this.getRecordingCallId();
    }

    getRecordingTitle() {
        if (!this.getRecordingCallId()) {
            return _t("Recording unavailable");
        }
        if (this.state.recordingBusy) {
            return this.state.recordingState === "starting" ? _t("Starting recording") : _t("Stopping recording");
        }
        if (this.state.recordingState === "error") {
            return this.state.recordingError || _t("Recording error");
        }
        return this.isRecordingOn() ? _t("Stop Recording") : _t("Start Recording");
    }

    getRecordingIconClass() {
        if (this.state.recordingState === "error") {
            return "fa fa-exclamation-triangle";
        }
        if (this.state.recordingBusy) {
            return "fa fa-spinner fa-spin";
        }
        return this.isRecordingOn() ? "fa fa-stop-circle" : "fa fa-circle";
    }

    async onToggleRecording() {
        if (this.isRecordingButtonDisabled()) return;
        const action = this.isRecordingOn() ? "stop_softphone_recording" : "start_softphone_recording";
        this.state.recordingBusy = true;
        this.state.recordingState = this.isRecordingOn() ? "stopping" : "starting";
        try {
            const result = await this.orm.call(
                "connect.channel",
                action,
                [this._recordingPayload()]
            );
            this._applyRecordingResult(result);
        } catch (error) {
            this.state.recordingState = "error";
            this.state.recordingError = error.message || String(error);
            this.state.recordingBusy = false;
            this.notification.add(this.state.recordingError, {
                title: _t("Recording"),
                type: "danger",
                sticky: false,
            });
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
            case "disconnected": return _t("Disconnected");
            case "connecting": return _t("Connecting...");
            case "reconnecting": return _t("Reconnecting...");
            case "registered": return _t("Ready");
            case "error": return _t("Error");
            default: return this.props.state;
        }
    }

    getCallStateText() {
        switch (this.props.callState) {
            case "idle": return "";
            case "calling": return _t("Calling...");
            case "ringing": return _t("Ringing...");
            case "active": return this.formatDuration(this.state.callDuration);
            case "incoming": return _t("Incoming call");
            default: return this.props.callState;
        }
    }

    get displayCallerName() {
        return this.props.callerName || _t("Unknown");
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
