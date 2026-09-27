# MealMatch pre-trained model orchestration

MealMatch uses three primary pre-trained models in distinct data spaces. Each model is connected to a working feature and its output changes application behavior.

| Domain | Pre-trained model | User input | Model output | Product action |
| --- | --- | --- | --- | --- |
| Text | Ollama `llama3.2:3b` | Pantry-aware request or cooking question | Recipe JSON, substitutions, explanations, or assistant response | Creates validated recipes and answers within the correct pantry/recipe context |
| Image | Qwen2.5-VL 3B (selected household-photo variant) | Pantry or fridge photograph | Structured packaged and unpackaged ingredient suggestions | Opens a confirmation form; confirmed items are saved to the pantry |
| Audio | Whisper `small.en` via faster-whisper | Browser microphone recording | English transcript and language confidence | Powers continuous hands-free recipe navigation and questions in cooking mode, with an editable chat recorder as a secondary entry point |

Supporting models are `all-MiniLM-L6-v2` for semantic recipe retrieval and Tesseract LSTM English trained data for receipt OCR. YOLO-World is retained as a tested-and-rejected historical image baseline, not a runtime model.

## Orchestration flows

### Pantry photograph

1. The browser uploads a JPG, PNG, or WebP image to `/upload-image`. The photo is read into memory and the file is deleted at once.
2. Qwen2.5-VL 3B lists the visible packaged and unpackaged food in the whole photo. Its answer is streamed: every complete item is kept even if the answer is cut off, and an answer that starts repeating itself is stopped.
3. Code turns each answer into suggestions: brand, store and marketing words are removed, units are mapped onto the confirmation form's units, and non-food, vague and low-confidence items are dropped.
4. The whole-photo suggestions are shown for review. If the user presses "Look closer", the browser sends the same photo to `/upload-image/{scan_id}/close-ups` and the model looks at four overlapping close-ups. Each close-up adds only foods not listed yet, and a more specific name for a listed food is offered as a one-tap rename. Close-ups are not automatic because they added mostly wrong items on the frozen test and cost four more model runs.
5. The user edits or removes suggestions, adds missed items, enters quantities and expiry dates, optionally rates confidence, and confirms the list. They can confirm before the close-ups finish.
6. Only the confirmed list is posted to `/verify-ingredients/{user_id}` and saved. Correction counts, timings, each pass's result (how the answer ended, output length, items added) and whether the user asked for close-ups are retained for evaluation.

