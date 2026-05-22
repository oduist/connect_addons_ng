/** @odoo-module **/

import { registry } from "@web/core/registry";
import { EventBus } from "@odoo/owl";
import { PhoneSystray } from "./phone_systray";
import { PhonePanel } from "./phone_panel";
import { VertoClient } from "./verto_client";


export const phoneService = {
    dependencies: ["orm", "bus_service"],

    async start(env, { orm, bus_service }) {
        const pathname = document.location.pathname;
        if (!pathname.includes("/odoo")) {
            return { enabled: false };
        }

        let config;
        try {
            config = await orm.call("connect.settings", "get_webrtc_config", []);
        } catch (error) {
            console.error("[Phone] Failed to load config:", error);
            return { enabled: false };
        }

        if (!config.enabled) {
            return { enabled: false };
        }

        const bus = new EventBus();
        const displayMode = config.displayMode || "dropdown";
        let vertoClient = null;

        // Ringtone state
        let ringAudioCtx = null;
        let ringOscillator = null;
        let ringGain = null;
        let ringing = false;
        let ringTimeout = null;

        function startRingtone() {
            stopRingtone();
            try {
                ringAudioCtx = new AudioContext();
                ringGain = ringAudioCtx.createGain();
                ringGain.connect(ringAudioCtx.destination);
                ringGain.gain.value = 0;

                ringOscillator = ringAudioCtx.createOscillator();
                ringOscillator.type = "sine";
                ringOscillator.frequency.value = 440;
                ringOscillator.connect(ringGain);
                ringOscillator.start();

                ringing = true;
                const ringCycle = () => {
                    if (!ringing) return;
                    ringGain.gain.value = 0.3;
                    ringTimeout = setTimeout(() => {
                        if (!ringing) return;
                        ringGain.gain.value = 0;
                        ringTimeout = setTimeout(ringCycle, 2000);
                    }, 1000);
                };
                ringCycle();
            } catch (error) {
                console.error("[Phone] Failed to start ringtone:", error);
            }
        }

        function stopRingtone() {
            ringing = false;
            clearTimeout(ringTimeout);
            if (ringOscillator) {
                try { ringOscillator.stop(); } catch {}
                ringOscillator = null;
            }
            if (ringAudioCtx) {
                ringAudioCtx.close();
                ringAudioCtx = null;
            }
            ringGain = null;
        }

        function connect() {
            if (vertoClient) return;

            vertoClient = new VertoClient({
                socketUrl: config.socketUrl,
                domain: config.domain,
                login: config.login,
                password: config.password,
                callerName: config.callerName,
                callerNumber: config.callerNumber,
                iceServers: config.iceServers,
                onStateChange: (state) => {
                    bus.trigger("phoneStateChanged", { vertoState: state });
                },
                onCallStateChange: (state, data) => {
                    if (state === "incoming") {
                        bus.trigger("phoneToggle", { show: true });
                        startRingtone();
                    } else {
                        stopRingtone();
                    }
                    bus.trigger("phoneCallStateChanged", {
                        callState: state,
                        callerName: data.callerName || "",
                        callerNumber: data.callerNumber || "",
                    });
                },
                onError: (error) => {
                    console.error("[Phone] Verto error:", error);
                },
            });

            vertoClient.connect().catch((error) => {
                console.error("[Phone] Connection failed:", error);
            });
        }

        function disconnect() {
            if (vertoClient) {
                vertoClient.disconnect();
                vertoClient = null;
            }
            stopRingtone();
        }

        const service = {
            enabled: true,
            bus,
            config,
            displayMode,
            get vertoClient() { return vertoClient; },
            connect,
            disconnect,
        };

        registry.category("systray").add("connect_freeswitch.PhoneSystray", {
            Component: PhoneSystray,
            props: { bus, displayMode, getVertoClient: () => vertoClient },
        }, { sequence: 50 });

        registry.category("main_components").add("connect_freeswitch.PhonePanel", {
            Component: PhonePanel,
            props: { bus, displayMode, getVertoClient: () => vertoClient, connect },
        });

        // Subscribe to Odoo bus channel for server-pushed events (e.g. parking).
        bus_service.addChannel("connect_actions");
        bus_service.subscribe("parking_state_changed", (payload) => {
            bus.trigger("parkingStateChanged", payload);
        });

        // Connect immediately
        connect();

        return service;
    },
};

registry.category("services").add("connect_freeswitch.phone", phoneService);
