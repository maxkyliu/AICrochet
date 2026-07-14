"""Tests for job-tracker TTL eviction and the retraining trigger guard."""

import sys, os
import time
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import comfyui
import main


# ─── ComfyUI job tracker eviction ─────────────────────────────────────────────

def test_comfyui_expired_job_evicted_on_create():
    comfyui._jobs.clear()
    comfyui.create_job("old")
    comfyui._jobs["old"]["created_at"] = time.time() - comfyui._JOB_TTL_SECONDS - 1
    comfyui.create_job("new")
    assert comfyui.get_job("old") is None
    assert comfyui.get_job("new") is not None


def test_comfyui_fresh_job_survives_create():
    comfyui._jobs.clear()
    comfyui.create_job("a")
    comfyui.create_job("b")
    assert comfyui.get_job("a") is not None
    assert comfyui.get_job("b") is not None


# ─── Mesh-measurement job tracker eviction ────────────────────────────────────

def test_measure_expired_job_evicted_on_create():
    main._measure_jobs.clear()
    main._measure_create("old")
    main._measure_jobs["old"]["created_at"] = time.time() - main._MEASURE_JOB_TTL_SECONDS - 1
    main._measure_create("new")
    assert main._measure_get("old") is None
    assert main._measure_get("new") is not None


def test_measure_fresh_job_survives_create():
    main._measure_jobs.clear()
    main._measure_create("a")
    main._measure_create("b")
    assert main._measure_get("a") is not None
    assert main._measure_get("b") is not None


# ─── Retraining trigger guard ─────────────────────────────────────────────────

def _patch_db(monkeypatch, count):
    monkeypatch.setattr(main, "DB_AVAILABLE", True)
    monkeypatch.setattr(main, "get_db", mock.MagicMock(), raising=False)
    monkeypatch.setattr(
        main, "get_unincorporated_count", lambda conn: count, raising=False
    )


def test_retrain_spawns_when_threshold_met(monkeypatch):
    _patch_db(monkeypatch, main.RETRAIN_THRESHOLD)
    monkeypatch.setattr(main, "_retrain_process", None)
    with mock.patch.object(main.subprocess, "Popen") as popen:
        popen.return_value.pid = 12345
        main._maybe_trigger_retraining()
        popen.assert_called_once()


def test_retrain_skipped_while_previous_run_alive(monkeypatch):
    _patch_db(monkeypatch, main.RETRAIN_THRESHOLD)
    alive = mock.MagicMock()
    alive.poll.return_value = None  # still running
    monkeypatch.setattr(main, "_retrain_process", alive)
    with mock.patch.object(main.subprocess, "Popen") as popen:
        main._maybe_trigger_retraining()
        popen.assert_not_called()


def test_retrain_skipped_below_threshold(monkeypatch):
    _patch_db(monkeypatch, main.RETRAIN_THRESHOLD - 1)
    monkeypatch.setattr(main, "_retrain_process", None)
    with mock.patch.object(main.subprocess, "Popen") as popen:
        main._maybe_trigger_retraining()
        popen.assert_not_called()
