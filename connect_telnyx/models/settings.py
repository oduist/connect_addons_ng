# -*- coding: utf-8 -*-
import json
import logging
import re
from urllib.parse import urljoin

import phonenumbers
import requests
from babel.core import Locale, UnknownLocaleError

from odoo import fields, models, api, release
from odoo.exceptions import AccessError, ValidationError
from telnyx import Telnyx

from odoo.addons.connect.models.license import ODUIST_MODULES
from odoo.addons.connect.models.settings import debug

from .texml_response import pretty_xml

ODUIST_MODULES.append('connect_telnyx')


logger = logging.getLogger(__name__)

MAX_EXTEN_LEN = 4

TELNYX_PROTECTED_FIELDS = [
    "display_telnyx_api_key",
]

TELNYX_API_BASE = "https://api.telnyx.com/v2/"
TELNYX_SYSTEM_VOICE_DEFAULT = "Polly.Joanna"
# Instructions of the Telnyx conversation insight that produces the AI call
# summary written back into the ledger.
DEFAULT_AI_SUMMARY_INSTRUCTIONS = (
    "Summarize this conversation in 2-3 factual sentences. "
    "Include the request, outcome, and follow-up actions."
)
TELNYX_BASIC_VOICES = [
    {
        "id": "man", "name": "Man", "provider": "basic",
        "language": "en-US", "gender": "Male",
    },
    {
        "id": "woman", "name": "Woman", "provider": "basic",
        "language": "en-US", "gender": "Female",
    },
    {
        "id": "alice", "name": "Alice", "provider": "basic",
        "language": "en-US", "gender": "Female",
    },
    {
        "id": TELNYX_SYSTEM_VOICE_DEFAULT, "name": "Joanna",
        "provider": "aws", "language": "en-US", "gender": "Female",
    },
]
# Speed is not a shared Telnyx TTS parameter: every provider that supports
# it names the key inside its own object and the others reject an unknown
# field, so a sample is generated with the speed only where it exists.
TELNYX_VOICE_SPEED_PARAMS = {
    "telnyx": ("telnyx", "voice_speed"),
    "rime": ("rime", "voice_speed"),
    "minimax": ("minimax", "speed"),
}
TELNYX_VOICE_SAMPLE_TEXT = (
    "Hello! This is how the selected Telnyx voice sounds."
)
# The sample is synthesized while the administrator waits for the form, so
# it stays short enough to answer inside the normal API timeout.
MAX_VOICE_SAMPLE_CHARS = 200
TELNYX_PROVIDER_LABELS = {
    "aws": "Amazon Web Services",
    "azure": "Microsoft Azure",
    "basic": "Telnyx Basic",
    "elevenlabs": "ElevenLabs",
    "fishaudio": "Fish Audio",
    "humain": "Humain",
    "inworld": "Inworld",
    "minimax": "MiniMax",
    "resemble": "Resemble AI",
    "rime": "Rime",
    "telnyx": "Telnyx",
    "xai": "xAI",
}


def format_connect_response(text):
    if not isinstance(text, str):
        text = str(text)
    symbol_pattern = re.compile(r"(\x08.)|\x08")
    text = symbol_pattern.sub("", text)
    color_pattern = re.compile(r"\x1b\[[\d;]+m")
    text = color_pattern.sub("", text)
    return text


def strip_number(number):
    """Strip number formatting"""
    if not isinstance(number, str):
        return number
    pattern = r"[\s\(\)\-\+]"
    return re.sub(pattern, "", number).lstrip("0")


