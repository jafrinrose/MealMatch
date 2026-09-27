# Pantry detector evaluation and selection results

**Status:** Completed detector experiment; YOLO retained as evaluated evidence but removed from the live application after household-photo validation  
**Run dates:** 19–20 September 2026  
**Hardware:** Apple M4 Pro, 24 GB unified memory, Apple MPS  
**Seed:** `20260919`

## Executive outcome

The detector experiment remains valid and reproducible: fine-tuned YOLO-World
was the strongest detector on the frozen Open Images benchmark. It was initially
selected as the deployment candidate. Subsequent formative testing with actual
user-supplied fridge, pantry and grocery-table photographs exposed serious
domain shift: most food was missed and false labels, including banana where no
banana was present, appeared. The benchmark selection was therefore overturned
for the product. YOLO is no longer called by the application; its checkpoint,
code, metrics and decision history are retained as evidence of testing and
rejection. The replacement study compares Qwen2.5-VL 3B and 7B on a frozen
household-photo ingredient-extraction set.

## Question and decision rule

MealMatch needs an image model that reduces the effort of entering visible food
without silently corrupting the pantry. The experiment asks which detector is
most useful for localized food suggestions under household-like variation.

The primary comparison is deliberately zero-shot: YOLO-World v2 and Grounding
DINO Tiny receive the same 27 class names, images and boxes. This isolates their
out-of-the-box pre-trained capability. A later, separately labelled experiment
fine-tunes YOLO-World because its low latency made it the practical deployment
candidate if domain adaptation could close the accuracy gap.

The initial deployment candidate had to combine test accuracy, ranked suggestion
quality and interactive latency. This report additionally records why benchmark
performance alone proved insufficient. No image model is allowed to write
directly to the pantry; user confirmation remains part of the system design.

## Frozen dataset

The acquisition script sampled an intended class-balanced subset from official
Open Images train, validation and test splits. It requested 80/20/20 images per
class; the union is smaller than 27 times each quota because one image can
contain several target classes, while some official splits have fewer eligible
images for a class.

| Split | Images | All boxes | Evaluated/trainable non-group boxes | Group boxes |
|---|---:|---:|---:|---:|
| Train | 2,131 | 7,179 | 5,974 | 1,205 |
| Validation | 504 | 1,294 | 1,052 | 242 |
| Test | 530 | 1,392 | 1,087 | 305 |
| **Total** | **3,165** | **9,865** | **8,113** | **1,752** |

The audit found zero image overlap between every pair of splits. Depictions were
excluded at acquisition. Occluded and truncated objects were retained because
they reflect real visual difficulty. Open Images `IsGroupOf` regions were not
treated as individual objects: a same-class prediction contained in such a
region is ignored rather than counted as a false positive.

This is the complete frozen MealMatch benchmark subset, not every food image in
the much larger Open Images dataset. Its value is controlled comparison across
varied public photographs. It does not replace testing on actual household
fridges and pantry shelves.

## Zero-shot pre-trained model comparison

Validation selected the confidence threshold that maximised F1 at IoU 0.50.
The test split was then evaluated once using that threshold.

| Model | Threshold | mAP@0.50 | mAP@0.50:0.95 | Precision | Recall | F1 | NDCG@0.50 | Mean latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| YOLO-World v2 | 0.50 | 0.057 | 0.049 | 0.088 | 0.092 | 0.090 | 0.165 | 31.2 ms |
| Grounding DINO Tiny | 0.40 | 0.181 | 0.167 | 0.193 | 0.232 | 0.211 | 0.356 | 571.7 ms |

Grounding DINO was the clear zero-shot accuracy winner. A paired bootstrap over
530 test images (200 resamples) estimated its mAP@0.50 advantage over zero-shot
YOLO-World as **+0.100 to +0.155** at 95% confidence. Its NDCG advantage was
**+0.149 to +0.243**. However, Grounding DINO took about 18 times longer per
image on the reference machine.

### Deterministic robustness conditions

