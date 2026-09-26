/** @odoo-module **/
// VoiceML softphone helpers.

export function normalizeNumber(number) {
    if (!number) return number;
    return String(number).replace(/[\s()\-+]/g, '').replace(/^0+/, '');
}

// Single log prefix so admins can filter the browser console by
// "[Connect VoiceML]" when a web phone fails to register.
export function vlog(...args) {
    console.log("[Connect VoiceML]", ...args);
}
