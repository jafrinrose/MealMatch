"""Fine-tune the pretrained YOLO-World baseline on the frozen food subset."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

MODEL_CACHE = Path(__file__).resolve().parents[1] / ".model_cache"
(MODEL_CACHE / "matplotlib").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MODEL_CACHE / "matplotlib"))


def default_device() -> str:
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "0"
    return "cpu"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/open_images_food/yolo_dataset.yaml"),
    )
    parser.add_argument("--model", default="yolov8s-worldv2.pt")
    parser.add_argument("--output", type=Path, default=Path("artifacts/vision_finetuning"))
    parser.add_argument("--name", default="yolo_world_food")
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--patience", type=int, default=7)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default=default_device())
    parser.add_argument("--seed", type=int, default=20260919)
    return parser.parse_args()


def main() -> None:
    from ultralytics import YOLOWorld
    from ultralytics.models.yolo.world.train import WorldTrainer

    args = parse_args()
    if not args.data.exists():
        raise FileNotFoundError(
            f"Missing {args.data}. Run prepare_yolo_finetuning.py first."
        )
    args.output.mkdir(parents=True, exist_ok=True)
    configuration = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "initial_checkpoint": args.model,
        "data": str(args.data.resolve()),
        "epochs_maximum": args.epochs,
        "early_stopping_patience": args.patience,
        "batch": args.batch,
        "image_size": args.imgsz,
        "device": args.device,
        "seed": args.seed,
        "optimizer": "AdamW",
        "initial_learning_rate": 0.001,
        "weight_decay": 0.0005,
        "augmentations": {
            "hsv_h": 0.015,
            "hsv_s": 0.5,
            "hsv_v": 0.3,
            "degrees": 5.0,
            "translate": 0.1,
            "scale": 0.35,
            "fliplr": 0.5,
            "mosaic": 0.5,
            "mixup": 0.0,
        },
    }
    (args.output / "configuration.json").write_text(
        json.dumps(configuration, indent=2), encoding="utf-8"
    )

    model = YOLOWorld(args.model)
    model.train(
        trainer=WorldTrainer,
        data=str(args.data.resolve()),
        epochs=args.epochs,
        patience=args.patience,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        seed=args.seed,
        deterministic=True,
        optimizer="AdamW",
        lr0=0.001,
        weight_decay=0.0005,
        hsv_h=0.015,
        hsv_s=0.5,
        hsv_v=0.3,
        degrees=5.0,
        translate=0.1,
        scale=0.35,
        fliplr=0.5,
        mosaic=0.5,
        mixup=0.0,
        close_mosaic=5,
        workers=0,
        project=str(args.output.resolve()),
        name=args.name,
        exist_ok=True,
        plots=True,
        verbose=True,
    )


if __name__ == "__main__":
    main()
