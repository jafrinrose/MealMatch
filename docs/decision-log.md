# MealMatch Design Decision Log

## Decision 1: Use SQLite for the MVP database

**Date:** 29 June 2026

**Options considered:**

* SQLite
* PostgreSQL
* Supabase PostgreSQL

**Chosen option:** SQLite

**Reason for choice:**
SQLite was selected for the local MVP because it requires no separate database server, no port forwarding, and no cloud configuration. This makes it easier to set up, demonstrate, and debug during prototype development. It is sufficient for storing users, pantry items, recipes, ingredient ratings, and saved recipes during the coursework prototype stage.

**Evidence from prototype:**
The FastAPI backend successfully writes pantry ingredients to the `pantry_items` table. DBeaver was connected directly to the local `mealmatch.db` file, allowing live inspection of database updates after manual ingredient entry and human verification.

**Trade-offs:**
SQLite is not ideal for high-concurrency production use. If the project is expanded into a deployed multi-user system, PostgreSQL would be more suitable.

**Report relevance:**
This supports the design section by showing that database choice was based on MVP feasibility and local reproducibility.

---

## Decision 2: Use FastAPI for the backend

**Date:** 29 June 2026

**Options considered:**

* FastAPI
* Flask
* Node/Express

**Chosen option:** FastAPI

**Reason for choice:**
FastAPI was selected because the AI components are Python-based, including Sentence Transformers, FAISS, EasyOCR, and future OCR/image-processing tools. FastAPI also provides automatic Swagger documentation, which made it easy to test endpoints such as `/pantry/{user_id}`, `/recommend/{user_id}`, and `/verify-ingredients/{user_id}`.

**Evidence from prototype:**
Swagger UI was used to test database operations, recommendation endpoints, image upload, and Ollama explanation routes before connecting the frontend.

**Trade-offs:**
FastAPI requires some care with route definitions. During development, a route decorator was accidentally attached to a helper function, causing `/pantry/1` to return a 422 error. This was fixed by separating helper functions from API route functions and ensuring each endpoint had a clear purpose.

**Report relevance:**
This can be discussed in the prototype evaluation as an implementation issue discovered and resolved during development.

---

## Decision 3: Separate AI prediction from database storage using human-in-the-loop verification

**Date:** 29 June 2026

**Options considered:**

* Automatically save AI-detected ingredients
* Require user verification before saving detected ingredients

**Chosen option:** Human verification before database storage

**Reason for choice:**
AI ingredient detection may be inaccurate, especially for noisy inputs such as receipts or pantry images. To reduce the risk of incorrect ingredients being used for recommendations, AI-suggested ingredients are shown to the user first. The user can edit, delete, or add ingredients before confirming them.

**Evidence from prototype:**
The current frontend implements a human verification section. Mock AI ingredient suggestions are displayed as editable fields. Only after the user confirms them are the ingredients saved to the SQLite pantry table through `/verify-ingredients/{user_id}`.

**Trade-offs:**
This adds an extra step for the user, but it improves trust, transparency, and data quality.

**Report relevance:**
This is one of the main feature prototype contributions because it shows how the system handles AI uncertainty.

---

## Decision 4: Use mocked image ingredient detection before integrating real OCR/vision models

**Date:** 29 June 2026

**Options considered:**

* Build real pantry image recognition immediately
* Build real OCR immediately
* Mock ingredient detection first to complete the end-to-end workflow

**Chosen option:** Mock image detection first

**Reason for choice:**
The human-in-the-loop workflow is required regardless of which AI input model is used. Mocking image detection allowed the upload → suggestion → verification → database update → recommendation flow to be implemented and tested before adding real OCR or image recognition models.

**Evidence from prototype:**
The `/upload-image` endpoint currently returns mock detected ingredients such as `chicken`, `rice`, and `spinach`. These suggestions are not saved automatically. They are passed into the verification layer first.

**Trade-offs:**
The current image detection is not yet a real AI model. This must be clearly stated as a prototype limitation. The next step is to replace the mock output with EasyOCR-based receipt extraction and later pantry image recognition.

**Report relevance:**
This should be mentioned honestly in the prototype evaluation: the workflow is implemented, while the image detection model remains a planned improvement.

---

## Decision 5: Use hybrid retrieval instead of embedding-only recipe retrieval

**Date:** 29 June 2026

**Options considered:**

* Keyword-only recipe matching
* Embedding-only FAISS retrieval
* Hybrid exact ingredient matching + FAISS semantic retrieval

**Chosen option:** Hybrid exact ingredient matching + FAISS semantic retrieval

**Reason for choice:**
Initial testing showed that embedding-only retrieval could return unsuitable recipes when the recipe dataset was small. For example, when the user entered `yogurt`, `oats`, `berries`, and `granola`, the system initially returned unrelated seed recipes or no useful recommendations. Exact ingredient matching was added to ensure obvious pantry matches are not missed.

**Evidence from prototype:**
The recommendation route now combines:

1. Exact ingredient-overlap candidates
2. FAISS semantic candidates
3. A ranking formula that filters out recipes with zero ingredient match

This improved recommendations for breakfast ingredients once breakfast recipes were added to the database.

**Trade-offs:**
Hybrid retrieval is slightly more complex than pure semantic search, but it is more reliable for ingredient-based recommendation.

**Report relevance:**
This is strong evidence of design iteration and evaluation. It shows that the retrieval strategy was improved based on observed prototype behaviour.

---

## Decision 6: Use a custom ranking formula for recommendation ordering

**Date:** 29 June 2026

**Options considered:**

* Return recipes directly from FAISS similarity order
* Use only ingredient overlap
* Use a weighted ranking formula

**Chosen option:** Weighted ranking formula

**Reason for choice:**
Recipe recommendation should consider more than semantic similarity. The ranking formula allows the system to combine ingredient match, user preferences, dietary compatibility, cooking time, and variety.

**Current ranking factors:**

* Ingredient match score
* Preference score
* Dietary compatibility
* Cooking time score
* Variety score

**Evidence from prototype:**
The frontend displays score details for each recommended recipe, including matched ingredients and score breakdown. This makes the recommendation process more transparent.

**Trade-offs:**
Some factors, such as user preferences and dietary needs, are not fully meaningful until onboarding and ingredient rating features are implemented. For now, these are partly neutral/default values.

**Report relevance:**
The ranking formula should be explained in the prototype chapter with a small code snippet and a diagram.

---

## Decision 7: Use Ollama for local LLM explanations

**Date:** 29 June 2026

**Options considered:**

* OpenAI API
* Ollama with local models
* No LLM explanation

**Chosen option:** Ollama with `llama3.2`

**Reason for choice:**
Ollama allows the prototype to run locally without paid APIs. This fits the requirement to use free tools and makes the project easier to demonstrate without relying on cloud billing or external API keys.

**Evidence from prototype:**
The endpoint `/explain-recommendation/{user_id}/{recipe_id}` sends the recipe, user pantry ingredients, and score details to Ollama. The frontend displays the LLM explanation directly under each recipe card.

**Trade-offs:**
Local LLM responses can be slower than cloud APIs and depend on the user’s machine. However, the user’s M4 Pro MacBook is able to run `llama3.2` locally.

**Report relevance:**
This supports the AI orchestration claim because the system combines retrieval, ranking, and natural-language explanation.

---

## Decision 8: Use seed recipes during development before importing a larger recipe dataset

**Date:** 29 June 2026

**Options considered:**

* Start immediately with a large open-source recipe dataset
* Use a small hardcoded seed dataset first

**Chosen option:** Small seed dataset during development

**Reason for choice:**
A small seed dataset made it easier to debug the database, recommendation logic, ranking scores, and frontend display. It allowed problems in the pipeline to be identified quickly.

**Evidence from prototype:**
The small seed dataset revealed that recommendations could appear fixed or irrelevant when the database lacked recipes matching the user’s pantry. Breakfast recipes were added to test the system with ingredients such as `yogurt`, `oats`, `berries`, and `granola`.

**Trade-offs:**
A small seed dataset limits recommendation realism. The final prototype should import a larger open-source recipe dataset and precompute embeddings for more diverse recommendations.

**Report relevance:**
This should be included in the prototype evaluation as a limitation and planned improvement.

## Decision 9: Add EasyOCR for receipt-based ingredient extraction

