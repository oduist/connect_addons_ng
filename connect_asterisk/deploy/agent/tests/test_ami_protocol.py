"""AMI wire-protocol parsing tests."""
from connect_asterisk_agent.ami import parse_lines


def test_parse_simple_block():
    message = parse_lines([
        "Event: Newchannel",
        "Uniqueid: 1718000000.42",
        "Channel: PJSIP/101-0000af",
        "CallerIDNum: 101",
    ])
    assert message["Event"] == "Newchannel"
    assert message["Uniqueid"] == "1718000000.42"
    assert message["Channel"] == "PJSIP/101-0000af"


def test_parse_value_with_colon():
    message = parse_lines([
        "Response: Success",
        "Message: Authentication accepted: welcome",
    ])
    assert message["Message"] == "Authentication accepted: welcome"


def test_parse_skips_malformed_lines():
    message = parse_lines([
        "Event: Hangup",
        "garbage-without-colon",
        "Cause: 16",
    ])
    assert message == {"Event": "Hangup", "Cause": "16"}


def test_parse_last_value_wins():
    message = parse_lines([
        "Variable: A=1",
        "Variable: B=2",
    ])
    assert message["Variable"] == "B=2"