| Model | Condition | mAP@0.50 | Precision | Recall | NDCG@0.50 | Mean latency |
|---|---|---:|---:|---:|---:|---:|
| YOLO-World v2 | Dark | 0.053 | 0.089 | 0.082 | 0.155 | 29.7 ms |
| YOLO-World v2 | Bright | 0.050 | 0.084 | 0.090 | 0.152 | 30.7 ms |
| YOLO-World v2 | Blur | 0.054 | 0.146 | 0.063 | 0.139 | 26.5 ms |
| Grounding DINO Tiny | Dark | 0.165 | 0.179 | 0.212 | 0.330 | 571.5 ms |
| Grounding DINO Tiny | Bright | 0.172 | 0.177 | 0.213 | 0.326 | 545.4 ms |
| Grounding DINO Tiny | Blur | 0.185 | 0.229 | 0.210 | 0.353 | 552.3 ms |

The robustness results preserve the zero-shot ordering and show that neither
model collapses under the specified transforms. They do not simulate every
real fridge problem, such as severe occlusion, reflective packaging or very
small objects at the back of a shelf.

## Transfer-learning experiment

YOLO-World was fine-tuned from the same pretrained `yolov8s-worldv2.pt`
checkpoint; it was not trained from scratch. Training used only the official
train split. Group boxes were excluded. Validation controlled checkpoint
selection and the test split remained untouched.

| Setting | Value |
|---|---|
| Maximum epochs / patience | 20 / 5 |
| Completed epochs | 20; early stopping did not trigger |
| Batch / image size | 8 / 640 px |
| Optimizer | AdamW |
| Initial learning rate / weight decay | 0.001 / 0.0005 |
| Training augmentations | HSV jitter, ±5° rotation, translation, scaling, horizontal flip, reduced mosaic |
| Disabled augmentation | MixUp |

Validation mAP@0.50 increased from **0.044 at epoch 1** to **0.281 at epoch 20**;
validation mAP@0.50:0.95 increased from **0.028 to 0.197**. The best validation
checkpoint was then evaluated through the same independent MealMatch evaluator.

| Model state | Threshold | mAP@0.50 | mAP@0.50:0.95 | Precision | Recall | F1 | NDCG@0.50 | Mean latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| YOLO-World zero-shot | 0.50 | 0.057 | 0.049 | 0.088 | 0.092 | 0.090 | 0.165 | 31.2 ms |
| Grounding DINO zero-shot | 0.40 | 0.181 | 0.167 | 0.193 | 0.232 | 0.211 | 0.356 | 571.7 ms |
| **YOLO-World fine-tuned** | **0.25** | **0.244** | **0.172** | **0.399** | **0.288** | **0.335** | **0.461** | **24.7 ms** |

The fine-tuned model also retained similar performance under deterministic
variation: mAP@0.50 was 0.217 dark, 0.229 bright and 0.238 blurred.

### Uncertainty against the strongest zero-shot model

A paired non-parametric bootstrap over test images used 500 resamples. Values
below are fine-tuned YOLO-World minus zero-shot Grounding DINO.

| Metric difference | Median | 95% interval | Interpretation |
|---|---:|---:|---|
| mAP@0.50 | +0.066 | +0.026 to +0.108 | Positive throughout interval |
| mAP@0.50:0.95 | +0.007 | −0.027 to +0.040 | No clear difference at stricter IoUs |
| Precision | +0.203 | +0.150 to +0.262 | Positive throughout interval |
| Recall | +0.053 | −0.001 to +0.116 | Borderline; do not claim a definite recall gain |
| F1 | +0.121 | +0.066 to +0.181 | Positive throughout interval |
| NDCG@0.50 | +0.101 | +0.045 to +0.161 | Better ranked review suggestions |

This qualification matters: the fine-tuned detector clearly improves the main
IoU-0.50 interaction metrics, but the experiment does not show a reliable
advantage at every localization strictness or for recall alone.

## Class-level findings

