# -*- coding: utf-8 -*-
"""Minimal TwiML builder for VoiceML.

VoiceML is Twilio-wire-compatible, so this module renders the same XML verbs
it would render for Twilio. Like connect_telnyx's texml_response.py (ADR-032),
we do not depend on the ``twilio`` package just to emit XML — this small
ElementTree builder covers the verbs connect_voiceml renders. Add verbs here
only as the module needs them; keep it a strict subset of Twilio's TwiML.
"""

from xml.etree import ElementTree as ET


def _xml_decl():
    return '<?xml version="1.0" encoding="UTF-8"?>'


class TwiMLResponse:
    """Accumulates a ``<Response>`` document and renders it to a string."""

    def __init__(self):
        self.root = ET.Element('Response')

    def verb(self, name, text=None, **attrs):
        el = ET.SubElement(self.root, name)
        for key, value in attrs.items():
            if value is not None:
                el.set(key, str(value))
        if text:
            el.text = str(text)
        return el

    def say(self, text, **attrs):
        return self.verb('Say', text, **attrs)

    def play(self, url, **attrs):
        return self.verb('Play', url, **attrs)

    def hangup(self, **attrs):
        return self.verb('Hangup', **attrs)

    def reject(self, reason=None):
        return self.verb('Reject', reason=reason)

    def pause(self, length=None):
        return self.verb('Pause', length=length)

    def redirect(self, url, method=None):
        return self.verb('Redirect', url, method=method)

    def gather(self, **attrs):
        return _GatherHelper(self, **attrs)

    def dial(self, **attrs):
        return _DialHelper(self, **attrs)

    def to_string(self):
        return _xml_decl() + ET.tostring(self.root, encoding='unicode')


class _GatherHelper:
    """Scoped builder so ``gather().say(...)`` nests under ``<Gather>``."""

    def __init__(self, response, **attrs):
        self.response = response
        self.el = ET.SubElement(response.root, 'Gather')
        for key, value in attrs.items():
            if value is not None:
                self.el.set(key, str(value))

    def say(self, text, **attrs):
        child = ET.SubElement(self.el, 'Say', **{k: str(v) for k, v in attrs.items() if v is not None})
        child.text = str(text)
        return child

    def play(self, url, **attrs):
        return ET.SubElement(self.el, 'Play', **{k: str(v) for k, v in attrs.items() if v is not None})


class _DialHelper:
    """Scoped builder so ``dial().number(...)`` nests under ``<Dial>``."""

    def __init__(self, response, **attrs):
        self.response = response
        self.el = ET.SubElement(response.root, 'Dial')
        for key, value in attrs.items():
            if value is not None:
                self.el.set(key, str(value))

    def number(self, value, **attrs):
        el = ET.SubElement(self.el, 'Number', **{k: str(v) for k, v in attrs.items() if v is not None})
        el.text = str(value)
        return el

    def sip(self, value, **attrs):
        el = ET.SubElement(self.el, 'Sip', **{k: str(v) for k, v in attrs.items() if v is not None})
        el.text = str(value)
        return el

    def client(self, value, **attrs):
        el = ET.SubElement(self.el, 'Client', **{k: str(v) for k, v in attrs.items() if v is not None})
        el.text = str(value)
        return el
