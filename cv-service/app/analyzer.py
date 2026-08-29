"""Confluence/cell-count analysis.

Two modes, chosen automatically:
  - REAL: if Cellpose is installed AND sample images are present, run Cellpose
    on the image, derive confluence (masked area / total) and cell count
    (number of labels).
  - STUB: otherwise return a deterministic rising-confluence curve keyed off the
    image index, so the whole system is demoable with zero setup.

To go real:
  pip install cellpose, drop ordered images in ./samples (sparse -> dense),
  and set CV_MODE=real.
"""
import glob
import os
import threading

from .logging_config import get_logger

logger = get_logger(__name__)

CV_MODE = os.environ.get("CV_MODE", "auto")  # auto | real | stub
SAMPLES_DIR = os.environ.get("SAMPLES_DIR", "samples")

_model = None
_samples: list[str] = sorted(glob.glob(os.path.join(SAMPLES_DIR, "*")))
_model_lock = threading.RLock()
_samples_lock = threading.RLock()


def _load_model():
    global _model
    with _model_lock:
        if _model is None:
            from cellpose import models  # imported lazily so stub mode needs no torch
            _model = models.Cellpose(model_type="cyto3")
        return _model


def _real_available() -> bool:
    if CV_MODE == "stub":
        return False
    with _samples_lock:
        if not _samples:
            return False
    try:
        import cellpose  # noqa: F401
    except ImportError:
        return False
    return True


def stub_reading(image_index: int) -> dict:
    conf = min(0.95, 0.30 + 0.18 * image_index)
    return {
        "confluence": round(conf, 3),
        "cell_count": int(200 + 900 * conf),
        "anomalies": [],
        "mode": "stub",
    }


def real_reading(image_index: int) -> dict:
    import numpy as np
    from PIL import Image

    with _samples_lock, _model_lock:
        path = _samples[min(image_index, len(_samples) - 1)]
        img = np.array(Image.open(path).convert("L"))
        model = _load_model()
        masks, _, _, _ = model.eval(img, diameter=None, channels=[0, 0])
    total = masks.size
    covered = int((masks > 0).sum())
    return {
        "confluence": round(covered / total, 3),
        "cell_count": int(masks.max()),
        "anomalies": [],
        "mode": "real",
    }


def analyze(run_id: int, image_index: int) -> dict:
    if _real_available():
        try:
            return real_reading(image_index)
        except (OSError, RuntimeError, ImportError) as e:
            logger.warning(
                "real_analysis_failed",
                extra={
                    "error": str(e),
                    "event_type": "cv_error",
                    "run_id": run_id,
                    "image_index": image_index,
                },
            )
    return stub_reading(image_index)
