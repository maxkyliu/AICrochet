"""Tests for vision.analyze_with_retry — the silent-retry wrapper around analyze_image."""

import sys, os
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import vision


def _resp(parts):
    """Helper: build a vision response with the given part dicts."""
    return {"parts": list(parts)}


SHORT = _resp([
    {"name": "Arm", "type": "capsule", "scale": 1.0},
    {"name": "Leg", "type": "cylinder", "scale": 1.0},
])
FULL = _resp([
    {"name": "Head", "type": "sphere", "scale": 1.0},
    {"name": "Body", "type": "capsule", "scale": 1.5},
    {"name": "Left Arm", "type": "capsule", "scale": 0.8},
    {"name": "Left Leg", "type": "cylinder", "scale": 0.8},
])


def test_first_call_passes_no_retry():
    with mock.patch.object(vision, "analyze_image", return_value=FULL) as m:
        result = vision.analyze_with_retry(b"img", "prompt")
    assert result == FULL
    assert m.call_count == 1


def test_undersegmented_first_then_retry_succeeds():
    with mock.patch.object(vision, "analyze_image", side_effect=[SHORT, FULL]) as m:
        result = vision.analyze_with_retry(b"img", "prompt")
    assert result == FULL
    assert m.call_count == 2
    # Retry call used the strengthened prompt
    retried_prompt = m.call_args_list[1][0][1]
    assert "IMPORTANT" in retried_prompt
    assert "BOTH arms" in retried_prompt


def test_all_retries_fail_returns_last_response():
    bad = _resp([{"name": "Blob", "type": "sphere", "scale": 1.0}])
    with mock.patch.object(vision, "analyze_image", side_effect=[SHORT, SHORT, bad]) as m:
        result = vision.analyze_with_retry(b"img", "prompt")
    # Returns the last response without raising
    assert result == bad
    assert m.call_count == 3   # initial + 2 retries


def test_missing_head_triggers_retry():
    # Has Body + 4 parts but no Head → should retry
    no_head = _resp([
        {"name": "Body", "type": "capsule", "scale": 1.0},
        {"name": "Arm", "type": "capsule", "scale": 1.0},
        {"name": "Leg", "type": "cylinder", "scale": 1.0},
        {"name": "Tail", "type": "cone", "scale": 1.0},
    ])
    with mock.patch.object(vision, "analyze_image", side_effect=[no_head, FULL]) as m:
        result = vision.analyze_with_retry(b"img", "prompt")
    assert result == FULL
    assert m.call_count == 2


def test_missing_body_triggers_retry():
    no_body = _resp([
        {"name": "Head", "type": "sphere", "scale": 1.0},
        {"name": "Arm", "type": "capsule", "scale": 1.0},
        {"name": "Leg", "type": "cylinder", "scale": 1.0},
        {"name": "Tail", "type": "cone", "scale": 1.0},
    ])
    with mock.patch.object(vision, "analyze_image", side_effect=[no_body, FULL]) as m:
        result = vision.analyze_with_retry(b"img", "prompt")
    assert result == FULL
    assert m.call_count == 2