class Settings(models.Model):
    _inherit = "connect.settings"

    # Never grant this to connect.group_webhook: the webhook user is the
    # identity of all public webhook controllers, and get_param() returns
    # groups-restricted fields to group members (ADR-025).
    telnyx_api_key = fields.Char(groups="base.group_erp_manager")
    display_telnyx_api_key = fields.Char(string="Telnyx API Key")
    # The Ed25519 public key from Mission Control used to verify webhook
    # signatures. Not a secret.
    telnyx_public_key = fields.Char(string="Telnyx Public Key")
    # TeXML Account SID (the Telnyx account/user ID from Mission Control).
    # Required for the TeXML REST originate API; Telnyx has no discovery
    # endpoint for it (ADR-032).
    telnyx_account_sid = fields.Char(string="Telnyx Account SID")
    telnyx_messaging_profile_id = fields.Char(readonly=True)
    telnyx_outbound_voice_profile_id = fields.Char(readonly=True)
    telnyx_outbound_destinations = fields.Char(
        string='Outbound Destinations',
        help="Comma separated ISO country codes Telnyx is allowed to place "
             "calls to, for example PL, DE, US. Saved straight onto the "
             "outbound voice profile: a country missing here has its calls "
             "rejected by Telnyx before Odoo sees them. Leave empty to "
             "allow every destination.")
    telnyx_ai_summary_insight_id = fields.Char(readonly=True)
    telnyx_ai_summary_group_id = fields.Char(readonly=True)
    telnyx_ai_summary_instructions = fields.Text(
        string="AI Summary Instructions",
        required=True,
        default=DEFAULT_AI_SUMMARY_INSTRUCTIONS,
        help="Prompt of the Telnyx conversation insight that summarizes AI "
             "assistant calls. Saving a new text drops the current insight in "
             "Telnyx and recreates it, so past summaries keep the wording "
             "they were generated with.",
    )
    telnyx_balance = fields.Char(readonly=True)
    telnyx_auto_sync = fields.Boolean(default=True)
    telnyx_verify_requests = fields.Boolean(
        default=True, string="Verify Telnyx Requests"
    )
    telnyx_fetch_call_prices = fields.Boolean(
        default=False,
        string="Fetch Call Prices",
        help="Enable fetching call costs from Telnyx detail records after call completion."
    )
    telnyx_system_voice_language = fields.Selection(
        selection="_get_telnyx_voice_language_selection",
        default="en-US",
        required=True,
        string="System Voice Language",
        help="Language used to filter the Telnyx system voice catalog.",
    )
    telnyx_system_voice_provider = fields.Selection(
        selection="_get_telnyx_voice_provider_selection",
        default="aws",
        required=True,
        string="System Voice Provider",
        help="Provider used to filter the Telnyx system voice catalog.",
    )
    telnyx_system_voice = fields.Char(
        default=TELNYX_SYSTEM_VOICE_DEFAULT,
        required=True,
        string="System Voice",
        help="Voice added to every Telnyx TeXML Say without its own voice. "
             "Refresh the catalog after adding voices in Telnyx.",
    )
    telnyx_tts_voices = fields.Text(readonly=True)

    @api.model
    def _get_cached_telnyx_voices(self, include_basic=True):
        """Return a normalized, de-duplicated catalog without a live call.

        The basic TeXML voices belong to the `<Say>` contract only; an AI
        assistant cannot speak with them, so its selector asks for the
        catalog without them.
        """
        settings = self.sudo().search([], limit=1)
        try:
            voices = json.loads(settings.telnyx_tts_voices or "[]")
        except (TypeError, ValueError):
            voices = []
        if not isinstance(voices, list):
            voices = []
        catalog = {}
        basic = TELNYX_BASIC_VOICES if include_basic else []
        for voice in basic + voices:
            if not isinstance(voice, dict):
                continue
            voice_id = voice.get("id") or voice.get("voice_id")
            if not voice_id:
                continue
            catalog[voice_id] = {
                "id": voice_id,
                "name": voice.get("name") or voice_id,
                "provider": (voice.get("provider") or "").lower(),
                "language": voice.get("language") or "",
                "gender": voice.get("gender") or "",
            }
        return list(catalog.values())

    @api.model
    def _get_telnyx_voice_language_selection(self):
        languages = {
            voice["language"] for voice in self._get_cached_telnyx_voices()
            if voice["language"]
        }
        settings = self.sudo().search([], limit=1)
        current = settings.telnyx_system_voice_language if settings else False
        if current:
            languages.add(current)
        return sorted(
            ((language, self._get_telnyx_language_label(language))
             for language in languages),
            key=lambda item: item[1],
        )

    @api.model
    def _get_telnyx_voice_provider_selection(self):
        providers = {
            voice["provider"] for voice in self._get_cached_telnyx_voices()
            if voice["provider"]
        }
        settings = self.sudo().search([], limit=1)
        current = settings.telnyx_system_voice_provider if settings else False
        if current:
            providers.add(current)
        return sorted(
            ((provider, self._get_telnyx_provider_label(provider))
             for provider in providers),
            key=lambda item: item[1],
        )

    @api.model
    def _get_telnyx_language_label(self, language):
        try:
            name = Locale.parse(language, sep="-").get_display_name("en")
        except (UnknownLocaleError, ValueError):
            name = language
        if name == language:
            return language
        return "{} ({})".format(name.title(), language)

    @api.model
    def _get_telnyx_provider_label(self, provider):
        return TELNYX_PROVIDER_LABELS.get(
            provider, provider.replace("_", " ").title())

    @api.model
    def _format_telnyx_voice_option(self, voice):
        details = [voice.get("gender"), voice["id"]]
        return {
            "value": voice["id"],
            "label": voice.get("name") or voice["id"],
            "details": " - ".join(value for value in details if value),
        }

    @api.model
    def telnyx_get_voice_options(self, language, provider, search="",
                                 limit=80, include_basic=True):
        """Return a small readable subset for the voice autocomplete.

        Telnyx reports no language for some account-scoped voices, such as
        a cloned one. Those match every filter instead of disappearing from
        the catalog, which is the only way they stay selectable at all.
        """
        if not language or not provider:
            return []
        search = (search or "").strip().lower()
        limit = min(max(int(limit or 80), 1), 100)
        matches = []
        for voice in self._get_cached_telnyx_voices(
                include_basic=include_basic):
            if voice["language"] and voice["language"] != language:
                continue
            if voice["provider"] and voice["provider"] != provider:
                continue
            haystack = "{} {} {}".format(
                voice.get("name", ""), voice["id"], voice.get("gender", "")
            ).lower()
            if search and search not in haystack:
                continue
            matches.append(voice)
        matches.sort(key=lambda voice: (
            (voice.get("name") or "").lower(), voice["id"].lower()))
        return [
            self._format_telnyx_voice_option(voice)
            for voice in matches[:limit]
        ]

    @api.model
    def telnyx_get_voice_label(self, voice_id):
        for voice in self._get_cached_telnyx_voices():
            if voice["id"] == voice_id:
                return self._format_telnyx_voice_option(voice)
        return {
            "value": voice_id or "",
            "label": voice_id or "",
            "details": voice_id or "",
        }

    @api.model
    def _telnyx_voice_provider(self, voice_id):
        """Provider key of a catalog voice, or the one implied by its id."""
        for voice in self._get_cached_telnyx_voices():
            if voice["id"] == voice_id:
                if voice["provider"]:
                    return voice["provider"]
                break
        prefix = (voice_id or "").split(".")[0].lower()
        return prefix if prefix in TELNYX_PROVIDER_LABELS else ""

    @api.model
    def _telnyx_voice_sample(self, voice, text=None, voice_speed=1.0):
        """Return base64 audio of a short sample spoken by ``voice``.

        Telnyx validates the voice, the speed and the provider combination
        on this endpoint exactly as it does when an AI assistant synthesizes
        its greeting, so an unusable pair is reported while the form is open
        instead of ending every call with a greeting error.
        """
        if not voice:
            raise ValidationError("Select a voice first.")
        payload = {
            "voice": voice,
            "text": (text or TELNYX_VOICE_SAMPLE_TEXT)[
                :MAX_VOICE_SAMPLE_CHARS],
            "output_type": "base64_output",
        }
        speed_param = TELNYX_VOICE_SPEED_PARAMS.get(
            self._telnyx_voice_provider(voice))
        if speed_param and voice_speed:
            payload[speed_param[0]] = {speed_param[1]: voice_speed}
        response = self.telnyx_api_request(
            "POST", "text-to-speech/speech", payload=payload, timeout=30)
        audio = (response or {}).get("base64_audio")
        if not audio:
            raise ValidationError(
                "Telnyx returned no audio for voice {}.".format(voice))
        return {"audio": audio, "voice": voice}

    @api.model
    def telnyx_preview_voice(self, voice, voice_speed=1.0, text=None):
        """Play a sample of the system voice from the settings form.

        The model ACL does not protect a method call: `call_kw` only refuses
        private names, so any authenticated session could otherwise spend
        Telnyx text-to-speech credit here. The group is therefore checked in
        the method itself, and only server-side `sudo()` code is exempt.
        """
        if not self.env.su and not self.env.user.has_group(
                "connect.group_admin"):
            raise AccessError(
                "Only Connect administrators can preview a voice.")
        return self._telnyx_voice_sample(voice, text, voice_speed)

    @api.onchange(
        "telnyx_system_voice_language", "telnyx_system_voice_provider")
    def _onchange_telnyx_system_voice_filters(self):
        if not self.telnyx_system_voice:
            return
        voice = next((
            item for item in self._get_cached_telnyx_voices()
            if item["id"] == self.telnyx_system_voice
        ), None)
        if (not voice
                or (voice["language"]
                    and voice["language"] != self.telnyx_system_voice_language)
                or (voice["provider"]
                    and voice["provider"]
                    != self.telnyx_system_voice_provider)):
            self.telnyx_system_voice = False

    @api.model
    def _sync_telnyx_tts_voices(self):
        """Cache the current account catalog used by System Voice."""
        response = self.telnyx_api_request("GET", "text-to-speech/voices")
        voices = response.get("voices") or response.get("data") or []
        if not isinstance(voices, list):
            voices = []
        normalized = []
        for voice in voices:
            if not isinstance(voice, dict):
                continue
            voice_id = voice.get("id") or voice.get("voice_id")
            if not voice_id:
                continue
            normalized.append({
                "id": voice_id,
                "name": voice.get("name"),
                "provider": (voice.get("provider") or "").lower(),
                "language": voice.get("language"),
                "gender": voice.get("gender"),
            })
        self.sudo().set_param(
            "telnyx_tts_voices", json.dumps(normalized, sort_keys=True))
        return normalized

    def telnyx_sync_tts_voices(self):
        self._sync_telnyx_tts_voices()
        action = self.env.ref("connect_telnyx.telnyx_settings_action")
        cache_key = fields.Datetime.now().strftime("%Y%m%d%H%M%S%f")
        return {
            "type": "ir.actions.act_url",
            "url": "/web?telnyx_voices={}#action={}".format(
                cache_key, action.id),
            "target": "self",
        }

    @api.model
    def telnyx_apply_system_voice(self, content):
        from .texml_response import apply_say_voice

        voice = self.sudo().get_param(
            "telnyx_system_voice", TELNYX_SYSTEM_VOICE_DEFAULT)
        return apply_say_voice(content, voice)

    @api.model
    def get_telnyx_client(self):
        # connect.settings is admin-only; credentials are read with sudo()
        # below, so no caller-level model access check is needed here.
        api_key = self.sudo().get_param("telnyx_api_key")
        if not api_key:
            raise ValidationError("Set Telnyx API key first!")
        public_key = self.sudo().get_param("telnyx_public_key")
        return Telnyx(api_key=api_key, public_key=public_key or None)

    @api.model
    def telnyx_api_request(self, method, path, payload=None, params=None,
                           timeout=20):
        """Call Telnyx v2 endpoints not consistently exposed by SDK releases.

        The account key never appears in error messages or debug output.  The
        returned value is the decoded JSON body; callers normalize the few
        endpoints that wrap their result in ``data`` themselves.
        """
        api_key = self.sudo().get_param("telnyx_api_key")
        if not api_key:
            raise ValidationError("Set Telnyx API key first!")
        url = urljoin(TELNYX_API_BASE, path.lstrip("/"))
        try:
            response = requests.request(
                method.upper(), url,
                headers={
                    "Authorization": "Bearer {}".format(api_key),
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=payload,
                params=params,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise ValidationError(
                "Telnyx API request failed: {}".format(exc)
            ) from exc
        if response.status_code >= 400:
            try:
                body = response.json()
                detail = (
                    body.get("errors") or body.get("detail")
                    or body.get("message") or body.get("error")
                )
            except ValueError:
                detail = None
            raise ValidationError(
                "Telnyx API returned HTTP {}{}".format(
                    response.status_code,
                    ": {}".format(detail) if detail else "",
                )
            )
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise ValidationError(
                "Telnyx API returned an invalid JSON response."
            ) from exc

    def telnyx_sync(self):
        if not self.sudo().get_param("telnyx_api_key"):
            raise ValidationError("You must set the Telnyx API key!")
        api_url_check = self.check_api_url()
        if api_url_check:
            raise ValidationError(api_url_check)
        try:
            try:
                self._ensure_telnyx_account_sid()
            except Exception as e:
                # Click-to-call needs it, the rest of the sync does not.
                logger.warning('Cannot resolve the Telnyx account SID: %s', e)
            self._ensure_telnyx_outbound_voice_profile()
            self._ensure_telnyx_messaging_profile()
            try:
                self._sync_telnyx_tts_voices()
            except Exception as e:
                logger.warning(
                    "Cannot refresh the Telnyx TTS voice catalog: %s", e)
            # Checked after the numbers are known, at the end of the sync.
            self.env["connect.telnyx.texml"].sync()
            self.env["connect.telnyx.ai_assistant"].sync()
            self.env["connect.telnyx.domain"].sync()
            self.env["connect.telnyx.number"].sync()
            self.env["connect.telnyx.outgoing_callerid"].sync()
            # WhatsApp/RCS onboarding is optional on the Telnyx account —
            # keep their sync failures non-fatal (ADR-033).
            for model, title in [
                ("connect.telnyx.whatsapp_sender", "WhatsApp Senders"),
                ("connect.telnyx.whatsapp_template", "WhatsApp Templates"),
                ("connect.telnyx.rcs_agent", "RCS Agents"),
            ]:
                try:
                    self.env[model].sync()
                except Exception as e:
                    logger.warning('%s sync failed: %s', title, e)
                    self.connect_notify(
                        "{} sync failed: {}".format(title, e),
                        title="Sync Warning", warning=True, sticky=True)
            self._check_telnyx_outbound_destinations()
            self.connect_notify(
                "Telnyx account synced successfully", title="Sync Complete")
        except ValidationError:
            raise
        except Exception as e:
            status = getattr(e, 'status_code', None)
            text = str(e)
            if status == 401 or 'Authentication failed' in text or '401' in text:
                raise ValidationError(
                    'Error authenticating requests to the Telnyx API! '
                    'Check your API key!'
                )
            if (status == 403 or '10006' in text
                    or 'not authorized' in text.lower()):
                # Telnyx API keys are account-wide (no per-resource scopes),
                # so a 403 here is an account-level restriction — typically
                # the Voice / TeXML product is not enabled or the account is
                # not verified — not a key permission the user can toggle.
                raise ValidationError(
                    'Telnyx denied access to a required resource (HTTP 403). '
                    'Your Telnyx account is not authorized to use this '
                    'product — most often Voice / TeXML applications. Telnyx '
                    'API keys grant full account access and cannot be scoped '
                    'per resource, so this is an account-level restriction, '
                    'not an API key permission. Verify your account and '
                    'enable Voice in the Telnyx Mission Control portal '
                    '(https://portal.telnyx.com), then run Sync again.'
                )
            raise

    def _ensure_telnyx_account_sid(self):
        """Store the TeXML account SID, which the API reports as the
        organization id. It is required by every TeXML call and there is
        no reason to make the administrator copy it by hand."""
        account_sid = self.sudo().get_param('telnyx_account_sid')
        if account_sid:
            return account_sid
        data = (self.telnyx_api_request('GET', 'whoami') or {}).get('data') or {}
        account_sid = data.get('organization_id') or data.get('user_id')
        if account_sid:
            self.sudo().set_param('telnyx_account_sid', account_sid)
            debug(self, 'Telnyx account SID set to {}.'.format(account_sid))
        return account_sid

    def _ensure_telnyx_outbound_voice_profile(self):
        """Return the outbound voice profile every connection must carry.

        Telnyx refuses an outbound call from a connection that has no
        outbound voice profile — the INVITE is rejected before any
        webhook is sent, so a SIP hardphone registers fine and then
        cannot dial out at all.
        """
        profile_id = self.sudo().get_param('telnyx_outbound_voice_profile_id')
        if profile_id:
            return profile_id
        try:
            response = self.telnyx_api_request(
                'GET', 'outbound_voice_profiles', params={'page[size]': 20})
            for profile in response.get('data') or []:
                if profile.get('enabled', True):
                    profile_id = profile.get('id')
                    break
            if not profile_id:
                payload = {'name': 'Odoo Connect',
                           'traffic_type': 'conversational',
                           'service_plan': 'global'}
                regions = self._telnyx_local_regions()
                if regions:
                    payload['whitelisted_destinations'] = regions
                created = self.telnyx_api_request(
                    'POST', 'outbound_voice_profiles', payload=payload)
                profile_id = (created.get('data') or {}).get('id')
        except Exception as e:
            # Attaching the profile is what enables outbound calls, but a
            # resource is still worth creating without it.
            logger.warning(
                'Cannot resolve the Telnyx outbound voice profile: %s', e)
            return False
        if profile_id:
            self.sudo().set_param(
                'telnyx_outbound_voice_profile_id', profile_id)
            debug(self, 'Telnyx outbound voice profile: {}'.format(profile_id))
            self._read_telnyx_outbound_destinations(profile_id)
        return profile_id

    def _read_telnyx_outbound_destinations(self, profile_id=None):
        """Mirror the profile whitelist into the settings field."""
        profile_id = profile_id or self.sudo().get_param(
            'telnyx_outbound_voice_profile_id')
        if not profile_id:
            return False
        try:
            profile = (self.telnyx_api_request(
                'GET', 'outbound_voice_profiles/{}'.format(profile_id)
            ).get('data') or {})
        except Exception as e:
            logger.warning('Cannot read the outbound voice profile: %s', e)
            return False
        destinations = ', '.join(profile.get('whitelisted_destinations') or [])
        self.sudo().set_param('telnyx_outbound_destinations', destinations)
        return destinations

    def _push_telnyx_outbound_destinations(self, destinations):
        """Save the destinations an administrator typed onto the profile."""
        profile_id = self.sudo().get_param('telnyx_outbound_voice_profile_id')
        if not profile_id:
            profile_id = self._ensure_telnyx_outbound_voice_profile()
        if not profile_id:
            raise ValidationError(
                'Synchronize the Telnyx account first: no outbound voice '
                'profile is known yet.')
        regions = [
            code.strip().upper()
            for code in (destinations or '').replace(';', ',').split(',')
            if code.strip()
        ]
        self.telnyx_api_request(
            'PATCH', 'outbound_voice_profiles/{}'.format(profile_id),
            payload={'whitelisted_destinations': regions})
        debug(self, 'Telnyx outbound destinations set to {}'.format(
            regions or 'all'))
        return regions

    def _refresh_telnyx_ai_summary_insight(self, instructions):
        """Rebuild the summary insight after an administrator edited it.

        Telnyx owns the insight text, so the stored insight is dropped and
        recreated with the new instructions; the insight group survives and
        keeps the webhook Odoo listens on.  Old conversations keep the
        summaries they were generated with.
        """
        settings = self.sudo()
        insight_id = settings.get_param('telnyx_ai_summary_insight_id')
        if not insight_id:
            # Nothing is published yet: the next account sync creates the
            # insight straight from the stored instructions.
            return False
        if not settings.get_param('telnyx_api_key'):
            return False
        try:
            settings.telnyx_api_request(
                'DELETE', 'ai/conversations/insights/{}'.format(insight_id))
        except Exception as e:
            # An orphaned insight is harmless; refusing the save is not.
            logger.warning(
                'Cannot delete the Telnyx summary insight %s: %s',
                insight_id, e)
        settings.set_param('telnyx_ai_summary_insight_id', False)
        self.env['connect.telnyx.ai_assistant']._ensure_summary_group(
            instructions=instructions)
        debug(self, 'Telnyx AI summary insight recreated')
        return settings.get_param('telnyx_ai_summary_insight_id')

    @api.model
    def _telnyx_local_regions(self):
        """Country codes Odoo is expected to place calls to.

        Derived from the numbers the account owns and the company
        country, so a fresh outbound voice profile is not created with
        Telnyx's US/CA default on, say, a Polish account.
        """
        regions = set()
        callerids = self.env['connect.telnyx.outgoing_callerid'].sudo().search([])
        numbers = self.env['connect.telnyx.number'].sudo().search([])
        for number in callerids.mapped('number') + numbers.mapped('phone_number'):
            if not number:
                continue
            try:
                parsed = phonenumbers.parse(number, None)
                region = phonenumbers.region_code_for_number(parsed)
            except Exception:
                region = None
            if region:
                regions.add(region)
        country = self.env.company.country_id.code
        if country:
            regions.add(country)
        return sorted(regions)

    def _check_telnyx_outbound_destinations(self):
        """Warn when the profile forbids the destinations we dial.

        Telnyx rejects an outbound call to a country missing from the
        profile's whitelist before any webhook is sent, which otherwise
        looks like a phone that simply cannot dial.
        """
        profile_id = self.sudo().get_param('telnyx_outbound_voice_profile_id')
        if not profile_id:
            return True
        try:
            profile = (self.telnyx_api_request(
                'GET', 'outbound_voice_profiles/{}'.format(profile_id)
            ).get('data') or {})
        except Exception as e:
            logger.warning('Cannot read the outbound voice profile: %s', e)
            return True
        allowed = profile.get('whitelisted_destinations')
        if not allowed:
            return True
        missing = [r for r in self._telnyx_local_regions() if r not in allowed]
        if not missing:
            return True
        message = (
            "The Telnyx outbound voice profile '{}' allows calls to {} only, "
            "so calls to {} are rejected by Telnyx. Add the missing "
            "destinations to the profile in Mission Control.".format(
                profile.get('name') or profile_id,
                ', '.join(allowed), ', '.join(missing)))
        logger.warning(message)
        self.connect_notify(
            message, title='Outbound Calls Blocked', warning=True, sticky=True)
        return False

    def _ensure_telnyx_messaging_profile(self):
        """Get or create the messaging profile used for Odoo messaging."""
        client = self.get_telnyx_client()
        api_url = self.sudo().get_param('api_url')
        webhook_url = urljoin(api_url, 'telnyx/webhook/message')
        profile_id = self.sudo().get_param('telnyx_messaging_profile_id')
        if profile_id:
            try:
                client.messaging_profiles.update(
                    profile_id, webhook_url=webhook_url,
                    whitelisted_destinations=['*'])
                return profile_id
            except Exception as e:
                if 'not found' not in str(e).lower() and '404' not in str(e):
                    raise
                debug(self, 'Messaging profile {} not found, recreating.'.format(
                    profile_id))
        for profile in client.messaging_profiles.list():
            if profile.name == 'Odoo Connect':
                self.sudo().set_param(
                    'telnyx_messaging_profile_id', profile.id)
                client.messaging_profiles.update(
                    profile.id, webhook_url=webhook_url,
                    whitelisted_destinations=['*'])
                return profile.id
        profile = client.messaging_profiles.create(
            name='Odoo Connect',
            webhook_url=webhook_url,
            whitelisted_destinations=['*'])
        self.sudo().set_param('telnyx_messaging_profile_id', profile.data.id)
        return profile.data.id

    def compute_telnyx_sip_uri(self, user):
        return "sip:{}".format(self.env.user.connect_user.telnyx_uri)

    def get_telnyx_external_call_route(self, number, callerId, status_url):
        call_duration_limit = int(self.sudo().get_param('call_duration_limit'))
        texml = """
        <Response>
            <Dial callerId="{}" timeLimit="{}"><Number statusCallback='{}' statusCallbackEvent='initiated answered completed'>{}</Number></Dial>
        </Response>
        """.format(
            callerId, call_duration_limit, status_url, number
        )
        return texml

    @api.model
    def originate_call(self, number, res_model=None, res_id=None, user=None, **kwargs):
        # Dispatch by the user's click-to-call provider; fall through to
        # other installed telephony modules when it is not Telnyx.
        if self._get_originate_provider(user) != 'telnyx':
            return super().originate_call(
                number, res_model=res_model, res_id=res_id, user=user, **kwargs)
        self.env["oduist.license"].check_license("connect", silent=False)
        account_sid = self._ensure_telnyx_account_sid()
        if not account_sid:
            raise ValidationError(
                "Set the Telnyx Account SID in Telnyx settings first!")
        number = strip_number(number)
        if len(number) > MAX_EXTEN_LEN:
            number = "+{}".format(number)
        client = self.get_telnyx_client()
        partner_id = False
        obj = self.env[res_model].browse(res_id) if res_model and res_id else False
        caller_name = ""
        if res_model == "res.partner" and obj:
            partner_id = res_id
            caller_name = obj.display_name
        elif obj and hasattr(obj, "partner_id") and obj.partner_id:
            partner_id = obj.partner_id.id
            caller_name = obj.partner_id.display_name
        elif obj and hasattr(obj, "partner") and obj.partner:
            partner_id = obj.partner.id
            caller_name = obj.partner.display_name
        if not user:
            user = self.env.user
        connect_user = user.connect_user
        if not connect_user:
            raise ValidationError("User does not have a PBX user defined!")
        first_flow = self.env['connect.telnyx.user_callflow'].search([
            ('user', '=', connect_user.id),
            ('callflow_type', 'in', ['client', 'sip'])
        ], order='prio', limit=1)
        if first_flow.callflow_type == 'sip':
            to = connect_user._telnyx_credential_uri(
                connect_user.telnyx_sip_username)
        else:
            # X- URI parameters surface as custom headers in the TelnyxRTC
            # notification, mirroring Twilio's client: URL parameters.
            # Telnyx rejects a header with an empty value ("The
            # 'custom_headers' parameter is invalid"), so only the
            # parameters that carry a value are sent.
            to = connect_user._telnyx_credential_uri(
                connect_user.telnyx_client_username,
                [
                    ('X-autoAnswer', 'yes'),
                    ('X-Partner', partner_id or ''),
                    ('X-CallerName', caller_name or ''),
                    ('X-From', (number or '').replace('+', '')),
                ])
        exten = self.env["connect.telnyx.exten"].search(
            [("number", "=", number)], limit=1
        )
        api_url = self.sudo().get_param("api_url")
        status_url = urljoin(api_url, "telnyx/webhook/callstatus")
        if exten:
            callerId = connect_user.telnyx_exten.number
            texml = exten.render()
        else:
            default_number = self.env[
                "connect.telnyx.outgoing_callerid"
            ].search([("is_default", "=", True)], limit=1)
            if connect_user.telnyx_outgoing_callerid:
                callerId = connect_user.telnyx_outgoing_callerid.number
            else:
                callerId = default_number.number
            texml = self.get_telnyx_external_call_route(
                number, callerId, status_url
            )
        record = connect_user.record_calls
        record_status_url = urljoin(api_url, "telnyx/webhook/recordingstatus")
        texml_url = urljoin(api_url, "telnyx/webhook/callaction")
        debug(self, 'Originate destination TeXML: {}'.format(texml))
        # Telnyx rejects a TeXML originate without ApplicationSid, even
        # when the dialplan is supplied inline.
        application = self.env['connect.telnyx.number'].get_number_app()
        if not application.sid:
            application.update_telnyx_app(client)
        call_kwargs = {
            'application_sid': application.sid,
            'url': texml_url,
            'url_method': 'POST',
            'texml': str(texml),
            'to': to,
            'from_': callerId,
            'status_callback': status_url,
            'status_callback_event': 'initiated answered completed',
        }
        if record:
            call_kwargs.update({
                'record': True,
                'recording_channels': 'dual',
                'recording_status_callback': record_status_url,
                'recording_status_callback_event': 'completed',
            })
        channel = client.texml.accounts.calls.calls(account_sid, **call_kwargs)
        channel_sid = getattr(channel, 'sid', None)
        if channel_sid:
            self.env["connect.channel"].sudo().create(
                {
                    "sid": channel_sid,
                    "technical_direction": "outbound-api",
                    "caller_user": user.id,
                    "caller_pbx_user": connect_user.id,
                    "partner": partner_id,
                    "called": number,
                    "caller": callerId,
                }
            )
        else:
            debug(
                self,
                'Telnyx originate response has no call SID; status callbacks '
                'will create the channel record.',
                level='warning',
            )

    @api.model
    def telnyx_check_call_failure(self, cause=None, sip_code=None):
        """Confirm whether a failed web-phone call was caused by an
        exhausted Telnyx balance (ADR-040).

        Telnyx rejects every origination on a billing-blocked account with
        404 UNALLOCATED_NUMBER ("Not found D19"), which is indistinguishable
        from a wrong number on the client. The web phone calls this method
        for such failures; it verifies the balance against the API and
        returns a trustworthy message. Only members of the Connect groups
        get an answer, and only admins see the actual amount.
        """
        has_admin_group = self.env.user.has_group('connect.group_admin')
        if not (has_admin_group or self.env.user.has_group('connect.group_user')):
            return {'balance_blocked': False}
        try:
            client = self.sudo().get_telnyx_client()
            data = client.balance.retrieve().data
            available = float(getattr(data, 'available_credit', 0) or 0)
            if available > 0:
                return {'balance_blocked': False}
            debug(self, 'Call failure (cause: {}, SIP {}) matches blocked '
                  'balance: {}'.format(cause, sip_code, available))
            if has_admin_group:
                message = (
                    'The Telnyx account balance is exhausted (available '
                    'credit: {} {}). Calls are blocked until the account '
                    'is topped up.'.format(
                        getattr(data, 'available_credit', available),
                        getattr(data, 'currency', 'USD')))
            else:
                message = (
                    'The telephony provider account is out of balance and '
                    'calls are blocked. Please contact your administrator.')
            return {'balance_blocked': True, 'message': message}
        except Exception as e:
            debug(self, 'telnyx_check_call_failure: {}'.format(e),
                  level='error')
            return {'balance_blocked': False}

    def get_telnyx_balance(self):
        """Fetch current Telnyx account balance"""
        try:
            client = self.get_telnyx_client()
            balance_item = client.balance.retrieve()
            data = balance_item.data
            balance = "{} {}".format(
                getattr(data, 'balance', '0.00'),
                getattr(data, 'currency', 'USD'),
            )
            self.set_param('telnyx_balance', balance)
            self.connect_notify(
                "Telnyx Balance: {}".format(balance), title="Balance Update"
            )
            return balance
        except Exception as e:
            error_msg = "Failed to fetch Telnyx balance: {}".format(str(e))
            self.connect_notify(error_msg, title="Balance Error", warning=True)
            raise ValidationError(error_msg)

    def write(self, vals):
        if self.env.context.get("skip_protected_fields"):
            return super(Settings, self).write(vals)
        res = super(Settings, self).write(vals)
        if 'telnyx_outbound_destinations' in vals:
            # Owned by the outbound voice profile in Telnyx, not by Odoo.
            self._push_telnyx_outbound_destinations(
                vals['telnyx_outbound_destinations'])
        if 'telnyx_ai_summary_instructions' in vals:
            # get_param is cached and the registry cache is only cleared at
            # the end of this write, so pass the new text explicitly.
            self._refresh_telnyx_ai_summary_insight(
                vals['telnyx_ai_summary_instructions'])
        changed_fields = {}
        for field_name in TELNYX_PROTECTED_FIELDS:
            if vals.get(field_name):
                changed_fields.update(
                    {
                        field_name.replace("display_", ""): vals.get(
                            field_name
                        ),
                        field_name: "*" * len(vals.get(field_name)),
                    }
                )
        if changed_fields:
            self.with_context(
                skip_protected_fields=True
            ).sudo().write(changed_fields)
        if release.version_info[0] >= 17:
            self.env.registry.clear_cache()
        else:
            self.clear_caches()
