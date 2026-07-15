"""Tests for job-tracker TTL eviction and the retraining trigger guard."""

import sys, os
import time
from unittest import mock

import pytest

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

# ─── _measure_sync coordination (calibration, gating, orientation skip) ───────

import mesh_measure


_REF = [0.25, 0.5, 0.75, 1.0, 1.0, 0.75, 0.5, 0.25]


def _part(name, max_d=8.0, ptype="sphere", bbox=None):
    diameters = [max_d * v for v in _REF]
    return {
        "name": name,
        "instructions": [f"--- {name.upper()} ---"],
        "diameters": diameters,
        "primitive_type": ptype,
        "bbox": bbox,
    }


def _patch_measure(monkeypatch, measured_by_name, confidence=0.9):
    """Point _measure_sync's mesh dependencies at controlled outputs."""
    monkeypatch.setattr(main.mesh_measure, "load_normalized_mesh", lambda path: object())
    monkeypatch.setattr(
        main.mesh_measure, "resolve_orientation", lambda mesh, bboxes: (mesh, confidence)
    )
    # Identity: real normalization would strip the name tag smuggled in bbox[4].
    monkeypatch.setattr(main.mesh_measure, "normalize_bboxes", lambda bbs: bbs)
    calls = {"order": []}

    def fake_measure(mesh, bbox, n_slices=None):
        name = bbox[4] if len(bbox) > 4 else None  # name smuggled in bbox[4]
        calls["order"].append(name)
        return measured_by_name.get(name, [])

    monkeypatch.setattr(main.mesh_measure, "measure_part", fake_measure)
    monkeypatch.setattr(main.geo, "get_reference_curve", lambda ptype: (list(_REF), 0.4))
    return calls


def _bbox(name):
    # Valid 4-tuple plus a name tag our fake measure_part reads.
    return [0.0, 0.0, 1.0, 1.0, name]


def test_median_calibration_robust_to_one_inflated_part(monkeypatch):
    # Two clean parts measured at unit scale, one inflated 4x. Median ratio
    # (8/1) must win so the clean parts keep their true amplitude.
    measured = {
        "head": [v * 1.0 for v in _REF],
        "body": [v * 1.0 for v in _REF],
        "blob": [v * 4.0 for v in _REF],
    }
    _patch_measure(monkeypatch, measured)
    parts = [_part(n, bbox=_bbox(n)) for n in ("head", "body", "blob")]
    from grammar import CrochetGrammar
    refined = main._measure_sync(parts, "unused.glb", CrochetGrammar())

    by_name = {r["name"]: r for r in refined}
    assert max(by_name["head"]["diameters"]) == pytest.approx(8.0)
    assert max(by_name["body"]["diameters"]) == pytest.approx(8.0)
    # The inflated part lands 4x too big — its own error stays its own.
    assert max(by_name["blob"]["diameters"]) == pytest.approx(32.0)


def test_gate_keeps_initial_part_on_shape_disagreement(monkeypatch):
    # Flat measured shape, α=1.0 → regularized == measured, far from the
    # bell reference → MAE gate rejects; initial instructions retained.
    measured = {"head": [1.0] * 8}
    _patch_measure(monkeypatch, measured)
    monkeypatch.setenv("MESH_BLEND_ALPHA", "1.0")
    parts = [_part("head", bbox=_bbox("head"))]
    from grammar import CrochetGrammar
    refined = main._measure_sync(parts, "unused.glb", CrochetGrammar())
    assert refined[0]["instructions"] == ["--- HEAD ---"]
    assert refined[0]["diameters"] == parts[0]["diameters"]


def test_low_orientation_confidence_keeps_all_originals(monkeypatch):
    measured = {"head": [v * 1.0 for v in _REF]}
    calls = _patch_measure(monkeypatch, measured, confidence=0.1)
    parts = [_part("head", bbox=_bbox("head")), _part("body", bbox=_bbox("body"))]
    from grammar import CrochetGrammar
    refined = main._measure_sync(parts, "unused.glb", CrochetGrammar())
    assert [r["instructions"] for r in refined] == [["--- HEAD ---"], ["--- BODY ---"]]
    assert calls["order"] == []  # no measurement attempted


def test_response_shape_unchanged_in_all_outcomes(monkeypatch):
    measured = {"head": [v * 1.0 for v in _REF]}   # body unmeasurable → fallback
    _patch_measure(monkeypatch, measured)
    parts = [
        _part("head", bbox=_bbox("head")),
        _part("body", bbox=None),                   # no bbox → original kept
        _part("fin", ptype="flat_disc", bbox=_bbox("fin")),  # flat → skipped
    ]
    from grammar import CrochetGrammar
    refined = main._measure_sync(parts, "unused.glb", CrochetGrammar())
    assert len(refined) == 3
    for r in refined:
        assert set(r) == {"name", "instructions", "diameters", "primitive_type"}
