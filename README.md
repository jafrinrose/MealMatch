# MealMatch

MealMatch is a responsive pantry and cooking assistant designed to reduce household food waste and meal-decision fatigue. It tracks pantry quantities and expiry dates, recommends recipes using available and expiring food, and provides persistent hands-free cooking guidance.

## AI models

MealMatch uses pre-trained models in three different data spaces:

| Data space | Model | Working feature |
|---|---|---|
| Text | Ollama `llama3.2:3b` | Recipe generation, recommendation explanations, substitutions, cooking questions and naming receipt lines |
| Image | Qwen2.5-VL 3B | Structured ingredient extraction from pantry, fridge and grocery photographs |
| Audio | Whisper `small.en` through `faster-whisper` | Hands-free cooking commands and questions |

Fine-tuned YOLO-World and Grounding DINO were evaluated as dedicated detectors. YOLO initially won the detector benchmark but failed formative testing on real user fridge and grocery photographs, so it was removed from live inference. Its results and checkpoint remain as tested-and-rejected evidence. All photo and receipt suggestions require human confirmation before pantry data changes.

## Requirements

- Python 3.11 recommended (the tested backend environment uses Python 3.11)
- Node.js 20.19 or newer, or 22.12 or newer
- [Ollama](https://ollama.com/download); the evaluations and timings used 0.30.10. Other versions should work but can give slightly different answers and timings
- Tesseract OCR with English language data for receipt scanning
- 16 GB system memory recommended
- Approximately 10–15 GB free disk space for dependencies and model caches

The application runs on macOS, Windows and Linux. CPU inference works but is slower; Apple Silicon or a supported GPU improves model latency.

Install Tesseract before starting the backend, for example `brew install tesseract` on macOS or `sudo apt install tesseract-ocr` on Ubuntu. Windows installers are linked from the [official Tesseract documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html).

## Installation

Clone the repository, then create the backend environment from the repository root:

```bash
python3.11 -m venv backend/venv
source backend/venv/bin/activate
python -m pip install --upgrade pip
pip install -r backend/requirements.txt
```

On Windows PowerShell, create and activate with:

```powershell
py -3.11 -m venv backend\venv
backend\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
```

Install and start Ollama, then download every pretrained model at the version the evaluations used:

```bash
python backend/setup_models.py
```

The exact versions are pinned in [`backend/model_versions.py`](backend/model_versions.py). The script pulls each Ollama model only if it is missing, then checks every installed model against its recorded digest. Ollama tags can be republished upstream, so a mismatch is reported: results may then differ from those in `docs/`. It also downloads Whisper `small.en` and the `all-MiniLM-L6-v2` recipe-matching model at fixed commits into `backend/.model_cache` (about 550 MB). Without the recipe-matching model, recommendations use pantry matching only. Run it with the backend environment active (it stops and says so otherwise).

Equivalent manual commands for the Ollama models are:

```bash
ollama pull llama3.2:3b
ollama pull qwen2.5vl:3b
```

The rejected YOLO-World checkpoint remains under `backend/weights` only to preserve the detector experiment; the application does not load it. Other model weights, datasets, generated evaluation outputs and uploaded images are excluded from Git.

Install the frontend:

```bash
cd frontend
npm install
cd ..
```

## Run the application

Terminal 1:

```bash
source backend/venv/bin/activate
uvicorn main:app --app-dir backend --reload --port 8000
```

Terminal 2:

```bash
cd frontend
npm run dev
```

Open the local URL printed by Vite, normally `http://localhost:5173`. FastAPI documentation is available at `http://127.0.0.1:8000/docs`.

On first start the backend copies `backend/mealmatch_starter.db` (the demo user and the 200-recipe collection) to `backend/mealmatch.db`. Your pantry, cooking chats and study records are saved only in `mealmatch.db`, which Git ignores.

The app opens with a short scroll-driven film, "Open the fridge", once per browser session. "Open my kitchen" goes to the home screen, and "Replay the opening" on the home screen plays it again. Add `?skipIntro=1` to the URL to skip it, or `?intro=1` to force it; `?intro=1&introP=0.4` pins one frame for review. After the film, the "See how it works" tour plays once per browser session; `?skipTour=1` skips it.

To try the receipt route without a receipt of your own, use `samples/receipt.jpg`, a made-up supermarket receipt. In the app, choose **Add food**, then the **Receipt** tab, and upload the file.

Check local model readiness at any time:

```bash
python backend/setup_models.py --check
```

Optional environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `MEALMATCH_DATABASE_URL` | Local `backend/mealmatch.db` | Use another SQLite or SQLAlchemy database URL |
| `MEALMATCH_TEXT_MODEL` | `llama3.2:3b` | Selected Ollama text model from the guarded task evaluation |
| `MEALMATCH_RECEIPT_MODEL` | Same as `MEALMATCH_TEXT_MODEL` | Ollama model that names receipt lines |
| `MEALMATCH_VISION_LANGUAGE_MODEL` | `qwen2.5vl:3b` | Selected Ollama pantry-photo model from the frozen household evaluation |
| `MEALMATCH_WHISPER_MODEL` | `small.en` | Selected faster-whisper English speech model |
| `MEALMATCH_VLM_MIN_CONFIDENCE` | `0.45` | Minimum semantic suggestion confidence before review |
| `MEALMATCH_VISION_TIMEOUT_SECONDS` | `300` | Maximum local Qwen photo-analysis time |
| `MEALMATCH_VISION_CONTEXT_TOKENS` | `8192` | Ollama context size used for the image and fixed extraction prompt |
| `MEALMATCH_VISION_MAX_IMAGE_SIDE` | `1600` | Maximum image dimension before local vision inference |
| `MEALMATCH_VISION_MAX_OUTPUT_TOKENS` | `2048` | Longest photo answer; enough for about 35 items |
| `MEALMATCH_VISION_KEEP_ALIVE` | `5m` | How long the photo model stays in memory after the last scan |
| `MEALMATCH_VISION_CLOSE_UPS` | `0` | `1` runs the four close-ups after every photo instead of only on "Look closer" |
| `MEALMATCH_OLLAMA_CHAT_URL` | `http://127.0.0.1:11434/api/chat` | Ollama endpoint for pantry photos |
| `MEALMATCH_OLLAMA_GENERATE_URL` | `http://127.0.0.1:11434/api/generate` | Ollama endpoint for the text model |
| `VITE_API_URL` | `/api` through the Vite development proxy | Override the frontend API base URL for deployment |

## Memory and speed

Measured on the reference Apple M4 Pro with Ollama 0.30.10:

| Loaded in Ollama | Memory |
|---|---|
| Photo model `qwen2.5vl:3b` (8,192-token context) | 4.6 GB |
| Text model `llama3.2:3b` (Ollama's 4,096-token default) | 2.6 GB |
| Both at once | 7.1 GB |

Each photo pass spent about 7 seconds reading the image and 2–5 seconds writing the list. Loading the photo model took 1.4 seconds once its files were in the disk cache. The defaults therefore favour low memory:

- **One model pass per photo.** The four close-ups (four more passes) run only when the user presses "Look closer". On the frozen test they added 25 correct and 189 wrong items (see [Round 2 results](docs/user-testing-round-2-results.md)).
- **Models leave memory when idle.** The photo model unloads 5 minutes after the last scan, and the text model after Ollama's default of 5 minutes. The app starts loading the photo model when the Photo tab opens, so the reload is hidden while the user chooses a photo.
- **No recipe photos.** AI-created recipes show their main ingredients as emojis. An image model (FLUX.2 Klein) was tried and removed: it held 5.7 GB while it rendered and took about 10 s a photo at 512×384 ([Decision 43](docs/decision-log.md#decision-43-remove-recipe-photo-generation-emojis-stand-in)).

To use less memory:

- Start Ollama with `OLLAMA_MAX_LOADED_MODELS=1` (for example `OLLAMA_MAX_LOADED_MODELS=1 ollama serve`) so only one model is in memory at a time. Peak use then stays near 4.6 GB instead of 7.1 GB, but switching between photo scanning and the recipe features reloads a model.
- Run `ollama stop qwen2.5vl:3b` to free the photo model immediately.
- To run the models on another computer, start Ollama there with `OLLAMA_HOST=0.0.0.0` and point `MEALMATCH_OLLAMA_CHAT_URL` and `MEALMATCH_OLLAMA_GENERATE_URL` at it. Photos then travel over the network to that computer.

Lowering `MEALMATCH_VISION_CONTEXT_TOKENS` is not worthwhile: 4,096 tokens saved only 0.24 GB and is too small for the image plus a full answer. A smaller `MEALMATCH_VISION_MAX_IMAGE_SIDE` would shorten the image-reading time but has not been evaluated.

## Reproducing the historical detector evaluation

The detector benchmark uses a class-balanced subset of **Open Images V7**. The preparation script downloads official bounding-box annotations and only the selected images, preserves the official splits, and writes COCO JSON.

Detector dependencies are separate from the live application's requirements:

```bash
pip install -r backend/requirements-evaluation.txt
```

For the reproducible full subset used in the final comparison:

```bash
source backend/venv/bin/activate
python backend/vision_evaluation/prepare_open_images.py \
  --output data/open_images_food \
  --train-per-class 80 \
  --validation-per-class 20 \
  --test-per-class 20 \
  --workers 8
```

The training annotation file is large. For a quick pipeline check that avoids it:

```bash
python backend/vision_evaluation/prepare_open_images.py \
  --output data/open_images_food_smoke \
  --splits validation test \
  --validation-per-class 2 \
  --test-per-class 2
```

Do not move images between the official splits. The primary comparison is zero-shot: the training split is excluded, validation selects confidence thresholds, and the untouched test split produces final metrics. A separately labelled transfer-learning experiment then uses the training split, selects its checkpoint on validation, and evaluates it on the same untouched test split.

Run the model comparison after both validation and test splits exist:

```bash
python backend/vision_evaluation/evaluate.py \
  --dataset data/open_images_food \
  --output artifacts/vision_evaluation
```

The output contains raw predictions, validation threshold selection, mAP, precision, recall, NDCG, and confusion matrices for YOLO-World and Grounding DINO under original, dark, bright and blurred conditions. See [the full evaluation protocol](docs/vision-model-evaluation.md).

Audit split integrity and prepare the separately reported transfer-learning experiment:

```bash
python backend/vision_evaluation/audit_dataset.py \
  --dataset data/open_images_food \
  --output artifacts/vision_evaluation/dataset_audit.json

python backend/vision_evaluation/prepare_yolo_finetuning.py \
  --dataset data/open_images_food

python backend/vision_evaluation/finetune_yolo_world.py \
  --data data/open_images_food/yolo_dataset.yaml \
  --epochs 20 \
  --patience 5
```

Fine-tuning starts from the same pretrained YOLO-World v2 checkpoint; it is not training from scratch. Augmentations apply only to the training split, validation monitors loss and model fitness for early stopping, and the untouched test split remains reserved for final evaluation.

Evaluate the best fine-tuned checkpoint with the same independent evaluator:

```bash
MEALMATCH_YOLO_MODEL=artifacts/vision_finetuning/yolo_world_food/weights/best.pt \
python backend/vision_evaluation/evaluate.py \
  --dataset data/open_images_food \
  --output artifacts/vision_evaluation_finetuned \
  --models yolo_world \
  --run-label yolo-world-finetuned
```

The completed experiment used 3,165 images across the official splits and
initially selected the fine-tuned YOLO-World checkpoint. Household validation
later overturned that deployment decision. See the
[full results and revised decision](docs/vision-evaluation-results.md) for test
metrics, robustness results, paired-bootstrap intervals, deployment failures
and the reason YOLO is no longer part of the application.

## Selecting the Qwen household-photo model

The final image decision is deliberately limited to Qwen2.5-VL 3B and 7B. Add
consented household images and initialize the local annotation tool:

```bash
mkdir -p data/household_vision/images
# Copy photographs into data/household_vision/images, then:
python backend/vision_evaluation/label_household_photos.py init \
  --images-dir data/household_vision/images \
  --manifest data/household_vision/manifest.json

python backend/vision_evaluation/label_household_photos.py serve \
  --manifest data/household_vision/manifest.json
```

Open `http://127.0.0.1:8765` to label images without editing JSON. The tool can
generate hidden Qwen drafts, but only human-verified labels are accepted by the
evaluator. Frozen-test drafts cannot be revealed until the independent label is
saved. Install both model candidates before generating drafts:

```bash
ollama pull qwen2.5vl:3b
ollama pull qwen2.5vl:7b
```

Run the development set while checking the fixed prompt and labels, then freeze
them and run the test set three times per image:

```bash
python backend/vision_evaluation/evaluate_qwen_household.py \
  --manifest data/household_vision/manifest.json \
  --output artifacts/qwen_household_development \
  --split development

python backend/vision_evaluation/evaluate_qwen_household.py \
  --manifest data/household_vision/manifest.json \
  --output artifacts/qwen_household_final \
  --split test \
  --runs 3
```

The evaluator appends a signature-checked checkpoint after every model/image
run. If a long evaluation is interrupted, run the identical command with
`--resume`; changed labels, prompts, model lists or inference settings are
rejected instead of being silently mixed into the same result.

The evaluator records ingredient precision, recall, F1, hallucinations, misses,
empty responses, failures, latency, repeatability and performance by scene,
packaging and difficulty, image-cluster bootstrap intervals and the paired F1
difference between model sizes. The frozen test selected **Qwen2.5-VL 3B**: it
had F1 `0.219`, zero failures and 7.2-second median latency. 7B had higher F1
`0.253`, but its `6.7%` failure rate exceeded the predeclared `5%` ceiling and
its median latency was 44.7 seconds. The detailed evidence and limitations are
in the evaluation protocol.

Run the small post-selection public-dataset check separately:

```bash
python backend/vision_evaluation/evaluate_qwen_public.py \
  --dataset data/open_images_food \
  --output artifacts/qwen_public_external \
  --examples-per-class 2
```

This selects 50 official Open Images test photographs spanning all 27 classes.
It found substantially higher constrained-task F1 for 7B (`0.857`) than 3B
(`0.411`), while the household operational gate still selects 3B. The protocol
explains why the public result is supplementary rather than a replacement for
target-domain validation.

## Reproducing the hands-free audio evaluation

The audio selection uses two stages. On macOS with `ffmpeg` installed, first
generate the controlled command set and screen three Whisper capacities:

```bash
python backend/audio_evaluation/evaluate_whisper.py \
  --output artifacts/whisper_evaluation \
  --generate-macos
```

Then compare the winning Whisper size against two literature-backed ASR
families using the exact same frozen manifest:

```bash
python backend/audio_evaluation/evaluate_asr_models.py \
  --manifest artifacts/whisper_evaluation/audio-manifest.json \
  --output artifacts/asr_family_evaluation
```

The 108-file benchmark covers every cooking command across three English voices
under clean and 10 dB noise conditions. The final comparison evaluated Whisper
`small.en`, Distil-Whisper `small.en` and wav2vec 2.0 Base 960h. Only Whisper
met both intent gates: 95.4% overall and 92.6% noisy intent accuracy. This
synthetic benchmark is reproducible but does not replace participant evidence.
It was chosen instead of a public ASR corpus because
it supplies exact transcripts and expected MealMatch intents for every supported
cooking route under matched clean and noisy conditions. The recordings were
generated from 18 fixed phrases with three macOS voices, converted to 16 kHz
mono PCM and duplicated with deterministic 10 dB white noise. Its strength is a
controlled, application-relevant comparison; its weakness is that synthetic
speech cannot represent natural hesitation, unexpected wording, microphone
distance, room acoustics or real accent diversity. A subsequent ten-participant
formative study recorded 70/70 successful core command outcomes with no retries;
the ten retained detailed rows had 2.00-second mean response time and a 4.90/5
mean rating. Because full row-level logs and standardised noise conditions were
not retained, this remains formative evidence. Full literature
selection, generation method, results and limitations are in
[Audio-model evaluation](docs/audio-model-evaluation.md).

## Reproducing the text-model evaluation

Install the three final cross-family candidates, then run the guarded system
benchmark:

```bash
ollama pull llama3.2:3b
ollama pull qwen2.5:3b
ollama pull phi3.5:3.8b
python backend/text_evaluation/evaluate_text_models.py \
  --output artifacts/text_model_evaluation_cross_family
```

The final comparison contains 16 model calls and two deterministic
poultry-safety cases per candidate. Llama 3.2 3B scored `0.944`; Qwen2.5 3B
scored `0.960`; and Phi-3.5 Mini 3.8B scored `0.704` and failed the structure
and constraint gates. The Llama/Qwen difference was inside the frozen `0.03`
practical tie, so Llama's lower matched-run latency selected it. An earlier
Llama 1B capacity screen is retained as preliminary evidence. Raw testing also
showed unsafe poultry answers from both eligible 3B models, which is why those
narrow questions bypass the LLM in production. See
[Text-model evaluation](docs/text-model-evaluation.md).

The text cases are a fixed, purpose-built MealMatch benchmark rather than a
public general language-model dataset. They were constructed to test the exact
recipe schema, pantry grounding, receipt filtering, dietary and allergy rules,
substitution ordering and step context used by the application. This gives
repeatable and directly relevant model-selection evidence, but the small
project-defined set cannot measure the diversity of real requests, recipe
appeal or conversational quality. A nine-participant formative validation of
the selected workflow found mean usefulness of 4.35/5 for AI recipes (`n=8`),
3.86/5 for substitutions (`n=7`) and 4.71/5 for the cooking assistant (`n=7`).
Missing ratings were not imputed, no timed user-test latency was available, and
the sessions were not a blinded comparison between candidate models.

## User-study measurements

Every pantry-photo analysis creates a privacy-preserving study record. The uploaded photograph is deleted after inference; the database retains suggestions, model warnings, inference time, confirmation time, additions, deletions, renames, final count and optional user confidence. Summary data is available from:

```text
GET /vision-study/{user_id}/summary
```

## Tests

From the repository root, with the backend environment active:

```bash
python -m unittest discover -s backend/tests -t .
cd frontend && npm test
```

The backend tests use a temporary database and mock every model, so they need neither Ollama nor the model downloads.

## Project documentation

- [Model orchestration](docs/model-orchestration.md)
- [Vision-model evaluation protocol](docs/vision-model-evaluation.md)
- [Vision evaluation results and detector rejection](docs/vision-evaluation-results.md)
- [Vision evaluation smoke results](docs/vision-evaluation-smoke-results.md)
- [Audio-model evaluation](docs/audio-model-evaluation.md)
- [Text-model evaluation](docs/text-model-evaluation.md)
- [Combined formative user-testing results](docs/user-testing-combined-results.md)
- [Accessibility, inclusion and software-testing evidence](docs/accessibility-and-testing.md)
- [Anonymised user-testing participant evidence](docs/user-testing-participant-evidence.md)
- [User-study participant information sheet](docs/user-study-participant-information-sheet.md)
- [User-study consent form](docs/user-study-consent-form.md)
- [User-study ethics and data-management plan](docs/user-study-ethics-data-plan.md)
- [User-study observer worksheet](docs/user-study-observer-worksheet.md)
- [Receipt extraction: design iteration 2](docs/receipt-extraction-iteration.md)
- [User testing round 1](docs/user-testing-round-1.md)
- [User testing round 2 plan](docs/user-testing-round-2-plan.md) and [results](docs/user-testing-round-2-results.md)
- [Design decision log](docs/decision-log.md)
