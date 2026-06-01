"""Binary photo classifier: 'finished' vs 'wip' for amigurumi photos.

Uses a MobileNetV2 backbone with a fine-tuned classification head.
Requires torchvision. Falls back to a heuristic rule if torch is unavailable.

Training:
    python -m data.scraper.photo_classifier train --data-dir /path/to/labeled_photos

Labeled data directory structure:
    labeled_photos/
        finished/   <- photos of completed amigurumi
        wip/        <- in-progress, construction, yarn-only photos
"""

import os
import io
import json
import logging
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_PATH = Path(os.path.dirname(__file__), "..", "..", "data", "models", "photo_classifier.pt").resolve()
CONFIDENCE_THRESHOLD = 0.85


def _load_image_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "AICrochet/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()


class PhotoClassifier:
    """Wraps a fine-tuned MobileNetV2 for finished/wip classification."""

    def __init__(self):
        self._model = None
        self._transforms = None
        self._classes = ["finished", "wip"]
        if MODEL_PATH.exists():
            self._load_model()

    def _load_model(self):
        try:
            import torch
            import torchvision.transforms as T

            self._model = torch.jit.load(str(MODEL_PATH), map_location="cpu")
            self._model.eval()
            self._transforms = T.Compose([
                T.Resize((224, 224)),
                T.ToTensor(),
                T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])
            logger.info("Photo classifier loaded from %s", MODEL_PATH)
        except Exception as exc:
            logger.warning("Could not load photo classifier model: %s", exc)
            self._model = None

    def predict(self, image_url: str) -> tuple:
        """Returns (class_label, confidence). Falls back to heuristic if model unavailable."""
        if self._model is not None:
            return self._predict_model(image_url)
        return self._predict_heuristic(image_url)

    def _predict_model(self, image_url: str) -> tuple:
        import torch
        from PIL import Image

        img_bytes = _load_image_bytes(image_url)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        tensor = self._transforms(img).unsqueeze(0)
        with torch.no_grad():
            logits = self._model(tensor)
            probs = torch.softmax(logits, dim=1)[0]
        idx = int(probs.argmax())
        return self._classes[idx], float(probs[idx])

    def _predict_heuristic(self, image_url: str) -> tuple:
        """Naive URL-based heuristic when no model is available.
        Treats all photos as potentially finished with low confidence so the
        caller can decide whether to include them based on threshold logic.
        """
        lower = image_url.lower()
        if any(k in lower for k in ["wip", "progress", "process", "making"]):
            return "wip", 0.7
        return "finished", 0.6


def train(data_dir: str, epochs: int = 5, output_path: str = None):
    """Fine-tune MobileNetV2 on labeled photos in data_dir/finished and data_dir/wip."""
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader
        import torchvision.models as models
        import torchvision.transforms as T
        from torchvision.datasets import ImageFolder
    except ImportError:
        raise RuntimeError("Training requires torchvision: pip install torchvision")

    output_path = output_path or str(MODEL_PATH)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    transform = T.Compose([
        T.Resize((224, 224)),
        T.RandomHorizontalFlip(),
        T.ColorJitter(brightness=0.2, saturation=0.2),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    dataset = ImageFolder(data_dir, transform=transform)
    loader = DataLoader(dataset, batch_size=16, shuffle=True)

    backbone = models.mobilenet_v2(weights="IMAGENET1K_V1")
    backbone.classifier[1] = nn.Linear(backbone.last_channel, 2)
    backbone.train()

    optimizer = torch.optim.Adam(backbone.parameters(), lr=1e-4)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(epochs):
        total_loss = 0.0
        for images, labels in loader:
            optimizer.zero_grad()
            outputs = backbone(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        logger.info("Epoch %d/%d  loss=%.4f", epoch + 1, epochs, total_loss / len(loader))

    scripted = torch.jit.script(backbone.eval())
    scripted.save(output_path)
    logger.info("Photo classifier saved to %s", output_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")
    tr = sub.add_parser("train")
    tr.add_argument("--data-dir", required=True)
    tr.add_argument("--epochs", type=int, default=5)
    tr.add_argument("--output", default=None)
    args = parser.parse_args()
    if args.cmd == "train":
        logging.basicConfig(level=logging.INFO)
        train(args.data_dir, epochs=args.epochs, output_path=args.output)
