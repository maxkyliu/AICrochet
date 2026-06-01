"""Profile regressor: train and evaluate per-primitive GradientBoostingRegressors.

Each model predicts a fixed-length diameter profile array from (scale, aspect_ratio).
Models are serialized with joblib. A promotion gate (MAE < 1.0 stitches) prevents
degraded models from being deployed.

Usage:
    python -m models.train --all
    python -m models.train --primitive sphere
    python -m models.train --eval-only
"""

import json
import logging
import math
import os
import shutil
import sys
import numpy as np
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parent.parent / "data" / "models"
MAE_THRESHOLD = 1.0  # stitches — model must beat this to be promoted
FEEDBACK_SAMPLE_WEIGHT = 2.0

PRIMITIVES = [
    "sphere", "cylinder", "cone", "frustum", "capsule", "teardrop", "flat_disc", "torus"
]


def _load_sklearn():
    try:
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.multioutput import MultiOutputRegressor
        import joblib
        import sklearn
        return GradientBoostingRegressor, MultiOutputRegressor, joblib, sklearn
    except ImportError:
        raise RuntimeError("Install scikit-learn: pip install scikit-learn")


def _extract_features(record: dict) -> tuple:
    """Return 7-dimensional feature vector and label (diameter_profile)."""
    profile = record["diameter_profile"]
    counts = record.get("stitch_counts") or []
    scale = record.get("scale") or 1.0

    if len(counts) < 2:
        return [scale, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], profile

    n = len(counts)
    max_val = max(counts)
    flat_threshold = max_val * 0.9
    flat_fraction = sum(1 for v in counts if v >= flat_threshold) / n

    mid = n // 2
    first_half = counts[:mid]
    second_half = counts[mid:]

    def _mean_pos_diff(seq):
        diffs = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
        pos = [d for d in diffs if d > 0]
        return sum(pos) / len(pos) if pos else 0.0

    def _mean_neg_diff(seq):
        diffs = [seq[i] - seq[i + 1] for i in range(len(seq) - 1)]
        neg = [d for d in diffs if d > 0]
        return sum(neg) / len(neg) if neg else 0.0

    rise_slope = _mean_pos_diff(first_half)
    fall_slope = _mean_neg_diff(second_half)
    denom = rise_slope + fall_slope + 1e-6
    symmetry_score = max(0.0, 1.0 - abs(rise_slope - fall_slope) / denom)

    features = [
        scale,           # inferred scale (max_stitches / 24)
        float(n),        # sequence length (number of rounds)
        float(max_val),  # absolute size
        rise_slope,      # mean increase per step in first half
        fall_slope,      # mean decrease per step in second half
        flat_fraction,   # proportion of rounds near max diameter
        symmetry_score,  # 1 = perfectly symmetric rise/fall
    ]
    return features, profile


def _load_dataset(primitive_type: str) -> tuple:
    """Load training and validation records for one primitive type."""
    from data.dataset import export_split
    from data.database import get_db, get_feedback_records

    train_records = export_split(split="train", min_quality=0.5)
    val_records = export_split(split="val", min_quality=0.5)

    # Also include feedback corrections as training data
    with get_db() as conn:
        feedback = get_feedback_records(conn)
    for fb in feedback:
        train_records.append({
            "primitive_type": fb.get("primitive_type") or primitive_type,
            "scale": 1.0,
            "diameter_profile": fb["corrected_diameters"],
            "stitch_counts": [],
            "source_type": "feedback",
        })

    # Compute a shared target_len from both splits so predictions align with labels
    all_filtered = [
        r for r in (train_records + val_records)
        if r.get("primitive_type") == primitive_type
    ]
    if not all_filtered:
        return np.array([]), np.array([]), np.array([]), np.array([]), np.array([])
    target_len = max(len(r["diameter_profile"]) for r in all_filtered)

    def _pad_records(records, ptype):
        filtered = [r for r in records if r.get("primitive_type") == ptype]
        X, y, w = [], [], []
        for r in filtered:
            feats, profile = _extract_features(r)
            padded = profile + [profile[-1]] * (target_len - len(profile))
            X.append(feats)
            y.append(padded)
            weight = FEEDBACK_SAMPLE_WEIGHT if r.get("source_type") == "feedback" else 1.0
            w.append(weight)
        return X, y, w

    X_train, y_train, w_train = _pad_records(train_records, primitive_type)
    X_val, y_val, _ = _pad_records(val_records, primitive_type)

    return (
        np.array(X_train), np.array(y_train), np.array(w_train),
        np.array(X_val), np.array(y_val),
    )