Fine-tuned YOLO-World performed best on pasta (AP 0.773), chicken (0.712),
pumpkin (0.681), milk (0.493) and fish (0.434). It scored zero AP on grape and
potato and remained weak on carrot, banana and mango. Grounding DINO was strong
on chicken (0.809), pasta (0.528) and bread (0.440), but scored zero AP on
cheese, lemon, mango, peach and pineapple.

These failures rule out automatic inventory writes. They also show why a single
aggregate metric is insufficient: pantry usefulness depends on which foods a
household owns. Per-class metrics and confusion CSVs are retained with the raw
evaluation artifacts.

## Initial benchmark decision (20 September 2026)

**Initially selected detector candidate:** the fine-tuned MealMatch YOLO-World
v2 checkpoint.

Reasons:

1. it achieved the best test mAP@0.50, precision, F1 and NDCG;
2. its mAP@0.50 advantage over the strongest zero-shot alternative remained
   positive in the paired bootstrap interval;
3. 24.7 ms model inference supports an interactive confirmation flow; and
4. its fixed evaluated 27-class vocabulary matches the bundled checkpoint,
   avoiding a difference between the measured and deployed detector.

Grounding DINO is rejected as the runtime detector for this version, not as a
poor model: it was the best zero-shot model and remains the best fallback if a
future project needs open vocabulary without task-specific training.
Zero-shot YOLO-World is rejected because its accuracy was substantially lower.
RT-DETR-L was screened out before the zero-shot experiment because its ordinary
checkpoint has a fixed label vocabulary, so it was not falsely presented as an
equivalent open-vocabulary result.

Only the selected low-latency architecture was fine-tuned after the controlled
zero-shot comparison. Fine-tuning every screened model was not required to
answer the pre-trained model-selection question and would mix a like-for-like
zero-shot comparison with architecture-specific training recipes.

## Household deployment validation and revised decision (21 September 2026)

The initial decision was challenged with the kind of images the feature
actually receives. Formative use involved full refrigerators, pantry scenes and
groceries laid on a table rather than isolated Open Images objects. The
fine-tuned detector commonly returned only one or two ingredients, returned no
useful result for some unlabelled fridge contents, and produced banana false
positives in photographs without bananas.

A retained grocery-table test photograph containing many packaged and
unpackaged foods illustrates the failure. At the deployed `0.25` threshold the
detector returned only pineapple and banana. Lowering the threshold to `0.05`
did not recover the wider inventory; it chiefly duplicated those categories.
Qwen2.5-VL 3B also remained incomplete on this difficult photograph, but across
formative tests it recovered more packaged ingredients when readable labels
were present. These observations are formative product validation, not a
replacement for the planned frozen household benchmark or participant study.

The failure is consistent with dataset and task mismatch. The Open Images
experiment measured 27-class bounding-box detection on public photographs.
MealMatch needs open-ended ingredient extraction from densely packed domestic
scenes, including identification through package text. Good benchmark results
therefore did not establish household usefulness.

**Revised product decision:** YOLO-World is rejected as the live pantry-photo
model and has been removed from application inference. The detector checkpoint,
training scripts, raw-result references and all figures above remain in the
repository so the unsuccessful deployment decision is auditable. They are not
described as current architecture. The final image model will be the better of
Qwen2.5-VL 3B and 7B under the controlled household evaluation documented in
[`vision-model-evaluation.md`](vision-model-evaluation.md).

## Product operationalisation

The evaluated 25 MB checkpoint is retained at
`backend/weights/mealmatch-yolo-world-food.pt`. Its
SHA-256 is
`38ef21b13e4c414edca1132c7bd773305e31cb5102feb00671e312b8aeee681b`.
It is a historical reproducibility artifact and is **not** loaded or verified by
the live application.

The former detector-assisted runtime pipeline was:

1. selected YOLO-World returns localized common-food suggestions at the
   validation-selected 0.25 threshold;
