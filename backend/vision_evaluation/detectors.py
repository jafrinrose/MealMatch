"""Common prediction adapters for zero-shot pantry detector evaluation."""

from __future__ import annotations

import os
import re
import hashlib
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


def evaluation_device(torch_module) -> str:
    requested = os.getenv("MEALMATCH_EVALUATION_DEVICE", "auto")
    if requested != "auto":
        return requested
    if torch_module.backends.mps.is_available():
        return "mps"
    if torch_module.cuda.is_available():
        return "cuda:0"
    return "cpu"


def transformed_image(path: Path, condition: str) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if condition == "dark":
        return ImageEnhance.Brightness(image).enhance(0.55)
    if condition == "bright":
        return ImageEnhance.Brightness(image).enhance(1.45)
    if condition == "blur":
        return image.filter(ImageFilter.GaussianBlur(radius=2.0))
    return image


class YoloWorldAdapter:
    name = "YOLO-World v2"

    def __init__(self, class_names: list[str]):
        import torch
        from ultralytics import YOLOWorld

        model_name = os.getenv("MEALMATCH_YOLO_MODEL", "yolov8s-worldv2.pt")
        self.device = evaluation_device(torch)
        self.model = YOLOWorld(model_name)
        self.class_names = class_names
        self.model.set_classes(class_names)
        checkpoint = Path(str(self.model.ckpt_path or model_name))
        self.metadata = {
            "architecture": self.name,
            "checkpoint": str(checkpoint.resolve()) if checkpoint.exists() else model_name,
            "checkpoint_sha256": (
                hashlib.sha256(checkpoint.read_bytes()).hexdigest()
                if checkpoint.exists()
                else None
            ),
            "inference_size": 640,
            "device": self.device,
        }

    def predict(self, image: Image.Image, minimum_score: float) -> list[dict]:
        result = self.model.predict(
            source=image,
            conf=minimum_score,
            imgsz=640,
            device=self.device,
            verbose=False,
        )[0]
        detections: list[dict] = []
        for box in result.boxes:
            x_min, y_min, x_max, y_max = [float(value) for value in box.xyxy[0].tolist()]
            class_index = int(box.cls.item())
            detections.append(
                {
                    "category_name": self.class_names[class_index],
                    "bbox": [x_min, y_min, x_max - x_min, y_max - y_min],
                    "score": float(box.conf.item()),
                }
            )
        return detections


class GroundingDinoAdapter:
    name = "Grounding DINO Tiny"
    # Mixed-size Open Images batches are padded to the largest image and were
    # slower than single-image inference on the reference M4 Pro. Keep this
    # configurable, but use the empirically faster default.
    batch_size = int(os.getenv("MEALMATCH_GROUNDING_DINO_BATCH", "1"))

    def __init__(self, class_names: list[str]):
        import torch
        from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

        model_name = os.getenv(
            "MEALMATCH_GROUNDING_DINO_MODEL", "IDEA-Research/grounding-dino-tiny"
        )
        revision = os.getenv(
            "MEALMATCH_GROUNDING_DINO_REVISION",
            "a2bb814dd30d776dcf7e30523b00659f4f141c71",
        )
        self.torch = torch
        self.device = evaluation_device(torch)
        self.class_names = class_names
        try:
            self.processor = AutoProcessor.from_pretrained(
                model_name, revision=revision, local_files_only=True
            )
            self.model = AutoModelForZeroShotObjectDetection.from_pretrained(
                model_name, revision=revision, local_files_only=True
            )
        except OSError:
            self.processor = AutoProcessor.from_pretrained(model_name, revision=revision)
            self.model = AutoModelForZeroShotObjectDetection.from_pretrained(
                model_name, revision=revision
            )
        self.model.to(self.device)
        self.model.eval()
        self.metadata = {
            "architecture": self.name,
            "checkpoint": model_name,
            "revision": revision,
            "device": self.device,
            "processor_defaults": True,
        }

    def _convert_processed(self, processed: dict) -> list[dict]:
        labels = processed.get("text_labels", processed.get("labels", []))
        detections: list[dict] = []
        for box, score, label in zip(processed["boxes"], processed["scores"], labels):
            x_min, y_min, x_max, y_max = [float(value) for value in box.tolist()]
            if not isinstance(label, str):
                label = self.class_names[int(label)]
            normalized = re.sub(r"[^a-z0-9]+", " ", str(label).casefold()).strip()
            matched_name = next(
                (
                    name
                    for name in self.class_names
                    if re.sub(r"[^a-z0-9]+", " ", name.casefold()).strip() == normalized
                    or normalized in re.sub(r"[^a-z0-9]+", " ", name.casefold()).strip()
                    or re.sub(r"[^a-z0-9]+", " ", name.casefold()).strip() in normalized
                ),
                None,
            )
            if matched_name:
                detections.append(
                    {
                        "category_name": matched_name,
                        "bbox": [x_min, y_min, x_max - x_min, y_max - y_min],
                        "score": float(score.item()),
                    }
                )
        return detections

    def predict_batch(
        self, images: list[Image.Image], minimum_score: float
    ) -> list[list[dict]]:
        prompt = ". ".join(name.lower() for name in self.class_names) + "."
        inputs = self.processor(
            images=images,
            text=[prompt] * len(images),
            return_tensors="pt",
            padding=True,
        )
        inputs = {
            key: value.to(self.device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }
        with self.torch.no_grad():
            outputs = self.model(**inputs)
        processed = self.processor.post_process_grounded_object_detection(
            outputs,
            inputs["input_ids"],
            threshold=minimum_score,
            text_threshold=0.15,
            target_sizes=[image.size[::-1] for image in images],
        )
        return [self._convert_processed(item) for item in processed]

    def predict(self, image: Image.Image, minimum_score: float) -> list[dict]:
        return self.predict_batch([image], minimum_score)[0]


def build_detector(name: str, class_names: list[str]):
    if name == "yolo_world":
        return YoloWorldAdapter(class_names)
    if name == "grounding_dino":
        return GroundingDinoAdapter(class_names)
    raise ValueError(f"Unknown detector: {name}")
