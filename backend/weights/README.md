# MealMatch pantry detector checkpoint

`mealmatch-yolo-world-food.pt` is the evaluated but rejected MealMatch detector
checkpoint. It was
fine-tuned from the pretrained Ultralytics `yolov8s-worldv2.pt` checkpoint on a
frozen 27-class subset of Open Images V7.

- SHA-256: `38ef21b13e4c414edca1132c7bd773305e31cb5102feb00671e312b8aeee681b`
- Input size: 640 pixels
- Historical deployment threshold: 0.25, selected on the validation split
- Training images: 2,131
- Validation images: 504
- Untouched test images: 530
- Test mAP@0.50: 0.244
- Test precision/recall at IoU 0.50: 0.399 / 0.288

The detector was initially deployed because it led the controlled benchmark.
Formative testing on actual user fridge, pantry and grocery-table images then
showed poor coverage and false detections, including banana where none was
present. It has been removed from live application inference. The checkpoint is
retained only so the training, evaluation, initial selection and later rejection
remain auditable and reproducible.

The current application uses a configured Qwen2.5-VL variant for complete
ingredient extraction and requires confirmation before saving anything.

The exact data preparation, evaluation, robustness checks, transfer-learning
configuration, limitations, and citations are documented in
[`../../docs/vision-model-evaluation.md`](../../docs/vision-model-evaluation.md)
and [`../../docs/vision-evaluation-results.md`](../../docs/vision-evaluation-results.md).

The upstream YOLO-World implementation is distributed through Ultralytics.
Review the Ultralytics licensing terms before commercial deployment. Open
Images entries retain their source-image licences and attribution requirements.