2. Qwen2.5-VL separately interprets readable packaging and ambiguity;
3. suggestions are merged with model provenance;
4. the source image is deleted after inference; and
5. the user confirms names, quantities and expiry dates before SQLite changes.

The intended detector contribution was reduced manual pantry entry. Household
validation showed that its correction burden undermined that contribution;
retaining the review step nevertheless prevented false detections from silently
changing pantry state.

The current application pipeline is deliberately simpler:

1. the configured Qwen2.5-VL variant analyses the complete photograph for
   packaged and unpackaged food;
2. its structured suggestions are validated and non-food terms are blocked;
3. the source image is deleted after inference; and
4. the user confirms, removes, renames or adds items and supplies expiry dates
   before pantry state changes.

The completed frozen household comparison selected `qwen2.5vl:3b` as the final
runtime variant. Across 105 calls per model, 3B achieved precision `0.334`,
recall `0.163`, F1 `0.219`, zero failures, 7.2-second median latency and
repeatability Jaccard `0.679`. 7B increased F1 to `0.253`, but seven calls timed
out: its `6.7%` failure rate exceeded the predeclared `5%` operational ceiling,
while median latency rose to 44.7 seconds and p95 reached the 300-second
timeout. The paired 7B-minus-3B F1 interval (`-0.023` to `+0.087`) crossed zero.
3B was therefore the only eligible candidate and remains protected by mandatory
human confirmation.

## Supplementary public Qwen comparison (23 September 2026)

After freezing the household decision, the same Qwen variants were evaluated
once on a deterministic 50-image subset of the official Open Images test split.
The subset contains at least two examples from every one of the 27 food classes.
The models received an identical closed vocabulary and were scored on
image-level ingredient presence rather than bounding boxes.

Qwen2.5-VL 3B achieved precision `0.833`, recall `0.273` and F1 `0.411`;
Qwen2.5-VL 7B achieved precision `0.900`, recall `0.818` and F1 `0.857`. Both
completed all 50 calls. Median latency was 3.18 seconds for 3B and 6.39 seconds
for 7B. The paired 7B-minus-3B F1 difference was `+0.446`, with a 95% bootstrap
interval of `+0.306` to `+0.608`.

This is strong evidence that 7B is the better classifier on the constrained
public task. It is not evidence that 7B is the better local MealMatch model:
the frozen household benchmark is closer to the deployment distribution and
exposed a `6.7%` 7B timeout rate. The result is therefore retained as an
external-validity check and as a transparent example of why benchmark rank can
change with data distribution, prompt constraints and operational conditions.
Its two examples per class do not support reliable class-specific conclusions.

## What remains for the human study

The detector and replacement-model experiments are complete. The remaining
rubric evidence is participant testing of the selected 3B workflow. The
application already records additions, deletions, renames, confirmation time,
failure rate and optional confidence. The next report stage should compare that
correction effort with manual entry, collect qualitative feedback and document
at least one interface iteration driven by the findings.

## Reproducibility and retained evidence

- Protocol and commands: [`vision-model-evaluation.md`](vision-model-evaluation.md)
- Historical pipeline smoke test: [`vision-evaluation-smoke-results.md`](vision-evaluation-smoke-results.md)
- Dataset audit: `artifacts/vision_evaluation/dataset_audit.json`
- Zero-shot predictions/results: `artifacts/vision_evaluation/`
- Fine-tuning logs, losses and plots: `artifacts/vision_finetuning/yolo_world_food/`
- Fine-tuned test predictions/results: `artifacts/vision_evaluation_finetuned/`
- Qwen household development results: `artifacts/qwen_household_development_v2/`
- Qwen frozen-test predictions/results: `artifacts/qwen_household_final/`
- Qwen public external-validity results: `artifacts/qwen_public_external/`
- Training and evaluation source: `backend/vision_evaluation/`

The large dataset and generated artifacts are intentionally Git-ignored. The
rejected checkpoint and report evidence are included in the repository so the
full model-selection and rejection process remains reproducible.
