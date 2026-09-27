# Pantry-photo model identification and evaluation

## Objective and scope

The image component should reduce the effort of entering food into the pantry while avoiding silent inventory errors. The target environment is a real household fridge, pantry shelf, or groceries laid on a table. The first experiment treated this as bounding-box detection of visually identifiable food, with branded products handled by a vision-language fallback. Household validation later showed that this formulation was too narrow, so the current experiment evaluates end-to-end visual ingredient extraction with mandatory human confirmation.

The historical detector question was: **which pre-trained open-vocabulary detector provides the most useful zero-shot ingredient boxes?** The current product question is: **which Qwen2.5-VL size provides the most useful reviewable ingredient list from real household photographs at acceptable local latency?**

## Literature-led shortlist

Three architectures were initially identified from peer-reviewed object-detection literature:

1. **YOLO-World v2** is a real-time open-vocabulary detector that connects language prompts to object detection. It was the initial application baseline and is no longer used in production inference. See [Cheng et al., CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/html/Cheng_YOLO-World_Real-Time_Open-Vocabulary_Object_Detection_CVPR_2024_paper.html).
2. **Grounding DINO Tiny** is an open-set detector that grounds text prompts in image regions and provides a contrasting transformer-based architecture. See [Liu et al., ECCV 2024](https://www.ecva.net/papers/eccv_2024/papers_ECCV/html/6319_ECCV_2024_paper.php).
3. **RT-DETR-L** is an efficient real-time transformer detector with strong closed-set results. See [Zhao et al., CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/html/Zhao_DETRs_Beat_YOLOs_on_Real-time_Object_Detection_CVPR_2024_paper.html).

RT-DETR-L is documented in the review but screened out of the primary zero-shot experiment. Its ordinary pre-trained checkpoint predicts a fixed training vocabulary, whereas MealMatch needs arbitrary pantry target classes. Making the comparison equivalent would require task-specific fine-tuning and would turn it into a different experimental condition. The fair primary comparison is therefore YOLO-World versus Grounding DINO using the same text vocabulary, images and ground-truth boxes. RT-DETR can remain a future **fine-tuned closed-set baseline**, reported separately if implemented.

## Dataset choice

The primary benchmark is a class-balanced subset of [Open Images V7](https://storage.googleapis.com/openimages/web/download_v7.html). It was selected because:

- it supplies official train, validation and test splits;
- target objects have human-created or human-verified bounding boxes;
- annotations include occlusion, truncation, depiction and group flags;
- its images contain varied backgrounds, viewpoints, lighting and object scales;
- the official site supports downloading selected classes and image IDs rather than the entire dataset.

Open Images is not perfectly pantry-specific. Its value is controlled detector comparison, not full product validation. A later MealMatch user study covers actual fridges, pantry shelves and grocery-table layouts. MVTec D2S may be considered as an additional retail-domain benchmark, but its acquisition terms and packaged-retail distribution differ from the intended household scene.

### Reproducible acquisition

From the repository root:

```bash
source backend/venv/bin/activate
python backend/vision_evaluation/prepare_open_images.py \
  --output data/open_images_food \
  --train-per-class 80 \
  --validation-per-class 20 \
  --test-per-class 20 \
  --workers 8
```

The script:

1. downloads the official V7 boxable-class mapping;
2. downloads the official bounding-box CSV for each requested split;
3. performs deterministic class-balanced reservoir sampling using seed `20260919`;
4. excludes depictions such as drawings while retaining occlusion and truncation metadata;
5. downloads only selected images from official Open Images storage;
6. converts normalized boxes to pixel-coordinate COCO JSON; and
7. writes a manifest containing the classes, seed and split counts.

The raw annotations are cached under the dataset directory. The training bounding-box CSV is the largest download, so a quick validation/test smoke command is provided in the root README.

Dataset files remain outside Git. This avoids redistributing image files without their original per-image attribution metadata and keeps the repository small. The report should cite Open Images and preserve the original image IDs.

## Experimental design

The primary comparison evaluates **pre-trained zero-shot models**. It is kept separate from the later YOLO-World transfer-learning experiment so the report does not confuse out-of-the-box capability with task-specific adaptation.

- **Training split:** not used to fit the zero-shot models. It is used only in the separately labelled YOLO-World transfer-learning experiment.
- **Validation split:** selects one confidence threshold per detector. Candidate thresholds are `0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.70`; selection maximises F1 at IoU 0.50, with mAP@0.50 as the tie-breaker.
- **Test split:** used once for final model comparison with the validation-selected threshold.
- **Prompts/classes:** identical ordered food-class names are supplied to both detectors.
- **Inference size:** YOLO-World uses 640 pixels. Grounding DINO uses its official processor defaults.
- **Reproducibility:** dataset seed, Grounding DINO revision, YOLO checkpoint checksum, model identifiers, threshold, raw predictions and metrics are saved.

No training augmentation is applied because no training occurs in this experiment. Instead, deterministic brightness reduction, brightness increase and Gaussian blur are applied only as **test-time robustness conditions**. These transformations do not change geometry, so ground-truth boxes remain valid.

### Separate transfer-learning experiment

After the controlled zero-shot comparison, YOLO-World v2 is also fine-tuned from its pretrained checkpoint on the frozen training split. It is the transfer-learning candidate because its substantially lower latency makes it viable for an interactive local application if adaptation closes the accuracy gap. COCO boxes are converted mechanically into normalized YOLO labels; group annotations are excluded because they do not identify individual object locations. The run uses 640-pixel input, batch size 8, AdamW, initial learning rate `0.001`, weight decay `0.0005`, seed `20260919`, a maximum of 20 epochs and early-stopping patience of five validation epochs.

Training-only augmentation uses hue/saturation/value jitter, up to five-degree rotation, translation, scale, horizontal flips and reduced mosaic probability. MixUp is disabled because blends are a poor representation of fridge and tabletop photographs. Ultralytics records box, classification and distribution-focal losses plus validation precision, recall and mAP after every epoch. The best validation checkpoint—not the last checkpoint—is evaluated on the untouched test split using the same MealMatch metric implementation.

## Operationalised metrics

- **IoU:** intersection divided by union for predicted and ground-truth boxes.
- **mAP@0.50:** mean 101-point interpolated average precision across classes at IoU 0.50.
- **mAP@0.50:0.95:** mean AP over IoU thresholds 0.50 to 0.95 in increments of 0.05.
- **Precision and recall:** micro-averaged across non-group ground-truth instances at IoU 0.50.
- **NDCG@0.50:** predictions are ranked by confidence within each image; a prediction is relevant when class and box match an unused ground-truth object at IoU 0.50.
- **Confusion matrix:** rows are actual classes and columns are predicted classes, with a background row and column for false positives and missed objects.
- **Latency:** the benchmark records mean and 95th-percentile inference milliseconds per image after model loading; runtime app telemetry separately records end-to-end analysis milliseconds.

Predictions contained by an Open Images same-class `IsGroupOf` region are ignored rather than counted as false positives, following the intent of COCO crowd-region handling. A paired non-parametric bootstrap over test images reports 95% intervals for both models and their metric differences.

Run the evaluation with:

```bash
python backend/vision_evaluation/evaluate.py \
  --dataset data/open_images_food \
  --output artifacts/vision_evaluation
```

The commands have now been run on the frozen dataset. The immutable report-facing results, uncertainty analysis and final selection are recorded in [vision-evaluation-results.md](vision-evaluation-results.md); raw predictions and generated confusion matrices remain under the Git-ignored `artifacts/` directory.

## From detector deployment to ingredient extraction

The initial runtime combined fine-tuned YOLO-World with `qwen2.5vl:3b`. That
implementation and its detector results are preserved in
[`vision-evaluation-results.md`](vision-evaluation-results.md). Formative use
with actual fridge, pantry and grocery-table photographs showed that the
detector frequently returned one or two objects, missed most unlabelled fridge
contents, and sometimes returned banana where none was present. This exposed a
domain and task mismatch that the Open Images score did not measure.

YOLO has consequently been removed from application inference. The checkpoint
and detector scripts remain only to reproduce the completed experiment. The
live photo path now calls one configured Qwen2.5-VL variant, validates its JSON,
deletes the source image and sends every suggestion through the existing human
confirmation screen. There is no detector/VLM merge in the current architecture.

Qwen2.5-VL is supported by its [technical report](https://arxiv.org/abs/2502.13923),
which documents visual recognition, localization and structured extraction. It
is described here as a **pre-trained vision-language model for ingredient
extraction**, not as a conventional calibrated bounding-box detector.

## Final Qwen 3B-versus-7B evaluation

The production default is `qwen2.5vl:3b`, selected by the completed controlled
replacement experiment. The final candidates were
`qwen2.5vl:3b` and `qwen2.5vl:7b`; adding more image architectures would obscure
the already documented selection process without answering a new question.

### Target-domain dataset

The MealMatch household manifest contains consented refrigerator, individual
shelf/drawer, pantry and grocery-table photographs. It separates development
images used for prompt refinement from a frozen test set. Scenes are tagged as
packaged, unpackaged or mixed and as easy, moderate or difficult. Ground truth
records only food that is visibly identifiable. A second annotator should label
at least 20–30% of the images, with disagreements resolved before the test run.

Manual ground truth is an evaluation resource, not model training. The public
Open Images benchmark remains the reproducible detector comparison; the
household set answers whether the replacement works for MealMatch's actual
input distribution.

The September 2026 audit began with 51 collected photographs. Three exact
duplicate copies were moved to the manifest's exclusion log, rather than
deleted from the evidence trail. One development photograph containing only
opaque freezer bags was also excluded because its reference label, `packaged
goods`, was not an identifiable pantry ingredient and would reward prohibited
guessing. The active set therefore contains 47 unique, scorable photographs:
12 development and 35 frozen test images. Every active record has verified
ingredient labels plus complete scene, packaging and difficulty metadata. Test
labels are recorded as independent human annotations; no test record is marked
model-assisted. A second person subsequently reviewed a stratified nine-image
sample covering every scene type, packaging type and difficulty level (25.7% of
the test split). The dataset owner reported agreement on every ingredient list,
so all nine are recorded as `agreed` with no ground-truth changes. Reviewer
identity was not supplied and is recorded as such rather than inferred.

Use the local annotation helper rather than editing JSON manually:

```bash
mkdir -p data/household_vision/images
# Copy the consented photographs into the images directory, then run:
python backend/vision_evaluation/label_household_photos.py init \
  --images-dir data/household_vision/images \
  --manifest data/household_vision/manifest.json \
  --development-fraction 0.25

python backend/vision_evaluation/label_household_photos.py serve \
  --manifest data/household_vision/manifest.json
```

Open `http://127.0.0.1:8765`. The interface shows each photograph, records its
scene, packaging and difficulty, and accepts one canonical ingredient per line.
Aliases use `canonical | alias 1, alias 2`. It can generate local 3B and 7B
drafts, but stores them separately under `draft_predictions`. For a frozen-test
image, draft reveal is blocked until an independent human label is verified.
The evaluator refuses unverified records or incomplete scene metadata.

The deterministic initial split is only a starting point. Before freezing the
test set, inspect the scene and packaging balance and move records in the UI if
needed. Near-duplicate photographs must remain in the same split.

Optional batch pre-labelling is appropriate for the development split:

```bash
python backend/vision_evaluation/label_household_photos.py prelabel \
  --manifest data/household_vision/manifest.json \
  --split development
```

Do not copy automatic output directly into final ground truth. A human must
remove hallucinations, add misses and verify the entire photograph. The tool
keeps a `.backup` copy of the previous manifest whenever it saves.

### Controlled variables and metrics

Both candidates receive the same image, prompt, JSON schema, temperature,
confidence filtering and label normalization. The development split may be used
to refine the single shared prompt. It must then be frozen before the test split
is run. For the final experiment, each image is processed three times to measure
run-to-run Jaccard consistency.

The frozen inference configuration uses temperature `0.1`, context size `8192`,
maximum image side `1600` pixels, JPEG quality `90`, and minimum returned
confidence `0.45`. EXIF orientation is normalized before resizing. The final
prompt requires one generic pantry concept per output entry, prohibits combined
food strings and vague categories, and production validation removes vague,
non-food and duplicate suggestions. These changes were made using development
images only after the original 4096-token context caused failures on large
photographs.

Before inference, the human label vocabulary is audited for spelling and a
small, frozen canonicalization table handles plurality and harmless specificity
such as `apples`/`green apple` → `apple`, `eggs` → `egg`, and `cherry tomato` →
`tomato`. The table is saved in every result JSON. It deliberately does not
collapse product-distinct concepts such as dairy milk and almond milk. No
mapping may be added after inspecting frozen-test predictions.

The evaluator reports micro ingredient precision, recall and F1; hallucinations
and misses per image; empty-output and failure rates; latency; consistency; and
breakdowns by scene type, packaging and difficulty. Bounding-box IoU, mAP and
NDCG remain appropriate for the earlier detector experiment but are not
misapplied to an unordered ingredient-extraction output.

Uncertainty is estimated with 2,000 deterministic image-cluster bootstrap
resamples. Images, rather than repeated calls, are the sampling unit. The report
also includes the paired 7B-minus-3B F1 interval. A signature-checked JSONL
checkpoint is written after each inference call so an interrupted multi-hour
run can resume without combining incompatible prompts, labels or settings.

### Development-only prompt iteration

The first development run used 13 images. Qwen2.5-VL 3B achieved precision
`0.510`, recall `0.198` and F1 `0.286`; 7B achieved precision `0.465`, recall
`0.458` and F1 `0.462`. Review of development outputs found duplicate concepts,
combined food strings and vague categories. It also identified the unscorable
opaque-bag photograph described above.

After the predeclared cleaning and resizing changes, the second run used the 12
valid development photographs. 3B achieved precision `0.604`, recall `0.223`
and F1 `0.326`, with median latency `13.9` seconds. 7B achieved precision
`0.444`, recall `0.485` and F1 `0.463`, with median latency `29.0` seconds. Both
had zero inference failures. The 7B candidate therefore remains ahead on the
development objective and satisfies the 45-second median gate, although its
`6.58` unmatched suggestions per image confirms the need for human review. No
frozen-test metric has been used for prompt or threshold selection.

Install the two candidates and run development first:

```bash
ollama pull qwen2.5vl:3b
ollama pull qwen2.5vl:7b
python backend/vision_evaluation/evaluate_qwen_household.py \
  --manifest data/household_vision/manifest.json \
  --output artifacts/qwen_household_development \
  --split development
```

After labels, second-person review and the prompt are frozen, run one locked
final experiment with three repeated inferences per image:

```bash
python backend/vision_evaluation/evaluate_qwen_household.py \
  --manifest data/household_vision/manifest.json \
  --output artifacts/qwen_household_final \
  --split test \
  --runs 3
```

If interrupted, append `--resume` to that exact command. The evaluator rejects
a checkpoint whose frozen-input signature differs.

### Predeclared selection rule

Require a failure rate no greater than 5% and median latency no greater than 45
seconds on the reference M4 Pro. Among eligible candidates, select the highest
ingredient F1. Treat an absolute F1 difference below `0.03` as practically tied;
then prefer unpackaged-scene recall. If that recall is also within `0.03` and 7B
is more than 1.5 times slower, select 3B. These thresholds may be changed only
before the frozen test is inspected. Applying this rule selected the existing
`qwen2.5vl:3b` default, which is now final in
`MEALMATCH_VISION_LANGUAGE_MODEL`, the setup script and this report.

### Frozen-test results and final decision

The final experiment processed all 35 frozen test images three times with both
models: 210 image-model runs. Qwen2.5-VL 3B achieved precision `0.334`, recall
`0.163`, F1 `0.219`, zero failures, median latency `7.2` seconds, p95 latency
`137.8` seconds and mean repeatability Jaccard `0.679`. Qwen2.5-VL 7B achieved
precision `0.252`, recall `0.254`, F1 `0.253`, median latency `44.7` seconds,
p95 latency approximately `300` seconds and repeatability `0.657`.

Seven of 7B's 105 calls timed out at 300 seconds, producing a `6.7%` failure
rate. This exceeded the predeclared `5%` eligibility ceiling. The 7B-minus-3B
F1 difference was `+0.034`, but its paired image-cluster bootstrap 95% interval
was `-0.023` to `+0.087`, crossing zero. Consequently, **Qwen2.5-VL 3B is the
selected production image model**: it was the only operationally eligible
candidate, was much faster, had higher precision and had no failures.

The selected result is still modest, particularly on dense grocery tables
(3B recall `0.086`) and should not be represented as autonomous inventory
recognition. Its appropriate role is producing editable suggestions that reduce
some entry effort. Mandatory human confirmation, additions, deletions and
renaming remain part of the product design and the next user study must measure
whether this is actually faster than manual entry.

### Post-selection public-dataset check

A deliberately small external-validity check was run after the household
decision had been frozen. It therefore tests whether the two model sizes behave
similarly on reproducible public imagery; it does not retrospectively influence
model selection. Fifty images were selected deterministically from the official
Open Images V7 test split, with at least two labelled examples for each of the
27 food classes. Both models received the same images, fixed class vocabulary,
prompt and inference settings. This was an image-level presence task because
Qwen returns ingredient lists rather than calibrated boxes.

| Model | Precision | Recall | Micro F1 | Macro F1 | Exact sets | Failures | Median latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen2.5-VL 3B | 0.833 | 0.273 | 0.411 | 0.298 | 20% | 0% | 3.18 s |
| Qwen2.5-VL 7B | 0.900 | 0.818 | 0.857 | 0.827 | 72% | 0% | 6.39 s |

The paired image-cluster bootstrap estimated the 7B-minus-3B micro-F1
difference as `+0.446`, with a 95% interval from `+0.306` to `+0.608`. On this
small, constrained benchmark 7B was unequivocally more capable, while 3B often
returned an empty set and consequently had high precision but poor recall.

This finding does not conflict with the household deployment decision. Public
images were usually simpler, the prompt supplied a closed 27-label vocabulary,
and neither model failed. The household benchmark instead contained dense,
open-ended domestic scenes, used three runs per image, and exposed seven 7B
timeouts plus much higher latency. MealMatch therefore retains 3B because it
alone met the predeclared household reliability gate. The public result is
reported as evidence that model quality is distribution- and task-dependent,
and it identifies a future option: a server-hosted 7B mode may be worthwhile if
its household timeout problem can be removed.

Reproduce the check with:

```bash
python backend/vision_evaluation/evaluate_qwen_public.py \
  --dataset data/open_images_food \
  --output artifacts/qwen_public_external \
  --examples-per-class 2
```

The generated Markdown and JSON retain the 50-image selection, annotation
checksum, raw predictions, per-class results, invalid outputs, inference
configuration and bootstrap intervals. Two examples per class are sufficient
for a fast supplementary check, but not for precise class-by-class claims.

## User testing and design iteration

Participants photograph actual fridges, pantry shelves and groceries arranged on tables. For each scan the software records:

- number of initial and final items;
- additions, deletions and renamed detections;
- inference and confirmation time;
- zero-detection and processing failure rate; and
- optional confidence from 1 (not sure) to 5 (very confident).

The study should also collect short qualitative comments about unclear labels, perceived control and whether confirmation feels faster than manual entry. Results should be segmented by scene type and lighting. Iterations must be tied to evidence—for example, raising the detection threshold after excess deletions, changing prompts after systematic class confusion, or improving review UI after long confirmation times.

The endpoint `GET /vision-study/{user_id}/summary` exports the quantitative interaction measures without retaining the uploaded photographs.

Round 2 refrigerator and grocery-table tests, the diagnosis of their missed items and the resulting pipeline change (close-up passes, recovery of cut-off answers, name and unit handling) are reported in [user-testing-round-2-results.md](user-testing-round-2-results.md#photo-detection-iteration-1). The per-scan record now also stores how each model pass ended and the time until all passes finished.
