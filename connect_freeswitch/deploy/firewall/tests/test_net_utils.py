"""Unit tests for IP/CIDR normalization and family routing."""
import pytest

from connect_firewall_service.net_utils import normalize_entry, set_for


@pytest.mark.parametrize("value,expected", [
    # IPv4 hosts and networks
    ("1.2.3.4", ("1.2.3.4", 4)),
    ("  1.2.3.4  ", ("1.2.3.4", 4)),
    ("1.2.3.4/32", ("1.2.3.4", 4)),
    # Host bits inside a CIDR are canonicalized like ipset does.
    ("1.2.3.4/24", ("1.2.3.0/24", 4)),
    ("10.0.0.0/8", ("10.0.0.0/8", 4)),
    # IPv6 hosts and networks — compressed lowercase, /128 stripped
    ("2001:DB8:0:0:0:0:0:1", ("2001:db8::1", 6)),
    ("2001:db8::1/128", ("2001:db8::1", 6)),
    ("2001:DB8::/32", ("2001:db8::/32", 6)),
    ("2001:db8::5/64", ("2001:db8::/64", 6)),
    ("::1", ("::1", 6)),
    # IPv4-mapped IPv6 unwraps to plain IPv4
    ("::ffff:203.0.113.9", ("203.0.113.9", 4)),
    ("[2001:db8::1]", None),  # brackets are NOT accepted here
])
def test_normalize_entry(value, expected):
    if expected is None:
        with pytest.raises(ValueError):
            normalize_entry(value)
    else:
        assert normalize_entry(value) == expected


@pytest.mark.parametrize("value", [
    "not-an-ip", "999.0.0.1", "", "1.2.3.4:5060", "example.com",
    "1.2.3", "2001:db8::zz", None,
])
def test_normalize_entry_rejects_garbage(value):
    with pytest.raises((ValueError, TypeError)):
        normalize_entry(value)


def test_set_for_routes_by_family():
    assert set_for("connect_fw_banned", "1.2.3.4") == "connect_fw_banned"
    assert set_for("connect_fw_banned", "2001:db8::1") == "connect_fw_banned6"
    assert set_for("connect_fw_whitelist", "10.0.0.0/8") == "connect_fw_whitelist"
    assert set_for("connect_fw_whitelist", "2001:db8::/64") == "connect_fw_whitelist6"
    # IPv4-mapped source lands in the v4 set where the packets flow.
    assert set_for("connect_fw_banned", "::ffff:1.2.3.4") == "connect_fw_banned"
