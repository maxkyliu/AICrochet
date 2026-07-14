"""Tests for public-deployment guards: daily quota, upload validation,
rate limiting, output sweep, and error hygiene.

TestClient is used WITHOUT a context manager so startup events (ComfyUI
launch) never run.
"""

import sys, os
import time

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import main

client = TestClient(main.app)


# ─── Daily quota unit tests ───────────────────────────────────────────────────

def _reset_quota(monkeypatch, limit, count=0, day=None):
    monkeypatch.setattr(main, "GENERATE_DAILY_LIMIT", limit)
    main._daily_quota["day"] = day if day is not None else time.strftime("%Y-%m-%d")
    main._daily_quota["count"] = count


def test_quota_unlimited_when_zero(monkeypatch):
    _reset_quota(monkeypatch, 0, count=10**6)
    assert main._consume_daily_quota() is True


def test_quota_consumes_then_blocks(monkeypatch):
    _reset_quota(monkeypatch, 2)
    assert main._consume_daily_quota() is True
    assert main._consume_daily_quota() is True
    assert main._consume_daily_quota() is False


def test_quota_resets_on_new_day(monkeypatch):
    _reset_quota(monkeypatch, 1, count=999, day="2000-01-01")
    assert main._consume_daily_quota() is True


# ─── Output sweep ─────────────────────────────────────────────────────────────

def test_sweep_deletes_only_expired_files(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads"
    models = tmp_path / "models"
    uploads.mkdir(); models.mkdir()
    monkeypatch.setattr(main, "_UPLOADS_DIR", str(uploads))
    monkeypatch.setattr(main, "_MODELS_DIR", str(models))

    old = uploads / "old.jpg"
    fresh = models / "fresh.glb"
    old.write_bytes(b"x"); fresh.write_bytes(b"x")
    expired = time.time() - main.OUTPUT_TTL_HOURS * 3600 - 60
    os.utime(old, (expired, expired))

    main._sweep_old_outputs()
    assert not old.exists()
    assert fresh.exists()


# ─── Endpoint guards (order matters: the rate-limit test must run last, as it
#     exhausts the shared per-IP budget on /generate) ──────────────────────────

def test_root_redirects_to_ui():
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/static/index.html"


def test_healthz():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_generate_rejects_oversized_upload(monkeypatch):
    monkeypatch.setattr(main, "MAX_UPLOAD_MB", 0.001)  # ~1 KB
    resp = client.post("/generate", files={"file": ("big.jpg", b"x" * 4096, "image/jpeg")})
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"].lower()


def test_generate_rejects_invalid_image():
    resp = client.post("/generate", files={"file": ("fake.jpg", b"not an image", "image/jpeg")})
    assert resp.status_code == 400
    assert "not a readable image" in resp.json()["detail"]


def test_generate_daily_quota_exhausted(monkeypatch):
    _reset_quota(monkeypatch, 1, count=1)
    resp = client.post("/generate", files={"file": ("a.jpg", b"x", "image/jpeg")})
    assert resp.status_code == 429
    assert "daily" in resp.json()["detail"].lower()


def test_generate_rate_limited_eventually():
    for _ in range(10):
        resp = client.post("/generate", files={"file": ("a.jpg", b"x", "image/jpeg")})
        if resp.status_code == 429 and "daily" not in resp.text.lower():
            break
    assert resp.status_code == 429