**Options considered:**
- Continue using mock image detection only
- Use EasyOCR for receipt OCR
- Use Tesseract OCR
- Use pantry object detection first

**Chosen option:** EasyOCR for receipt OCR

**Reason for choice:**
Receipt OCR is a more reliable first AI input feature than pantry image recognition because receipts contain text labels for purchased ingredients. EasyOCR integrates directly into the Python FastAPI backend and can extract receipt text from uploaded images.

**Evidence from prototype:**
The `/upload-receipt` endpoint accepts a receipt image, extracts raw text lines using EasyOCR, parses possible ingredient candidates, and sends them to the human verification screen. Ingredients are not saved until the user confirms them.

**Trade-offs:**
OCR output can include noisy receipt text such as totals, payment information, and abbreviations. A parser and human verification step are needed to clean the output. The current ingredient parser uses a simple dictionary and will need expansion.

**Future improvement:**
Compare EasyOCR with Tesseract on a small set of receipt images using extraction accuracy, correction rate, and setup difficulty.

## Decision 10: Replace EasyOCR backend integration with Tesseract CLI for the MVP

**Problem discovered:**
EasyOCR integration caused the FastAPI backend to crash with a macOS segmentation fault. The crash report showed native library failure involving `libomp.dylib` and PyTorch-related libraries. This made the backend unreliable during `/upload-receipt` testing.

**Options considered:**
- Continue debugging EasyOCR inside FastAPI
- Run EasyOCR as a separate subprocess
- Use Tesseract CLI for the MVP OCR feature
- Delay OCR and keep mock image detection only

**Chosen option:**
Use Tesseract CLI for the MVP OCR feature.

**Reason for choice:**
Tesseract is free, local, installable through Homebrew, and can be called as a command-line subprocess. This reduces the risk of crashing the FastAPI backend because OCR runs outside the main Python process. It also keeps the prototype easier to demonstrate reliably.

**Evidence from prototype:**
Swagger returned “Failed to fetch” because the backend process crashed during `/upload-receipt`. After reviewing the crash, the problem appeared to be native ML/OCR dependency instability rather than a frontend or CORS issue.

**Trade-offs:**
Tesseract may be less flexible than EasyOCR for messy receipt images, and OCR accuracy may depend on receipt quality. However, its reliability makes it more suitable for the local MVP.

**Future improvement:**
Compare Tesseract and EasyOCR using the same receipt images in a separate `experiments/ocr_comparison/` folder. Measure raw text extraction quality, ingredient detection accuracy, correction rate, speed, and setup difficulty.

## Decisiom
Tesseract is used for optical character recognition.
The extracted receipt text is passed to a local LLM through Ollama.
The LLM interprets noisy receipt text and extracts likely grocery ingredients.
The user then verifies the extracted ingredients before they are stored.

## Decision: Replace hardcoded OCR ingredient parser with Ollama-based semantic parsing

During receipt OCR testing, Tesseract successfully extracted raw receipt text, but the rule-based ingredient parser became too specific to the test receipts. Adding more aliases and exceptions risked making the prototype brittle and less generalisable.

The design was changed so that Tesseract is responsible only for OCR text extraction, while Ollama is used to semantically interpret the receipt text and return likely grocery ingredients as a JSON array. This better matches the project aim of orchestrating AI models because the system now combines OCR, LLM-based text understanding, human verification, database persistence, and recipe recommendation.

The trade-off is that LLM extraction may still make mistakes, so ingredients are not saved automatically. They are passed into the human-in-the-loop verification screen before being stored in SQLite.

## Decision: Focus preliminary prototype on receipt OCR rather than pantry image recognition

The original MealMatch concept included multiple ingredient input methods, including pantry/fridge image recognition and receipt scanning. During prototype development, receipt OCR was prioritised for the preliminary submission because it provides a more reliable and feasible way to extract ingredient information from real user input.

Pantry image recognition remains a planned future feature, but it is more technically complex because food items may be partially hidden, packaged, visually similar, or affected by lighting and camera angle. Receipt OCR allows the prototype to demonstrate the core AI orchestration pipeline now: OCR text extraction, LLM-based ingredient interpretation, human verification, database storage, recommendation ranking, and LLM explanation.

This decision keeps the MVP focused while still satisfying the requirement to implement an important technical feature that demonstrates project feasibility.

## Decision
The current prototype uses a small curated recipe dataset designed to test the full end-to-end pipeline using ingredients extracted from the receipt examples used during development. This was chosen for the preliminary prototype because the main aim at this stage is to demonstrate technical feasibility: receipt upload, OCR text extraction, LLM-based ingredient interpretation, human verification, pantry storage, recommendation ranking, and explanation generation.

A limitation of this approach is that recommendation coverage depends on the size and diversity of the recipe database. If the user enters ingredients that are not well represented in the current dataset, the system may return few or no suitable recipes. In the next stage, the curated seed data will be replaced or expanded with a larger open-source recipe dataset, such as TheMealDB, Food.com Recipes, or RecipeNLG. This would improve recipe variety, allow more robust testing of the recommendation engine, and make the system more realistic for broader user use.

## Decision 11: Restructure the prototype as a responsive multi-screen application

**Date:** 9 September 2026

**Chosen option:** Use a shared responsive application shell with Home, Pantry, Recipes, Assistant, and Settings screens.

**Reason for choice:**
The previous frontend placed every workflow on one long page. The new structure follows familiar mobile application patterns, gives each task a clear destination, and uses the same React components and data on desktop and mobile. Desktop uses persistent side navigation, while smaller screens use a fixed bottom tab bar.

**Evidence from prototype:**
The app now opens with a session-based welcome screen, then provides five navigable screens. Pantry search, category filtering, ingredient add/edit, receipt verification, recipe search, cooking assistance, theme selection, and cooking preferences are all available within the new shell. Pantry and preference changes continue to be stored through the FastAPI and SQLite layers.

**Trade-offs:**
The prototype continues to use one demonstration user rather than a complete authentication system. The entry screen is remembered for the current browser session, while saved cooking data remains available in SQLite across sessions.

## Decision 12: Deduct pantry quantities when a user starts a recipe

**Date:** 9 September 2026

**Chosen option:** Add a dedicated cooking endpoint that updates pantry quantities transactionally.

**Reason for choice:**
Opening a recipe should lead to an actionable cooking flow, not only display a recommendation. The detailed recipe screen now shows ingredient quantities, serving controls, and ordered instructions. When the user selects “I’m cooking this”, the backend deducts matched ingredient quantities and removes exhausted pantry records.

**Safety rule:**
Quantities are deducted only when the recorded pantry unit is compatible with the recipe unit. If the units are incompatible, the recorded quantity is left unchanged rather than applying an unsafe conversion. Ingredients recorded without a numeric quantity are treated as a single available pantry entry and removed once used.

**Current limitation:**
The curated recipe records store comma-separated ingredient names but not structured quantities. The MVP therefore uses a canonical quantity table for known ingredients. A larger production dataset should store recipe ingredients as structured amount-and-unit records and introduce explicit unit conversion.