YOLO is not loaded, called or merged in this flow. The design history is in [user-testing-round-2-results.md](user-testing-round-2-results.md#photo-detection-iteration-1).

### Grocery receipt

1. The browser uploads a JPG or PNG receipt to `/upload-receipt`.
2. The image is straightened, converted to greyscale, contrast-stretched and upscaled, then read by Tesseract.
3. Deterministic code keeps only product lines, counts repeated lines, reads printed counts, weights and pack sizes, and expands abbreviations as hints.
4. Llama names each numbered line and marks it as food or not through a fixed JSON schema, so it cannot skip or add lines. A name guard keeps words the model dropped, and a whole-word denylist removes non-food products.
5. Lines naming the same ingredient and unit are merged into one row with the quantities added. Each row shows the receipt text it came from.
6. The user edits and confirms the rows as in the photo flow. The receipt image is deleted after processing.

The design history is in [receipt-extraction-iteration.md](receipt-extraction-iteration.md).

### Voice cooking assistance

1. After “I’m cooking this”, the user says “Hey Mimi” or taps Start voice. The browser asks for microphone access the first time; if it is refused, the panel says how to allow it.
2. Browser audio analysis detects when speech begins and automatically ends an utterance after a pause, without requiring another tap.
3. `/transcribe-audio` processes the temporary recording using Whisper and immediately deletes the audio file.
4. `frontend/src/voiceCommands.ts` turns each transcript into one action, so what Mimi says and what the step card shows always agree. Any phrase with “next” moves the card; so do go back, go to step N, repeat and time remaining. On the last step, “done”, “finished” or “the meal is ready” finish the meal like the “Meal is ready” button. Finishing early and cancelling require spoken confirmation.
5. Open-ended questions go to Llama with the recipe, ordered instructions, and current step as context.
6. Explicitly labelled poultry-temperature and raw-poultry washing questions are intercepted by deterministic safety rules because candidate-model testing found contradictory unsafe answers; those two cases do not invoke an LLM.
7. Browser speech synthesis reads steps and answers aloud with the highest-scored installed natural English voice, warmer pacing, and speech-friendly phrasing. The user can override the device voice and the choice is remembered locally.
8. A visible status indicator and stop control keep microphone use explicit. The Assistant tab retains its editable push-to-talk composer as a secondary Whisper workflow.

### Text generation and recommendation

1. MiniLM retrieves semantically related recipes and deterministic ingredient matching calculates pantry coverage.
2. Allergy conflicts are removed. Recipes that break a saved diet are listed only after every recipe that fits, and say which diet they break.
3. Recipes that use food due within five days come first, the food due soonest counting most; pantry coverage, cuisine preference and semantic similarity follow.
4. Llama generates explanations, substitutes, or a new structured recipe when explicitly requested. For a new recipe it is offered only the pantry foods that belong in the requested dish; a dessert is never offered savoury food.
5. Generated recipes and substitutions are post-validated against saved dietary restrictions and allergies. A recipe is regenerated when it does not match the taste asked for (a savoury food in a dessert, nothing sweet in a sweet dish, or a dessert food in a savoury one), when its title names a pantry food it does not use, or when it repeats an idea already shown. Swaps come from the pantry and a table of standard substitutions first; the text model is asked only about ingredients those do not cover. AI recipes show their main ingredients as emojis; no image model is used.

## Model loading and evidence

`python backend/setup_models.py` installs every pretrained model at the version pinned in `backend/model_versions.py`: it pulls missing Ollama models and checks installed ones against their recorded digests, and downloads Whisper and the recipe-matching embedding model at fixed commits into a local cache. The rejected 25 MB YOLO-World checkpoint remains under `backend/weights` solely to preserve the completed detector experiment and is excluded from runtime setup checks. Other large model and evaluation artifacts are not committed. The interface shows animated loading and explicit model warnings instead of silently failing.

Technical verification completed through 24 September 2026:

- The frozen benchmark contained 2,131 train, 504 validation and 530 untouched test images across 27 Open Images food classes, with no image overlap across splits.
- Grounding DINO beat YOLO-World in the controlled zero-shot comparison; the separately fine-tuned YOLO-World checkpoint then achieved the best detector-benchmark result: test mAP@0.50 `0.244`, precision `0.399`, recall `0.288`, NDCG `0.461`, and mean model latency `24.7 ms` on the reference M4 Pro.
- A 500-resample paired bootstrap placed the fine-tuned detector's mAP@0.50 advantage over zero-shot Grounding DINO between `+0.026` and `+0.108` at 95% confidence.
- Formative use with actual household photos then exposed severe detector domain shift, including low recall and banana false positives. YOLO was removed from production and the final image decision was narrowed to Qwen2.5-VL 3B versus 7B on a frozen household set.
- The frozen household test contained 35 independently labelled images, each processed three times by both Qwen variants. 3B achieved precision `0.334`, recall `0.163`, F1 `0.219`, zero failures and 7.2-second median latency. 7B achieved F1 `0.253`, but its `6.7%` failure rate exceeded the predeclared `5%` gate and its median latency was 44.7 seconds; 3B was therefore selected.
- A post-selection Open Images check used the same deterministic 50-image, 27-class subset for both variants. 7B substantially outperformed 3B on this constrained public task (F1 `0.857` versus `0.411`) and neither failed, but this does not override the household reliability gate. The contrast is retained as evidence of distribution-dependent performance rather than hidden.
- A preliminary capacity screen compared Whisper `tiny.en`, `base.en` and `small.en` across 108 app-specific clean/noisy clips each. A final breadth comparison then evaluated the winning `small.en` checkpoint against Distil-Whisper `small.en` and wav2vec 2.0 Base 960h on the unchanged manifest. Only Whisper passed both intent gates: WER `0.046`, overall intent `95.4%`, noisy intent `92.6%`, with no failures. Distil-Whisper reached `81.5%` noisy intent and wav2vec 2.0 reached `31.5%`, so both were rejected despite lower latency.
- The final guarded text-system comparison used 18 cases for three distinct local families. Llama 3.2 3B scored `0.944`, Qwen2.5 3B scored `0.960`, and Phi-3.5 Mini 3.8B scored `0.704`; Phi failed the structured-output and constraint gates. The eligible Llama and Qwen candidates were inside the frozen `0.03` practical tie, so lower matched-run median latency selected Llama 3.2 3B (1.11 seconds versus 1.53 seconds). The previously tested Llama 1B remains a rejected capacity-screening baseline. Both raw eligible 3B models failed one of two critical poultry questions before deterministic interception; those failures are retained in the report rather than attributed to the selected model.
- An isolated integration test verified dietary filtering, recommendation order, shopping-list persistence, varied timing, image/audio endpoint wiring, and AI recipe creation.

The full detector evidence, subsequent product rejection and replacement protocol are in [vision-evaluation-results.md](vision-evaluation-results.md) and [vision-model-evaluation.md](vision-model-evaluation.md). The audio protocol and results are in [audio-model-evaluation.md](audio-model-evaluation.md), and the text comparison is in [text-model-evaluation.md](text-model-evaluation.md).

## Limitations and safety

- Vision detections can be wrong, particularly for packaged, hidden, or prepared food. Human confirmation is mandatory.
- Speech can be affected by noise and accents. Hands-free transcripts remain visible for review, and the Assistant-tab transcript is editable before submission.
- Allergy rules reduce risk but MealMatch is not medical advice and cannot guarantee an allergen-free meal.
- Llama output is validated structurally and against saved preferences, but generated recipes still require ordinary food-safety judgement.
