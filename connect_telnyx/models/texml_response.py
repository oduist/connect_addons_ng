# -*- coding: utf-8 -*-
"""Minimal TeXML builder.

Telnyx TeXML is Twilio-compatible XML, but this module must not depend on
the ``twilio`` python package (ADR-032), so it ships its own tiny builder
covering only the verbs the module renders. The API mirrors
``twilio.twiml.voice_response`` closely enough that render code ported
from connect_twilio reads the same.
"""
from xml.etree import ElementTree as ET
from xml.dom.minidom import parseString


def _format_attr(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def apply_say_voice(content, voice):
    """Add a fallback voice to every Say that has no explicit voice."""
    if content is None or not voice:
        return content
    text = str(content)
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, TypeError, ValueError):
        return text
    changed = False
    for element in root.iter():
        tag = element.tag.rsplit('}', 1)[-1]
        if tag == 'Say' and not element.get('voice'):
            element.set('voice', voice)
            changed = True
    if not changed:
        return text
    xml = ET.tostring(root, encoding='unicode')
    if text.lstrip().startswith('<?xml'):
        return '<?xml version="1.0" encoding="UTF-8"?>' + xml
    return xml


class TeXML:
    """Base TeXML element. Attribute kwargs are rendered verbatim
    (camelCase names as in TwiML/TeXML)."""

    tag = 'Response'

    def __init__(self, body=None, **attrs):
        self.element = ET.Element(
            self.tag,
            {k: _format_attr(v) for k, v in attrs.items() if v is not None})
        if body is not None:
            self.element.text = str(body)

    def append(self, child):
        self.element.append(child.element)
        return child

    def _add(self, tag, body=None, **attrs):
        el = ET.SubElement(
            self.element, tag,
            {k: _format_attr(v) for k, v in attrs.items() if v is not None})
        if body is not None:
            el.text = str(body)
        return el

    def say(self, message, **attrs):
        return self._add('Say', message, **attrs)

    def pause(self, length=1):
        return self._add('Pause', length=length)

    def hangup(self):
        return self._add('Hangup')

    def reject(self, **attrs):
        return self._add('Reject', **attrs)

    def redirect(self, url, **attrs):
        return self._add('Redirect', url, **attrs)

    def play(self, url=None, **attrs):
        return self._add('Play', url, **attrs)

    def record(self, **attrs):
        return self._add('Record', **attrs)

    def to_xml(self):
        return '<?xml version="1.0" encoding="UTF-8"?>' + ET.tostring(
            self.element, encoding='unicode')

    def __str__(self):
        return self.to_xml()


class VoiceResponse(TeXML):
    tag = 'Response'


class Gather(TeXML):
    tag = 'Gather'


class Dial(TeXML):
    tag = 'Dial'

    def sip(self, uri, **attrs):
        return self._add('Sip', uri, **attrs)

    def number(self, number, **attrs):
        return self._add('Number', number, **attrs)

    def conference(self, name, **attrs):
        return self._add('Conference', name, **attrs)


class Connect(TeXML):
    tag = 'Connect'

    def ai_assistant(self, assistant_id, **attrs):
        attrs['id'] = assistant_id
        return self._add('AIAssistant', **attrs)


def pretty_xml(content):
    try:
        dom = parseString(str(content))
        pretty_content = dom.toprettyxml()
        return "\n".join(
            [line for line in pretty_content.splitlines() if line.strip()])
    except Exception as e:
        return 'Pretty XML parse error: {}\n{}'.format(e, str(content))
