"""Unit tests for family-agnostic IP extraction from ESL events."""
import pytest

from connect_firewall_service.esl_handler import _extract_ip
from connect_firewall_service.reconciler import _split_by_family


@pytest.mark.parametrize("event,expected", [
    # Bare IP headers, both families, normalization applied
    ({"network_ip": "1.2.3.4"}, "1.2.3.4"),
    ({"network_ip": "2001:DB8::1"}, "2001:db8::1"),
    ({"Network-Ip": "[2001:db8::1]"}, "2001:db8::1"),
    ({"network_ip": "::ffff:203.0.113.9"}, "203.0.113.9"),
    ({"sip_contact_host": "2001:db8:0:0::2"}, "2001:db8::2"),
    # Contact URI host, both families
    ({"contact": '"user" <sip:user@1.2.3.4:5060>'}, "1.2.3.4"),
    ({"contact": "<sip:user@[2001:db8::3]:5060>"}, "2001:db8::3"),
    # NAT: received= wins over the URI host, brackets optional
    ({"contact": "<sip:user@10.99.0.5>;received=203.0.113.7"}, "203.0.113.7"),
    ({"contact": "<sip:u@[2001:db8::4]>;received=[2001:db8::9]"}, "2001:db8::9"),
    ({"contact": "<sip:u@[2001:db8::4]>;received=2001:db8::8"}, "2001:db8::8"),
    # Invalid candidates are rejected, not passed to ipset
    ({"network_ip": "garbage"}, None),
    ({"from-host": "example.com"}, None),
    ({"network_ip": "1.2.3.999"}, None),
    ({}, None),
])
def test_extract_ip(event, expected):
    assert _extract_ip(event) == expected


def test_split_by_family_normalizes_and_skips_invalid():
    rows = [
        {"ip_or_cidr": "1.2.3.4/24", "name": "office"},
        {"ip_or_cidr": "2001:DB8::1", "name": "v6 host", "note": "x"},
        {"ip_or_cidr": "not-an-ip", "name": "bad"},
        {"ip_or_cidr": None, "name": "empty"},
    ]
    v4, v6 = _split_by_family(rows)
    assert [entry for entry, _comment in v4] == ["1.2.3.0/24"]
    assert [entry for entry, _comment in v6] == ["2001:db8::1"]
    assert v6[0][1] == "v6 host — x"