def _compute_mae(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    if len(y_true) == 0:
        return {"overall": float("nan"), "per_position": []}
    diff = np.abs(y_true - y_pred)
    per_pos = diff.mean(axis=0).tolist()
    overall = diff.mean()
    return {"overall": float(overall), "per_position": per_pos}


def _archive_existing_model(model_path: Path) -> None:
    if model_path.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        bak = model_path.with_suffix(f".joblib.bak").parent / f"{model_path.stem}_{ts}.joblib.bak"
        shutil.move(str(model_path), str(bak))
        logger.info("Archived previous model to %s", bak.name)


def train_primitive(primitive_type: str, eval_only: bool = False) -> dict:
    """Train (or evaluate) the regressor for one primitive type.

    Returns an eval report dict.
    """
    GBR, MultiOutput, joblib, sklearn = _load_sklearn()
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODELS_DIR / f"{primitive_type}_regressor.joblib"
    meta_path = MODELS_DIR / f"{primitive_type}_regressor_meta.json"

    X_train, y_train, w_train, X_val, y_val = _load_dataset(primitive_type)

    if len(X_train) == 0:
        logger.warning("No training data for primitive '%s'", primitive_type)
        return {"primitive": primitive_type, "status": "no_data"}

    logger.info(
        "Training %s regressor: %d train samples, %d val samples, profile_len=%d",
        primitive_type, len(X_train), len(X_val), y_train.shape[1] if y_train.ndim > 1 else 0,
    )

    if not eval_only:
        base_estimator = GBR(n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42)
        model = MultiOutput(base_estimator)
        model.fit(X_train, y_train, sample_weight=w_train)

        if len(X_val) > 0:
            y_pred_val = model.predict(X_val)
            eval_result = _compute_mae(y_val, y_pred_val)
        else:
            y_pred_train = model.predict(X_train)
            eval_result = _compute_mae(y_train, y_pred_train)
            logger.warning("No val data for '%s'; evaluating on train set", primitive_type)

        overall_mae = eval_result["overall"]
        logger.info("Primitive '%s' MAE=%.4f (threshold=%.1f)", primitive_type, overall_mae, MAE_THRESHOLD)

        report = {
            "primitive": primitive_type,
            "train_count": len(X_train),
            "val_count": len(X_val),
            "mae": eval_result,
            "sklearn_version": sklearn.__version__,
            "trained_at": datetime.now().isoformat(),
            "promoted": False,
        }

        if overall_mae < MAE_THRESHOLD:
            _archive_existing_model(model_path)
            joblib.dump(model, str(model_path))
            report["promoted"] = True
            meta_path.write_text(json.dumps(report, indent=2))
            logger.info("Model promoted: %s", model_path.name)
        else:
            failed_path = MODELS_DIR / f"failed_eval_{primitive_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            failed_path.write_text(json.dumps(report, indent=2))
            logger.warning(
                "Model NOT promoted for '%s' (MAE=%.4f >= %.1f). Report: %s",
                primitive_type, overall_mae, MAE_THRESHOLD, failed_path.name,
            )
        return report

    else:
        # eval-only mode: load existing model
        if not model_path.exists():
            logger.warning("No model to evaluate for '%s'", primitive_type)
            return {"primitive": primitive_type, "status": "no_model"}
        model = joblib.load(str(model_path))
        if len(X_val) > 0:
            y_pred = model.predict(X_val)
            eval_result = _compute_mae(y_val, y_pred)
        else:
            eval_result = {"overall": float("nan"), "per_position": []}
        return {"primitive": primitive_type, "mae": eval_result}


def train_all(eval_only: bool = False) -> list:
    """Train regressors for all primitives. Returns list of per-primitive reports."""
    reports = []
    for ptype in PRIMITIVES:
        try:
            report = train_primitive(ptype, eval_only=eval_only)
            reports.append(report)
        except Exception as exc:
            logger.error("Failed to train '%s': %s", ptype, exc)
            reports.append({"primitive": ptype, "status": "error", "error": str(exc)})

    # Write combined eval report
    report_path = MODELS_DIR / "eval_report.json"
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(reports, indent=2))
    logger.info("Eval report written to %s", report_path)
    return reports


def mark_corrections_incorporated_after_training(promoted_primitives: list):
    """Mark all unincorporated feedback corrections as incorporated."""
    if not promoted_primitives:
        return
    from data.database import get_db, get_feedback_records, mark_corrections_incorporated
    with get_db() as conn:
        feedback = get_feedback_records(conn)
        ids_to_mark = [
            f["id"] for f in feedback
            if not f.get("incorporated")
            and (f.get("primitive_type") in promoted_primitives or f.get("primitive_type") is None)
        ]
        if ids_to_mark:
            mark_corrections_incorporated(conn, ids_to_mark)
            logger.info("Marked %d corrections as incorporated", len(ids_to_mark))


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(prog="models.train")
    parser.add_argument("--all", action="store_true", help="Train all primitive types")
    parser.add_argument("--primitive", default=None, help="Train a specific primitive type")
    parser.add_argument("--eval-only", action="store_true", help="Evaluate existing models only")
    args = parser.parse_args()

    if args.all:
        reports = train_all(eval_only=args.eval_only)
        promoted = [r["primitive"] for r in reports if r.get("promoted")]
        if not args.eval_only:
            mark_corrections_incorporated_after_training(promoted)
    elif args.primitive:
        report = train_primitive(args.primitive, eval_only=args.eval_only)
        if report.get("promoted") and not args.eval_only:
            mark_corrections_incorporated_after_training([args.primitive])
    else:
        parser.print_help()
