/** @odoo-module **/
// VoiceML phone bootstrap: a service that asks the backend for the current
// user's softphone config and, when enabled, mounts the softphone into the
// systray and registers the main phone component.
import { registry } from "@web/core/registry";
import { VoiceMLPhoneSysTray } from "@connect_voiceml/components/phone/tray/tray";

const serviceRegistry = registry.category("services");
const sysTrayRegistry = registry.category("systray");

export const voiceMLPhoneService = {
    dependencies: ["orm"],
    async start(env, { orm }) {
        let cfg;
        try {
            cfg = await orm.call("connect.user", "get_phone_config", []);
        } catch (err) {
            console.warn("[Connect VoiceML] config error", err);
            return;
        }
        if (!cfg || !cfg.ok) {
            return;
        }
        sysTrayRegistry.add("connectVoiceMLPhoneSysTray", {
            Component: VoiceMLPhoneSysTray,
        });
    },
};

serviceRegistry.add("ConnectVoiceMLPhoneService", voiceMLPhoneService);
