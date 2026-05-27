"""Remnants of Twilio extensions to `connect.settings`.

Most Twilio fields and methods moved to
`connect.provider.twilio.config` in ODU-22 (ADR-025). What stays here:

- module-level constants (TWILIO_EDGES, MAX_EXTEN_LEN, log level)
- helper functions (`strip_number`, `format_connect_response`) imported by
  other Twilio modules.
- license-side registration via ODUIST_MODULES.

`Settings(models.Model)` class is gone — connect.settings is no longer
extended by this module beyond the constants/helpers below.
"""
# -*- coding: utf-8 -*-
import logging
import re

from odoo.addons.connect.models.license import ODUIST_MODULES

ODUIST_MODULES.append('connect_twilio')

logger = logging.getLogger(__name__)

TWILIO_LOG_LEVEL = logging.WARNING

MAX_EXTEN_LEN = 4

TWILIO_EDGES = [
    ('ashburn', 'US East Coast (Virginia)'),
    ('umatilla', 'US West Coast (Oregon)'),
    ('dublin', 'Ireland'),
    ('frankfurt', 'Frankfurt'),
    ('sydney', 'Australia'),
    ('sao-paulo', 'Brazil'),
    ('tokyo', 'Japan'),
    ('singapore', 'Singapore'),
]


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
