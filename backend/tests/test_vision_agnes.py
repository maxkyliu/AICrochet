"""Tests for the Agnes AI (OpenAI-compatible) vision provider."""

import sys, os
import json
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import vision

_PARTS = {"parts": [{"name": "Head", "type": "sphere", "scale": 1.0}]}


def _openai_response(content: str):
    resp = mock.MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def _call_with(content: str, monkeypatch):
    monkeypatch.setenv("AGNES_API_KEY", "sk-test")
    with mock.patch("requests.post", return_value=_openai_response(content)) as post:
        result = vision._analyze_agnes(b"img", "prompt")
    return result, post


def test_agnes_parses_plain_json(monkeypatch):
    result, post = _call_with(json.dumps(_PARTS), monkeypatch)
    assert result == _PARTS
    url = post.call_args[0][0]
    assert url == "https://apihub.agnes-ai.com/v1/chat/completions"
    assert post.call_args[1]["headers"]["Authorization"] == "Bearer sk-test"


def test_agnes_strips_markdown_fences(monkeypatch):
    fenced = "```json\n" + json.dumps(_PARTS) + "\n```"
    result, _ = _call_with(fenced, monkeypatch)
    assert result == _PARTS


def test_agnes_requires_api_key(monkeypatch):
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    try:
        vision._analyze_agnes(b"img", "prompt")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "AGNES_API_KEY" in str(exc)


def test_analyze_image_routes_to_agnes(monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "agnes")
    with mock.patch.object(vision, "_analyze_agnes", return_value=_PARTS) as agnes:
        assert vision.analyze_image(b"img", "prompt") == _PARTS
        agnes.assert_called_once()