**Revision on 28 September 2026:** Superseded by [Decision 40](#decision-40-update-the-pantry-when-the-meal-is-ready-with-unit-conversion): the pantry changes when the meal is ready, with unit conversion.

## Decision 13: Make semantic recommendation loading optional at API startup

**Date:** 9 September 2026

**Chosen option:** Load the sentence-transformer model lazily from local files and fall back to exact ingredient matching when it is unavailable.

**Reason for choice:**
The earlier implementation loaded the Hugging Face model during Python module import, which could prevent the entire API from starting without a network connection. Lazy local loading keeps pantry, preferences, recipes, and cooking features available offline. If the cached semantic model is present, the hybrid retrieval strategy still uses it.

## Decision 14: Rank recipes with pantry, expiry, cuisine, and safety signals

**Date:** 10 September 2026

**Chosen option:** Apply hard allergy and dietary exclusions before using a weighted personalised score.

**Initial ranking weights:** Ingredient availability 45%, expiring-ingredient coverage 20%, cuisine preference 15%, semantic similarity 10%, cooking-time fit 5%, and previous recipe rating 5%.

**Revision on 12 September 2026:** The displayed score now uses ingredient availability 60%, expiry coverage 25%, cuisine preference 10%, and cooking-time fit 5%. Final ordering is lexicographic rather than score-only: pantry coverage first, matched ingredient count second, expiring-food use third, cuisine preference fourth, and MiniLM semantic similarity as a final tie-breaker. This guarantees the priority order required by the product instead of allowing a lower-priority weighted signal to overtake pantry coverage.

**Reason for choice:**
Allergies and dietary restrictions are safety constraints rather than preferences, so conflicting recipes are removed instead of merely ranked lower. Among eligible recipes, pantry coverage has the largest influence and recipes that use expiring ingredients are placed first. The API stores each score component, missing ingredient, and matched expiring ingredient so the interface can explain the result rather than present a black-box score.

**Limitation:**
Ingredient aliases and dietary conflict rules are deterministic prototype logic. They should be expanded and clinically reviewed before the application is presented as an allergy-safety tool.

## Decision 15: Use layered receipt filtering and keep human verification

**Date:** 10 September 2026

**Chosen option:** Combine Tesseract OCR, a food-only Ollama extraction prompt, a deterministic non-food denylist, and a user verification screen.

**Reason for choice:**
No individual OCR or language model can guarantee that soap, detergent, paper goods, or toiletries will never be mistaken for food. The post-processing denylist catches common household products even if the language model includes them, while the verification step prevents automatic pantry writes.

**Trade-off:**
Unfamiliar food names may require manual correction and an exhaustive food/non-food classifier remains future work.

## Decision 16: Make cooking a persistent, reversible session

**Date:** 10 September 2026

**Chosen option:** Store the active recipe, start/ready times, current step, assistant messages, and a pantry-change snapshot in SQLite.

**Reason for choice:**
The cooking flow now survives refreshes and gives the assistant a single-recipe context. Starting a recipe deducts compatible pantry quantities, the total prep-and-cook countdown continues from its stored start time, and “Changed my mind” restores the captured pantry state. Completing the recipe keeps the deductions.

**Safety rule:**
Only one cooking session can be active for a user at a time, preventing overlapping deductions and ambiguous assistant context.

**Revision on 28 September 2026:** Deductions now happen at "Meal is ready", so "Changed my mind" has nothing to restore ([Decision 40](#decision-40-update-the-pantry-when-the-meal-is-ready-with-unit-conversion)).

## Decision 17: Combine a real recipe source with optional local AI generation

**Date:** 10 September 2026

**Chosen option:** Import structured meals and image URLs from TheMealDB, while allowing Ollama to generate a pantry-aware recipe when requested.

**Reason for choice:**
The imported dataset gives the prototype real recipe names, source instructions, ingredient measures, cuisines, and food photography. AI generation adds flexibility for unusual pantry combinations. Generated recipes pass through the same dietary, allergy, and pantry validation used by the recommender before being saved.

**Trade-offs:**
TheMealDB images require an internet connection because the database stores their remote URLs. Generated recipes still require user judgement and should not be treated as authoritative food-safety guidance.

## Decision 18: Add durable saved recipes and custom preferences

**Date:** 10 September 2026

**Chosen option:** Save recipe bookmarks in SQLite and support user-entered allergy and cuisine values alongside the predefined options.

**Reason for choice:**
Bookmarks must remain available across sessions and screens, so they are stored by user and recipe rather than only in browser state. Custom preference chips preserve answers that do not fit the initial taxonomy and feed into the same ranking and exclusion logic.

## Decision 19: Use three pre-trained models across text, image, and audio

**Date:** 12 September 2026

**Chosen models:** Llama 3.2 for language reasoning, YOLO-World `yolov8s-worldv2.pt` for visual food detection, and Whisper `base.en` through faster-whisper for speech recognition.

**Reason for choice:**
These models operate on three visibly different input spaces and each powers a user-facing workflow. Llama interprets and generates cooking text, YOLO-World turns pantry photographs into confidence-scored ingredient suggestions, and Whisper turns microphone recordings into editable cooking questions. MiniLM semantic retrieval and Tesseract receipt OCR remain supporting pre-trained models.

**Human-in-the-loop rule:**
YOLO detections are suggestions only. The user must confirm the ingredient name and quantity, supply an expiry date, and can remove false detections before anything is written to SQLite.

**Trade-offs:**
The first image or audio request may take longer while weights load. Model weights are cached locally but excluded from version control because of their size. Ultralytics licensing must be reviewed before any commercial distribution; this implementation is for the educational prototype.

**Revision on 20 September 2026:** Decision 26 supersedes the zero-shot image checkpoint choice. The selected fine-tuned YOLO-World checkpoint is small enough to bundle so a fresh clone uses the exact evaluated model; other downloaded weights remain excluded.

## Decision 20: Make dietary rules hard filters and rank pantry coverage first

**Date:** 12 September 2026

**Chosen order:** Remove allergy and dietary conflicts, then order eligible recipes by pantry coverage, number of matched pantry ingredients, expiring-ingredient use, cuisine preference, and finally semantic similarity.

**Reason for choice:**
A vegetarian recipe requirement is not a soft preference. Unsafe or incompatible recipes must not reappear when the unranked catalog is appended to the recommendation result. Both the recipe browsing endpoint and recommendation endpoint now apply the same safety filter.

**Revision on 28 September 2026:** See [Decision 38](#decision-38-diet-rules-as-hard-filters-with-a-labelled-fallback-and-use-soon-food-first): diet conflicts follow every fitting recipe, labelled; use-soon food now ranks first.

## Decision 21: Separate general assistant context from active cooking context

**Date:** 12 September 2026

**Chosen option:** Use the selected recipe only while a persistent cooking session is active; otherwise call a pantry-aware general assistant endpoint.

**Reason for choice:**
The previous general chat silently attached the first recommended recipe, which made the assistant claim the user was cooking something they had not selected. Completing a session now clears the conversation in the client, and the Assistant screen provides an explicit “I’ve finished cooking” control for stale sessions.

## Decision 22: Persist missing ingredients as a shopping list

**Date:** 12 September 2026

**Chosen option:** Store shopping-list rows in SQLite by user and source recipe.

**Reason for choice:**
Recipe details can add only currently missing ingredients, avoid duplicate unchecked items, preserve quantities, and allow items to be checked across browser sessions. Substitute suggestions are generated by Llama when available, have deterministic fallbacks, and are post-filtered against allergy and dietary rules.

## Decision 23: Store or estimate per-step cooking durations

**Date:** 12 September 2026

**Chosen option:** Preserve distinct AI-provided step durations and estimate varied durations for imported recipes using explicit timing phrases and action types.

**Reason for choice:**
Evenly dividing total recipe time made every step misleadingly identical. Simmering, baking, preparation, and serving now receive different estimates, and the same values appear in recipe details and cooking mode.

## Decision 24: Make hands-free cooking the primary Whisper workflow

**Date:** 18 September 2026

**Chosen option:** Enable continuous utterance-based voice control inside an active cooking session, while keeping push-to-talk transcription in the general Assistant screen.

**Reason for choice:**
Speech recognition is most useful when the user is actively cooking and cannot safely touch the device. After one explicit enable action, browser voice activity detection stops each recording after a pause, Whisper transcribes it, and MealMatch resumes listening after responding. Navigation and state-changing commands use deterministic routing, while open cooking questions use Llama with the current recipe step attached.

**Safety and privacy rules:**
Finish and cancel require spoken confirmation. Audio recordings are deleted immediately after local transcription, microphone state remains visible, and the user can stop listening at any time. Browser speech synthesis provides spoken feedback so the workflow does not require reading the screen.

**Fallback:**
Every voice-controlled operation remains available through visible buttons, and the Assistant tab retains editable transcription for browsers or environments where continuous microphone access is unavailable.

**Revision on 28 September 2026:** See [Decision 39](#decision-39-one-action-per-voice-command-finishing-by-voice-and-a-reliable-wake-word).

**Voice quality revision:**
MealMatch ranks the English voices installed by the browser or operating system, preferring natural, neural, premium, or enhanced voices and known high-quality platform voices. It uses slower conversational pacing, expands awkward abbreviations before speaking, and exposes a persistent voice selector because the exact voices available differ by device.

---

## Decision 25: Evaluate open-vocabulary detectors and use a local VLM as a packaged-food fallback

**Date:** 19 September 2026

**Options considered:**

* YOLO-World v2 as the only photo model
* Zero-shot comparison of YOLO-World v2 and Grounding DINO Tiny
* RT-DETR-L fine-tuned as a fixed-vocabulary detector
* General vision-language detection without a dedicated object detector
* A hybrid dedicated-detector and vision-language workflow

**Chosen option:** Evaluate YOLO-World v2 against Grounding DINO Tiny on an official Open Images subset, then use the selected detector with local `qwen2.5vl:3b` as a semantic fallback.

**Reason for choice:**
YOLO-World and Grounding DINO both accept open text vocabularies, enabling a controlled zero-shot comparison on the same pantry-food classes. The ordinary RT-DETR checkpoint has a fixed pre-training vocabulary and would require task-specific fine-tuning, so including it in the same zero-shot table would not be a like-for-like comparison. A general vision-language model is useful for visible labels and branded packages but does not replace bounding-box evaluation. The hybrid design covers both localization and package semantics while maintaining human control.

**Evidence plan:**
The reproducible pipeline uses official Open Images boxes, validation-only threshold selection, an untouched test split, mAP, precision, recall, NDCG, confusion matrices and deterministic lighting/blur robustness conditions. The live application separately records user corrections, confirmation time, failures and confidence in household scenes.

**Trade-offs:**
Local inference requires model downloads and sufficient memory. Qwen output can still hallucinate and detector counts can be wrong, so no suggestion is saved until the user confirms it. Commercialisation would require a fresh review of model, code and dataset licences.

**Report relevance:**
This provides a documented chain from literature review, through model screening and controlled technical testing, to user testing and design iteration.

---

## Decision 26: Deploy the fine-tuned YOLO-World food checkpoint

**Date:** 20 September 2026

**Evidence considered:**

* 3,165 Open Images photographs across frozen train, validation and test splits
* zero-shot YOLO-World v2 versus Grounding DINO Tiny
* validation-only confidence-threshold selection
* untouched test metrics, class-level results and confusion matrices
* deterministic dark, bright and blur conditions
* 20-epoch YOLO-World transfer learning from pretrained weights
* a 500-resample paired bootstrap against the strongest zero-shot detector

**Chosen option:** Bundle and deploy the fine-tuned YOLO-World v2 checkpoint at a confidence threshold of `0.25`, with Qwen2.5-VL retained as the packaged-food semantic fallback and mandatory user confirmation retained before pantry writes.

**Reason for choice:**
Fine-tuned YOLO-World achieved test mAP@0.50 `0.244`, precision `0.399`, recall `0.288`, F1 `0.335`, NDCG `0.461` and mean model latency `24.7 ms`. Grounding DINO was the strongest zero-shot model at mAP@0.50 `0.181`, but required `571.7 ms` per image. The paired 95% interval for the fine-tuned model's mAP@0.50 advantage was `+0.026` to `+0.108`; its precision, F1 and NDCG differences were also positive throughout their intervals.

**Qualification:**
The mAP@0.50:0.95 difference interval crossed zero, as did the recall difference at its lower edge. Some classes remained weak or undetected. The result supports choosing a detector for a review workflow, not trusting it as autonomous inventory recognition.

**Operational consequence:**
The exact 25 MB selected checkpoint is stored in `backend/weights`, its checksum is verified by `backend/setup_models.py --check`, and the runtime preserves its evaluated 27-class vocabulary. The former zero-shot checkpoint remains an explicit environment override rather than the default.

**Remaining evidence:**
The technical model comparison is complete. A participant study using actual fridges, pantry shelves and groceries on tables is still required to measure correction effort, failure rate, confidence and design iteration. No user-study result is claimed before participants perform it.

**Commercialisation note:**
The current use is a non-commercial academic prototype. Ultralytics, upstream checkpoint and per-image Open Images licences must be reviewed again before any commercial release.

---

## Decision 27: Reject YOLO for household deployment and evaluate Qwen variants

**Date:** 21 September 2026

**Supersedes:** The production deployment portion of Decisions 25 and 26. Their
experiments, measurements and original reasoning remain part of the evidence.

**New evidence:**
Formative use with user-supplied refrigerator, pantry and grocery-table images
showed that the fine-tuned detector often returned only one or two ingredients,
missed unlabelled fridge contents, and sometimes predicted banana in images
without bananas. In a retained cluttered grocery-table example it returned only
pineapple and banana at the deployed threshold; lowering the threshold did not
recover the wider inventory. Qwen 3B was also incomplete, but was more useful
when product labels were visible.

**Decision:**
Remove YOLO from the live application rather than maintain an unhelpful merge
architecture. Preserve the checkpoint, scripts and detector reports strictly as
tested-and-rejected evidence. Promote Qwen2.5-VL to the sole pantry-photo model,
retain mandatory human confirmation, and limit the final replacement experiment
to Qwen2.5-VL 3B versus 7B on the same frozen household-photo set.

**Reason for choice:**
The Open Images benchmark answered a conventional localization question, while
MealMatch needs open-ended ingredient extraction from crowded household scenes,
including visible package text. The failed deployment check is evidence of
domain shift, not a reason to erase the earlier experiment. A focused 3B/7B
comparison is easier to defend than continually adding unrelated architectures.

**Operational consequence:**
The runtime no longer imports Ultralytics, loads the checkpoint, produces YOLO
boxes or merges detector and VLM output. Ultralytics dependencies live in the
optional evaluation requirements. At this decision stage, `qwen2.5vl:3b` was a
provisional runnable default pending the frozen test; Decision 28 later selected
and finalised that variant.

**Selection evidence still required:**
Build and independently label a consented household dataset, freeze the prompt
after development, run both variants three times on the test split, and compare
ingredient precision, recall, F1, hallucinations, misses, failures, latency,
repeatability and packaged/unpackaged subgroups. Then update the runtime default
to the winner and run participant correction-time and confidence testing.

---

## Decision 28: Select Qwen2.5-VL 3B for household photo extraction

**Date:** 23 September 2026

**Completes:** The replacement-model selection required by Decision 27.

**Evidence considered:**

* 51 collected household photographs, with three exact duplicates and one
  unscorable opaque-bag image retained in an exclusion log
* 12 development images used for prompt and preprocessing iteration
* 35 frozen test images with verified ingredient labels and complete metadata
* independent second-person agreement on a stratified nine-image test sample
* three repeated inferences per test image and model, totalling 210 calls
* ingredient precision, recall, F1, false suggestions, misses, empty responses,
  failures, latency, Jaccard repeatability and scene/packaging/difficulty groups
* 2,000 paired image-cluster bootstrap resamples

**Predeclared rule:**
A candidate must have at most `5%` failures and at most 45 seconds median
latency. Select the eligible candidate with the highest ingredient F1, applying
the recorded tie-breaks only if more than one eligible model is practically
tied.

**Results:**
Qwen2.5-VL 3B achieved precision `0.334`, recall `0.163`, F1 `0.219`, zero
failures, 7.2-second median latency, 137.8-second p95 and repeatability `0.679`.
Qwen2.5-VL 7B achieved precision `0.252`, recall `0.254`, F1 `0.253`, 44.7-second
median latency, approximately 300-second p95 and repeatability `0.657`. Seven of
7B's 105 calls timed out, giving a `6.7%` failure rate. The paired 7B-minus-3B
F1 estimate was `+0.034`, with a 95% interval of `-0.023` to `+0.087`.

**Decision:**
Select `qwen2.5vl:3b`. Although 7B returned more true ingredients, it breached
the failure ceiling and was therefore ineligible. 3B was substantially faster,
more precise, slightly more repeatable and had no failures.

**Qualification and next evidence:**
The selected model's F1 and dense-grocery recall remain low. It is suitable only
for editable suggestions, not autonomous inventory updates. Human confirmation
remains mandatory. Participant testing must now determine whether correcting 3B
suggestions is faster and less frustrating than manual entry and must drive a
documented interface iteration.

## Decision 29: Retain 3B after the public external-validity check

**Date:** 24 September 2026

**Question:** Does a reproducible public-image comparison change the household
deployment decision?

**Method:** A post-selection benchmark deterministically selected 50 official
Open Images test photographs, covering all 27 food classes at least twice.
Qwen2.5-VL 3B and 7B received the same image, closed vocabulary, prompt and
inference configuration. Image-level precision, recall, F1, exact-set accuracy,
latency, failures, invalid outputs and paired image-cluster bootstrap uncertainty
were recorded. Because this test occurred after Decision 28, it was declared
supplementary before results were inspected.

**Results:** 3B achieved precision `0.833`, recall `0.273`, F1 `0.411` and
3.18-second median latency. 7B achieved precision `0.900`, recall `0.818`, F1
`0.857` and 6.39-second median latency. Both had zero failures. The paired
7B-minus-3B F1 estimate was `+0.446` (95% bootstrap interval `+0.306` to
`+0.608`).

**Decision:** Retain `qwen2.5vl:3b` for the local application. The public result
demonstrates that 7B is genuinely stronger on a constrained 27-class task, but
the household benchmark is closer to the intended open-ended input distribution
and 7B failed its predeclared reliability ceiling there. Record both results and
their apparently different conclusions. Consider 7B only as a future hosted
option if its household timeout rate can be removed and re-tested.

**Limitation:** Two examples per class create a fast cross-domain check, not a
high-powered class-level benchmark. Public-image rank must not be presented as
proof of household usability.

## Decision 30: Select Whisper small.en for hands-free cooking

**Date:** 24 September 2026

**Question:** Which local English Whisper size best supports short cooking
commands while remaining viable on the reference laptop?

**Candidates:** `tiny.en`, the existing `base.en` baseline, and `small.en`, all
run through faster-whisper on CPU with int8 computation, beam size five and VAD.

**Method:** Each model processed the same 108 controlled recordings: 18
MealMatch utterances covering every deterministic cooking route, generated in
three English voices and repeated clean and with deterministic 10 dB white
noise. The evaluation measured WER, downstream intent accuracy, failures,
latency and real-time factor. Before inference, eligibility required at most 5%
failures, at least 95% clean intent accuracy and at least 85% noisy intent
accuracy; noisy intent, noisy WER and latency were the ordered selection
criteria.

**Results:** `tiny.en` achieved WER `0.102`, overall intent accuracy `82.4%` and
noisy intent `75.9%`; it failed both accuracy gates. `base.en` achieved WER
`0.059`, overall intent `91.7%`, clean intent `96.3%`, noisy intent `87.0%` and
351 ms median latency. `small.en` achieved WER `0.046`, overall intent `95.4%`,
clean intent `98.1%`, noisy intent `92.6%` and 3.64-second median latency. None
of the 324 calls failed.

**Decision:** Select `small.en` and make the runtime model configurable through
`MEALMATCH_WHISPER_MODEL`. It won the frozen accuracy-first rule, particularly
under noise. Retain `base.en` as the documented low-latency fallback if real
users judge the combined interaction delay unacceptable.

**Limitation and next evidence:** The computer-generated voices make this a
reproducible controlled benchmark, not a user study. Test the selected workflow
with consented speakers in an actual kitchen, including different accents,
microphone distances, hesitations and appliance noise. Measure command success,
time to complete, retries and perceived responsiveness before claiming robust
hands-free use.

## Decision 31: Retain Llama 3.2 3B behind deterministic food-safety guards

**Date:** 24 September 2026

**Candidates:** Llama 3.2 1B, the existing Llama 3.2 3B baseline, and Qwen2.5
3B. The shortlist compares a lower-resource same-family baseline with two
similarly sized local instruction models; it avoids adding unrelated large
models that would not be viable for repository users.

**Evidence:** Each candidate received six constrained recipe cases, four mixed
receipt OCR cases, four substitution cases and four step-aware cooking cases.
The evaluation recorded structure, dietary/allergy conflicts, pantry grounding,
receipt F1, substitution usefulness, required cooking facts, failures and
latency. A pre-selection audit fixed receipt output-mode and coconut-milk label
errors. A subsequent raw-model safety audit found that Llama 3B advised rinsing
raw chicken and Qwen2.5 3B described chicken at 60°C as safe, despite prompting.

**Safety iteration:** The application now answers explicitly labelled poultry
temperature questions and raw-poultry washing questions with deterministic,
unit-tested rules before any LLM call. The raw unsafe outputs remain in
`artifacts/text_model_evaluation_guarded_final/`. Final records mark the two
bypassed cases as `model_invoked: false`, so the report does not misattribute
their safety to a model. The rules follow the
[FoodSafety.gov 165°F/74°C poultry minimum](https://www.foodsafety.gov/food-safety-charts/safe-minimum-internal-temperatures)
and [CDC guidance that raw chicken does not need washing](https://www.cdc.gov/food-safety/foods/chicken.html).

**Final results:** Llama 1B scored `0.580`, with only `42.9%` structured validity
and `80.0%` constraint safety, and was rejected. Llama 3B scored `0.944`, with
100% structure and constraint safety and 2.27-second median latency. Qwen2.5 3B
scored `0.960`, also with 100% structure and constraint safety, at 2.79 seconds.
All guarded critical cases passed and no model call failed.

**Decision:** Retain Llama 3.2 3B. The `0.016` score difference between the 3B
models falls inside the frozen `0.03` practical-tie boundary, so lower median
latency decides the result. Pin the runtime and setup instructions to
`llama3.2:3b` rather than an ambiguous `latest` tag.

**Limitation:** The 18 cases are deliberately compact and deterministic. They
do not establish recipe appeal or conversational quality. Add blinded human
ratings for selected outputs and evaluate the complete text-plus-audio cooking
interaction with participants.

## Decision 32: Confirm Whisper small.en in a cross-family ASR comparison

**Date:** 24 September 2026

**Question:** Did the within-family Whisper size study explore enough of the
pretrained audio-model space?

**Literature shortlist:** Whisper was retained because its large-scale weakly
supervised pretraining was designed for robust zero-shot speech recognition.
Distil-Whisper `small.en` was added because the published distillation work
targets lower-resource inference, and wav2vec 2.0 Base 960h was added as an
architecturally different self-supervised/CTC baseline. The primary sources are
[Radford et al.](https://arxiv.org/abs/2212.04356),
[Gandhi et al.](https://arxiv.org/abs/2311.00430) and
[Baevski et al.](https://arxiv.org/abs/2006.11477).

**Method:** The Stage A winner, Whisper `small.en`, Distil-Whisper `small.en`
and `facebook/wav2vec2-base-960h` processed the same frozen 108-file manifest.
The manifest hash, transcripts, intents, clean/noisy conditions and frozen
eligibility rule were unchanged. The candidates used their ordinary deployable
decoders: faster-whisper beam search plus VAD for the Whisper variants and
greedy CTC for wav2vec 2.0.

**Results:** Whisper achieved WER `0.046`, overall intent `95.4%`, clean intent
`98.1%`, noisy intent `92.6%` and 1.05-second matched-run median latency.
Distil-Whisper was slightly faster at 0.92 seconds but achieved only `92.6%`
clean and `81.5%` noisy intent, failing both accuracy gates. wav2vec 2.0 was
fastest at 59 ms but achieved only `64.8%` clean and `31.5%` noisy intent. No
inference call failed.

**Decision:** Keep Whisper `small.en`. It was the only cross-family candidate
to satisfy the predeclared clean and noisy command requirements. This confirms
rather than retrospectively changes the runtime decision in Decision 30.

**Participant follow-up:** Ten participants subsequently tested the integrated
hands-free workflow. The session tally records 70/70 successful core command
outcomes, no retries and responses within five seconds. Ten retained detailed
rows had mean response time `2.00` seconds and mean rating `4.90/5`. This adds
real-voice and natural-phrase evidence, but raw audio and full row-level logs
were not retained and background noise was not standardised. It remains a
formative result rather than population-level proof of robust ASR performance.

## Decision 33: Confirm Llama 3.2 3B in a three-family text comparison

**Date:** 24 September 2026

**Question:** Did the original text comparison include enough architectural
breadth?

**Literature shortlist:** The final candidates are Llama 3.2 3B, Qwen2.5 3B
and Phi-3.5 Mini 3.8B. They represent three public instruction-model families
within the local 3–4B deployment envelope. The choice is supported by the
[Llama 3 family report](https://arxiv.org/abs/2407.21783) and
[Meta's Llama 3.2 local-model release](https://ai.meta.com/blog/llama-3-2-connect-2024-vision-edge-mobile-devices/),
the [Qwen2.5 technical report](https://arxiv.org/abs/2412.15115), and the
[Phi-3 technical report](https://arxiv.org/abs/2404.14219). Llama 1B remains a
rejected preliminary capacity baseline rather than one of the final families.

**Operationalisation:** Tagged Ollama artifacts were compared through the same
API, prompts, temperature-zero configuration, seed, context, output limit and
timeout. The deployable artifacts were Llama 3.2 3B Q4_K_M, Qwen2.5 3B Q4_K_M
and Phi-3.5 3.8B Q4_0. The differing default quantisation is recorded as a
pipeline limitation rather than hidden.

**Results:** Llama scored `0.944`, with 100% structure and constraint safety and
1.11-second median latency. Qwen scored `0.960`, also passing every gate, at
1.53 seconds. Phi scored `0.704`, with only `35.7%` structured validity and
`80.0%` constraint safety, so it was ineligible. No model call failed.

**Decision:** Retain Llama 3.2 3B. Qwen's `0.016` lead remains inside the frozen
`0.03` practical-tie boundary, so matched-run latency selects Llama. Phi-3.5 is
rejected for this application despite its strong general literature results,
demonstrating why task-specific validation is necessary.

**Participant follow-up:** Nine participants used the deployed AI recipe,
substitution and cooking-assistant features. Available mean usefulness ratings
were `4.35/5` (`n=8`), `3.86/5` (`n=7`) and `4.71/5` (`n=7`) respectively; ease
was `4.81/5`, `5.00/5` and `4.93/5` on the same feature-specific denominators.
The sessions were not a blinded candidate comparison, so they validate the
selected workflow without changing the frozen model-selection result.

## Decision 34: Parse receipt lines in code and let the model only name them

**Date:** 27 September 2026

**Problem:** A real wholesale receipt exposed four failures of the free-form
"extract the ingredients" prompt: abbreviations were missed (`B/S THIGHS`,
`ARTISAN BGT`), `KALAMATA OLV` became olive oil, a `water` that was not on the
receipt was invented, and repeated lines (three baguettes, two shrimp) lost
their quantity. Output also changed between identical runs.

**Chosen option:** Split the work between deterministic code and Llama 3.2 3B.

- `receipt_parsing.py` keeps only product lines (priced or item-coded, before
  the total; payment, address, discount and header lines are dropped) and reads
  the quantities a receipt states: repeated lines, `3 @ 1.29`, `x3`, weighed
  produce (`1.24 kg @ $1.52/kg`) and pack sizes (`4L`, `750G`, `12CT`, `10LB`).
- Abbreviations are expanded from a table, with Tesseract's common letter swaps
  (`OLY` → `OLV`) and a vowel-skeleton match for unlisted ones
  (`BRKFST` → breakfast, `CHDR` → cheddar). The expansion is a hint to the model.
- The model answers a JSON schema with one required key per numbered line
  (temperature 0, fixed seed, capped output). It names the line before
  deciding whether it is food, so it can neither skip nor add lines.
- If the model only dropped words from the receipt (`milk` for `WHL MLK`), the
  receipt's words are restored, so whole and skim milk, or red and yellow
  onions, stay separate rows. The same ingredient bought on several lines is
  merged into one row with the quantities added.
- The whole-word non-food denylist still backs up the model (no longer blocking
  bagels and cabbage through substring matches), and a warning appears when the
  receipt's "items sold" count is higher than the lines read.
- OCR runs on an upright, greyscale, contrast-stretched copy upscaled to about
  2000 px, which removed most garbled prices and item codes on phone photos.

**Evidence:** Three rendered receipts (`backend/tests/fixtures/receipts/`) plus the
participant's real receipt: 49 expected rows covering repeats, stated
quantities, abbreviations, look-alike foods and 11 non-food products. The first
line-based version scored 32/37 rows with Llama and Qwen2.5 3B alike; Qwen merged
whole and skim milk into one row. The final version scores 37/37 with Llama. A
holdout receipt written after tuning scored 8/12 on its first run, exposing an
OCR `@`-for-`0` weight bug and unlisted abbreviations; after those general fixes
all 49 rows are correct, no non-food product passes, and the confirmation page
shows the same rows in 5–8 seconds per receipt. The holdout is no longer blind.

**Trade-off:** Units come only from the receipt (weight, volume or pack count);
otherwise rows use pieces, because the model's unit guesses were mostly wrong.
The abbreviation table and grocery word list need occasional additions, and
the user still confirms every row.

**Details:** The full iteration record, including the code removed, is in
[Receipt extraction: design iteration 2](receipt-extraction-iteration.md).

## Decision 35: Recover cut-off photo answers and test close-up passes

**Date:** 27 September 2026

**Problem:** Round 2 refrigerator and grocery-table photographs had acceptable
precision (0.82 and 0.78) but low recall (0.60 and 0.47), matching the frozen
household test. Diagnosis found pipeline faults rather than a model limit.
Answers on crowded photographs hit the 1,200-token output limit and were
discarded whole, so the user saw no suggestions. The model lists only about
8–13 foods per image. Brand names were taken literally. The confirmation form
showed every unknown unit as "piece".

**Chosen option:** Keep Qwen2.5-VL 3B, its prompt and its threshold, and change
how its answers are handled.

- Stream the answer, keep every complete item, stop an answer that repeats
  itself, raise the output limit to 2,048 tokens, and store how each pass
  ended with the scan.
- Remove brand, store and marketing words; map product lines to foods; use a
  label only when it agrees with the model's name.
- Map model units onto the form's units, and let the form read plural units.
- After the whole photo, run the same prompt on four overlapping close-ups,
  streaming each pass into the confirmation form so review can start at once.

**Evidence:** On the frozen test, run once after the design was settled, the
whole-photo pass improved F1 from 0.219 to 0.279 (paired difference +0.060,
95% CI +0.009 to +0.121) and halved empty results. The close-ups raised recall
from 0.163 to 0.317, but only 12% of their additions were correct. F1 did not
change relative to the whole-photo pass (−0.016, CI −0.060 to +0.023). On the
participant's two photographs, five runs each, recall rose from 0.49 to 0.75
and from 0.55 to 0.81; those photographs informed the design. The frozen test
is no longer blind for pipeline changes.

**Trade-off:** Close-ups add about five wrong suggestions per typical photograph
and about 15 seconds after the first results. They should become a
user-requested "look closer" action rather than run on every photograph; until
then `MEALMATCH_VISION_CLOSE_UPS=0` turns them off.

**Details:** [User testing round 2, photo detection iteration 1](user-testing-round-2-results.md#photo-detection-iteration-1).


## Decision 36: Close-ups on request, shorter model hold and pinned model versions

**Date:** 28 September 2026

**Problem:** The photo model held about 4.6 GB for 30 minutes after every scan,
and every photograph ran five model passes, although close-ups added mostly
wrong items on the frozen test (Decision 35). Model versions were not pinned:
Ollama tags can be republished upstream, Whisper followed its latest commit,
and the recipe-matching embedding model was loaded only if it already happened
to be on the computer. A fresh GitHub clone therefore silently lost semantic
recipe matching, and could get different model builds from those evaluated.

**Chosen option:**

- Run only the whole-photo pass on upload. A "Look closer" button sends the
  same photo again to `/upload-image/{scan_id}/close-ups`, so the server still
  never keeps photographs. The close-ups add to the same scan record, which
  notes that the user asked for them. `MEALMATCH_VISION_CLOSE_UPS=1` restores
  automatic close-ups.
- Unload the photo model 5 minutes after the last scan instead of 30. Loading
  it took 1.4 seconds once its files were cached, and the app already starts
  loading it when the Photo tab opens. The 30-minute hold dated from a measured
  cold start of about 70 seconds, which no longer applies.
- Pin every pretrained model in `backend/model_versions.py`: Ollama manifest
  digests and the tested Ollama version, and fixed Hugging Face commits for
  Whisper `small.en` and `all-MiniLM-L6-v2`. `setup_models.py` pulls only
  missing Ollama models (a repeat pull could replace a pinned build), checks
  installed ones against their digests, and downloads the Hugging Face models
  into `backend/.model_cache`. The embedding download is limited to the
  PyTorch weights and configuration (87 MB instead of 912 MB).

**Evidence:** Memory reported by Ollama 0.30.10 on the reference M4 Pro: photo
model 4.6 GB, text model 2.6 GB, both 7.1 GB. Halving the photo model's
context to 4,096 tokens saved only 0.24 GB and cannot hold the image plus a
full answer, so it was rejected. Each pass spent about 7 seconds reading the
image and 2–5 seconds writing the list. In a browser test on the grocery-table
photograph, the whole photo gave 12 suggestions with no close-ups, and "Look
closer" added 5 more. The pinned versions are the ones installed when the
evaluations ran; `setup_models.py --check` confirmed all of them.

**Post-iteration timing evidence:** Three retained photo-analysis runs took
`5`, `4` and `5` seconds (mean `4.67`, median `5`, range `4–5` seconds). The
earlier ten participant observations had an approximate median of `23.75`
seconds, so the observed median was `18.75` seconds (`78.9%`) lower. The images
and conditions differed and the later values are repeated runs of one image;
this is descriptive evidence of improved responsiveness, not a paired causal
estimate.

**Trade-off:** Users who do not press "Look closer" miss the extra recall that
close-ups gave on the participant's photographs (Decision 35). A model is
reloaded after 5 idle minutes. Ollama installs by tag, so if a pinned build is
republished upstream a new installation gets the new build; the setup check
reports the difference but cannot prevent it.

**Details:** [README, Memory and speed](../README.md#memory-and-speed);
[User testing round 2, after iteration 1](user-testing-round-2-results.md#change-after-iteration-1-close-ups-on-request).

## Decision 37: Coherent, unique AI recipe ideas with title cards instead of generated photos

**Date:** 28 September 2026

**Problem (user testing, round 2):** A request for *ice cream* returned "Creamy Tomato Ice Cream Pie". Recipes appeared twice as cards, and generated photos were slow. The relevance step split "ice cream" into "ice" and "cream" and so offered onion, tomato and potato. The model sometimes repeated a title within one batch of three. Separately, any AI recipe with a photo was listed twice by `/recipes` and `/recommend`. The photo model holds 5.7 GB while rendering and took 15–16 s per photo at 768×576.

**Chosen option:**

- Keep compound foods as one term. Compare sweet requests only with sweet reference dishes, and never offer them savoury pantry foods unless named (`recipe_relevance.py`).
- Reject and regenerate a dessert that contains savoury ingredients, and an idea that repeats one already shown (same title words or at least 75% of the same main ingredients). Reuse an earlier identical recipe instead of saving a twin.
- List every recipe once (`browsable_recipes`). Hide earlier AI recipes that fail the dessert check.
- Turn recipe photos off by default and show a typographic title card. `MEALMATCH_LOCAL_IMAGE_MODEL=x/flux2-klein` turns photos back on, rendered at 512×384 (about 10 s). `setup_models.py` pulls the photo model only with `--with-photos`.

**Trade-off:** AI recipes no longer have a food photo by default. The dessert word lists are hand-written and may miss unusual dishes; the post-generation check is the safety net. See [User testing round 2, design iteration 2](user-testing-round-2-results.md#design-iteration-2-ai-recipe-ideas-and-hands-free-cooking).

**Post-iteration evidence:** The same participant cohort subsequently described
AI recipe generation as quicker. No instrumented post-iteration timings were
retained, so this supports perceived responsiveness only and is not reported as
a numerical latency improvement.

## Decision 38: Diet rules as hard filters with a labelled fallback, and use-soon food first

**Date:** 28 September 2026

**Chosen option:**

- Allergies stay absolute: a conflicting recipe is never listed.
- A recipe that breaks a saved diet is listed only after every recipe that fits, below a divider ("That's every recipe here that fits your vegetarian preference"). Its card shows which diet it breaks and why ("Not vegetarian · salmon").
- The word lists were extended: parmesan, ghee, chorizo, spaghetti, couscous and others were missed before. Look-alikes are excepted (peanut butter, coconut milk, butternut squash, buckwheat, rice noodles), so diet-safe recipes are not lost.
- Recommendations are ordered by:
  1. fitting the diet;
  2. using any food due within the 0–5 day "use soon" window;
  3. a score weighted 50% on rescuing that food and 40% on pantry coverage.

  Food due sooner counts more: 1 for today, down to 0.17 at five days. "Avocado" and "avocados" count once, and expired food no longer counts as available.

**Reason:** The purpose of MealMatch is to use food before it expires. Ordering by pantry coverage first (Decision 20) ranked a full match that rescues nothing above a recipe using food due tomorrow. On the participant's pantry, the top recommendations now use the salmon and prawns due tomorrow and the beef due today.

**Revision to Decision 20:** Diet conflicts are no longer removed outright; they follow every fitting recipe, labelled. Allergy conflicts are still removed.

## Decision 39: One action per voice command, finishing by voice, and a reliable wake word

**Date:** 28 September 2026

**Problem (user testing, round 2):**

- Phrases with "next" were answered with the next step while the step card stayed put.
- "Done" on the last step went nowhere.
- "Hey Mimi" only worked after hands-free had been turned on once.

**Chosen option:**

- `voiceCommands.ts` turns each transcript into exactly one intent. Any "next" moves the card, which updates immediately and is then confirmed by the server.
- On the last step, finishing words do what the "Meal is ready" button does. Before the last step, finishing asks for confirmation.
- The wake listener:
  - stops for good when removed, fixing the double listener under React's development double mount;
  - accepts punctuation and common mishearings;
  - falls back to en-US;
  - explains a refused microphone;
  - never waits for a user gesture when started by voice.

**Revision to Decision 24:** Finishing on the last step no longer needs a spoken confirmation, matching the button. Cancelling still does.

**Post-iteration evidence:** The same participant cohort re-tested the redesigned
flow. Every natural verbal indication of wanting to continue that was attempted
advanced the visible recipe card. This resolves the observed speech/card mismatch
for the tested phrases. The exact re-test denominator was not retained, so no new
success percentage is claimed.

## Decision 40: Update the pantry when the meal is ready, with unit conversion

**Date:** 28 September 2026

**Chosen option:** "I'm cooking this" records which pantry item each ingredient will come from, preferring the one that expires first, but changes nothing. "Meal is ready", by button or by voice, takes the amounts out.

`pantry_usage.py` converts units through typical weights, densities and package sizes:

- 1 cup of milk from 1 bottle leaves 0.8 bottle;
- 2 cloves from 1 garlic bulb leaves 0.8;
- 2 cups of spinach from a 150 g bag leaves 0.6 bag.

Amounts that cannot be converted are left unchanged rather than guessed. The app reloads the pantry and recommendations at once. "Changed my mind" now only stops the session, and still restores sessions started under the old rule.

"Use soon" on the home screen now opens the Recipes page filtered to recipes that use the foods shown, the most urgent first, instead of opening one recipe.

**Also fixed:** The rescue count used the UTC date of the cooking start, a day behind local time in UTC+8 until 8 am. It now uses the local date, like the "Use soon" panel.

**Revision to Decisions 12 and 16:** Deduction moved from the start of cooking to "Meal is ready", and incompatible units are now converted with typical sizes instead of being skipped. Every quantity stays editable, because converted amounts are estimates.

## Decision 41: The fridge film is the landing page

**Date:** 28 September 2026

**Chosen option:** The "Open the fridge" scroll film (formerly the standalone `mealmatch-cinematic-intro/`) is now `frontend/src/components/FridgeIntro.tsx`. It replaces the burger intro, the welcome screen, anime.js and `burger-intro/`.

- It plays once per browser session.
- "Open my kitchen" fades it out onto the home screen.
- "Replay the opening" on the home screen plays it again.
- `?skipIntro=1` and `?intro=1` skip or force it.

**Fixes to the film:**

- *Large windows dropped frames.* Full-screen light layers were oversized (up to 170vmax), blurred with CSS, or screen-blended every frame. They are now drawn at half or quarter size and scaled up, blended normally, and hidden when invisible. The room's focus pull crossfades a pre-blurred photo instead of blurring live, and images are decoded before playback. With software rendering as a proxy for graphics load, scrolling through the door and the push-in costs about 45 ms a frame at 1440×900 instead of 73 ms, and about 22 ms at 632×968 instead of 38 ms. The new runs also covered the dissolve and the start of the flash, which the old runs did not reach. In headless Chrome at 1920×1080 on the reference M4 Pro, three frames over the whole film exceeded 25 ms.
- *The fridge-to-shelf transition felt cut up.* The fridge zoomed toward its middle while an unrelated shelf photo cross-faded over it. Now one camera pushes toward the top shelf, and the close-up is laid exactly over that shelf and scaled with it. It fades in with soft edges and a brief motion blur.
- *The finished dish was off-centre.* It kept a 28-pixel sideways drift; it is now centred between the top bar and the title.

**Trade-off:** The close-up photo and the fridge photo show different arrangements of food. On tall phone screens a short soft overlap remains during the dissolve. A close-up made to match the fridge's top shelf would remove it.

## Decision 42: Taste words decide sweet or savoury, and a sweet request starts from sweet pantry food

**Date:** 28 September 2026

**Problem (design iteration 3):** "Sweet dish with what I have in my pantry" returned "Limey Beef Fritters", "Beef and Carrot Fritters", "Sweet Potato and Carrot Cake" and "Sweet Beef and Carrot Fritters". "Sweet" was treated as a filler word, so the request named no dish. The pantry selector then built on the food expiring first, beef sirloin due that day, and offered beef, onion, garlic butter, carrot and potatoes. The dessert check from Decision 37 did not run, because the request was not recognised as sweet.

**Chosen option (`recipe_relevance.py`):**

- A taste word ("sweet", "sugary", "savoury", "salty") sets what the dish must taste like, unless it is part of a food's name ("sweet potato", "sweet chilli", "sweet corn"). "Sweet" next to a named savoury food ("sweet and sour chicken") is a savoury dish with a sweet sauce.
- A sweet request that names no dish or food offers two groups of pantry food, one entry per food:
  1. the sweet foods that expire first;
  2. the dessert basics that sweet reference dishes use.

  Savoury and expired food are never offered.
- The prompt states the taste. When the request asks to use what the cook has ("with what I have", "use up"), it also asks for pantry foods plus basic staples only.
- A generated recipe is regenerated when:
  - it puts savoury food in a dessert;
  - it has nothing sweet in a sweet dish;
  - it puts a dessert food in a savoury dish;
  - its title names a pantry food its ingredients leave out ("Banana Date Bites" with neither).

  A pantry-only request is also retried when the recipe needs more than two foods to buy, but that recipe is kept as a last resort.
- One idea failing its checks no longer stops the next.

**Evidence:** For the participant's pantry, the request now offers blueberries, raspberries, strawberries, banana, dates, kiwi, eggs, milk and almonds. A run on a copy of the participant's database gave "Strawberry Banana Pancakes", "Strawberry Almond Crumble Parfait" and "Almond Berry Crumble Muffins", in 1, 2 and 3 attempts.

**Trade-off:** Taste and dessert words are still word lists and can miss unusual phrasing. The checks after generation are the safety net, and more checks can mean more attempts.

**Post-iteration evidence:** The same participant cohort re-tested the generator. They found that the recipes matched what they asked for and made better use of their pantry ingredients, and the median generation time was lower than before. The before and after timings were not added to the repository, so the size of the reduction is not stated.

## Decision 43: Remove recipe-photo generation; emojis stand in

**Date:** 28 September 2026

**Problem:** Recipe photos were already off by default (Decision 37), but the image model remained an option. It held 5.7 GB and took about 10 s a photo.

**Options considered:** FLUX.2 Klein 4B is the smallest image model offered through Ollama. A distilled one-step model such as SD-Turbo would draw faster. It would add a second image library, a multi-gigabyte download and gigabytes of memory while drawing, for less convincing food pictures. It was not tried.

**Chosen option:** The photo generator is removed:

- the `/recipes/{id}/image` endpoint;
- the `MEALMATCH_LOCAL_IMAGE_MODEL` and `MEALMATCH_IMAGE_*` settings;
- `setup_models.py --with-photos` and the pinned FLUX.2 Klein digest.

AI idea cards show only the idea number, time, name, pantry match and actions. Recipe cards, the recipe page and the cooking header show the recipe's main foods as emojis on a plate, with foods named in the title first. Photos rendered earlier are no longer shown, and `backend/generated_images` has since been removed.

**Revision to Decision 37:** Title cards and optional photos are replaced by emoji artwork, and there is no image model.

## Decision 44: Keep the screen under a recipe, and AI ideas until cleared

**Date:** 28 September 2026

**Problem (design iteration 3):** After opening a recipe and going back, the list was at the top again and the other AI ideas were gone. The recipe page replaced the whole screen, so the list and its ideas were removed and rebuilt from nothing.

**Chosen option:** The current screen stays mounted, hidden, under the recipe or cooking view. Its scroll position is restored on the way back.

- AI ideas are held by the app, not the page, and stored for the browser session. They survive opening a recipe, switching tabs and reloading, until a new request or "Clear ideas".
- Recipe cards made from a chat request are kept with the chat history.

**Evidence:** In a browser run, the list was scrolled to 2,600 px, a recipe was opened and closed, and the list returned to 2,600 px. All three ideas remained after opening one and after switching tabs, and "Clear ideas" removed them.

**Post-iteration evidence:** In the cohort re-test, the AI idea cards stayed after participants opened one, and the recipe list kept its scroll position. Participants reported higher usability after the redesign; SUS was not administered.

## Decision 45: Swaps from the pantry and a kitchen table first, the model last

**Date:** 28 September 2026

**Problem (design iteration 3):** Swap often said "No reliable substitute was found":

- swaps were worked out only for missing ingredients, so an ingredient the cook had never got any;
- all ingredients went to the model in one call, and it skipped or renamed some;
- the 13-food fallback list was used only when the whole answer failed.

**Chosen option (`substitutions.py`):** Swaps are fetched for the one ingredient tapped, in three steps:

1. pantry foods of the same kind, such as another hard cheese or another berry, but never ice cream for cream;
2. a table of standard substitutions for about 100 foods, each with how to use it, marked "In pantry" when the cook has it;
3. the text model, told the dish, only when those give fewer than three swaps.

The model's answers are matched to the ingredient by food, so a renamed answer still counts, and they rank after known swaps. Every swap is checked against saved allergies and diets, and at most three are shown.

**Evidence:** Every one of the 8 ingredients of an AI pancake recipe got swaps in a browser run. Tests cover same-kind pantry swaps, products that must not be swapped like their source food (chicken stock is not chicken), and allergy filtering.

**Post-iteration evidence:** The cohort rated the swap feature as more useful than before (earlier mean usefulness 3.86/5, n = 7). The post-iteration ratings were not supplied.

**Revision (design iteration 4):** In the dark theme, the light green card of an in-pantry swap made its text unreadable. Every swap now uses the same card; only the tag differs, green for "In pantry" and amber for "Alternative", with dark-theme colours for both.

## Decision 46: The cooking and loading screens follow the app palette

**Date:** 28 September 2026

**Chosen option:** The cooking screen's panels were plain white; they now use the same panel colours as the home and recipe screens:

- a green header like the recipe page;
- a gold timer;
- an apricot voice panel;
- a cream step card;
- step cards that alternate colours, with the current step outlined in green.

The loading screen shows only the green MealMatch mark and "MealMatch is loading", without the pink icon and orbiting emojis.

## Decision 47: The product tour plays when the app first loads

**Date:** 28 September 2026

**Problem (design iteration 4):** "See how it works" opened by itself only the first time a browser reached the Home screen, then never again unless the button was found. A user who opened the app on another screen, or had visited before, did not see it. Its screenshots also still showed generated recipe photos, white cooking panels and "restore pantry", which the app no longer has.

**Chosen option:**

- The tour belongs to the app rather than the Home screen. It plays once per browser session, when the app first loads, after the opening film, on whichever screen the app opens. Closing it records the session; "See how it works" replays it.
- `?skipTour=1` skips it for automated checks, and `?preview=experience` still forces it.
- The ten tour screens were re-captured from the current interface with `npm run capture:tour`. The capture script now answers the streamed photo endpoint, and its sample kitchen uses the current swaps and no recipe photos.

**Trade-off:** Returning users see the tour in every new browser session. It can be skipped with one key press (Escape) or button, and it never opens again in the same session.

