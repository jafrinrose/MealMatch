# MealMatch Round 2 Usability Results

The broader ten-participant interface study, nine-participant text-feature
subset and ten-participant hands-free study are reported in
[Combined formative user-testing results](user-testing-combined-results.md).
The controlled photograph repeatability test below remains a separate
single-scene technical observation and is not merged with the participant
denominators.

## Test 1: Controlled pantry-photograph recognition and repeatability

### Purpose

This test examined Qwen2.5-VL's ingredient-recognition precision, recall, quantity accuracy, latency and run-to-run consistency under a controlled household-photo condition. One photograph containing eight independently recorded ground-truth ingredients was submitted to the unchanged production workflow three times.

Repeated submissions of one photograph measure repeatability; they are not three independent photograph samples. Results are therefore reported descriptively and should not be used for inferential claims about performance on other household scenes.

### Ground truth and measurement definitions

- Ground-truth ingredients per run: 8.
- A true positive was a returned ingredient matching a ground-truth ingredient.
- A false positive was a returned ingredient not present in the photograph.
- A false negative was a ground-truth ingredient absent from the initial output.
- A quantity correction was counted when the participant had to edit an initially returned quantity.
- Detected-item quantity accuracy used only true-positive detections as its denominator.
- End-to-end exact-item coverage required both the ingredient and its initial quantity to be correct, with all eight ground-truth ingredients as the denominator.
- Upload-to-results time was measured from image selection until the confirmation results became visible.

### Per-run results

| Metric | Run 1 | Run 2 | Run 3 |
|---|---:|---:|---:|
| Ground-truth ingredients | 8 | 8 | 8 |
| True positives | 5 | 6 | 5 |
| False positives | 0 | 0 | 0 |
| False negatives | 3 | 2 | 3 |
| Precision | 100.0% | 100.0% | 100.0% |
| Recall | 62.5% | 75.0% | 62.5% |
| F1 score | 76.9% | 85.7% | 76.9% |
| Quantity corrections | 1 | 1 | 1 |
| Initial quantities correct | 4 of 5 | 5 of 6 | 4 of 5 |
| Detected-item quantity accuracy | 80.0% | 83.3% | 80.0% |
| Exact ingredient-and-quantity coverage | 4 of 8 (50.0%) | 5 of 8 (62.5%) | 4 of 8 (50.0%) |
| Upload-to-results time | 5 s | 4 s | 5 s |

The originally proposed `5/8` quantity figure for Run 1 describes the number of correctly named detections relative to ground truth. It is not initial detected-item quantity accuracy: one of those five detections required editing, so the model initially returned four correct quantities among five detected items.

### Aggregate descriptive metrics

The same eight ground-truth ingredients created 24 repeated ingredient opportunities across the three runs. These opportunities are correlated because they came from the same photograph.

| Aggregate measure | Result |
|---|---:|
| Total true positives | 16 |
| Total false positives | 0 |
| Total false negatives | 8 |
| Micro-averaged precision | 100.0% |
| Micro-averaged recall | 66.7% |
| Micro-averaged F1 | 80.0% |
| Mean ingredients detected per run | 5.33 of 8 |
| Detection-count range | 5–6 |
| Complete-detection runs | 0 of 3 |
| Total quantity corrections | 3 |
| Aggregate detected-item quantity accuracy | 13 of 16 (81.3%) |
| Aggregate exact ingredient-and-quantity coverage | 13 of 24 (54.2%) |
| Quantity-correction rate among detections | 3 of 16 (18.8%) |
| Mean upload-to-results time | 4.67 s |
| Median upload-to-results time | 5 s |
| Latency range | 4–5 s |

If every missed ingredient was manually added, the confirmation workflow would require eight missed-item additions and three quantity edits across the three runs: 11 item-level correction actions in total. No deletion action was required because the model produced no false-positive ingredients.

### Interpretation

Qwen2.5-VL was conservative under this condition. Every returned ingredient was relevant, resulting in perfect precision and no user effort spent deleting invented food. Recall was weaker and varied between 62.5% and 75.0%, meaning that two or three visible ingredients still had to be added manually on every run. This precision–recall pattern supports retaining the human confirmation stage and making missed-item addition fast.

The second run identified one more correct ingredient than the first and third runs even though the image and application pipeline were unchanged. This demonstrates output variability and means that a single inference should not be presented as an exact inventory. The detection-count variation was small—five to six items—but no run produced the complete eight-item inventory.

Quantity estimation was broadly usable but not fully reliable. One quantity edit was required in every run, producing an aggregate detected-item quantity accuracy of 81.3%. The quantity stepper and unit selector introduced after Round 1 directly support this correction task.

Latency was consistent at four to five seconds and was substantially shorter than the approximately 30-second delay observed with a different photograph during Round 1. Because image complexity, hardware state and model warm-up can affect inference time, these measurements should remain separate rather than being combined as if they represented identical conditions.

### Report-ready summary

> A controlled photograph containing eight ground-truth ingredients was processed three times to assess recognition performance and repeatability. Qwen2.5-VL returned no false-positive ingredients in any run, giving micro-averaged precision of 1.00. It detected five, six and five ingredients respectively, producing micro-averaged recall of 0.667 and F1 of 0.800. Recall varied from 0.625 to 0.750, and no run detected the complete inventory. One returned quantity required correction in every run; 13 of 16 detected-item quantities were initially correct, giving aggregate quantity accuracy of 81.3%. Mean upload-to-results time was 4.67 seconds, with a four-to-five-second range. The results indicate conservative but incomplete recognition, acceptable latency under this test condition, and measurable run-to-run variability. Human verification remains necessary, particularly for adding missed ingredients and correcting quantities.

### Remaining data to collect

The following fields were not recorded for this test and should be included in subsequent trials:

- scene type and packaging condition;
- which individual ingredients were consistently or intermittently missed;
- Qwen's returned `visible_text` for each correct detection;
- whether each ingredient had readable packaging text;
- evidence-of-label-use classification: text-supported, visual-only or mixed/uncertain;
- participant confidence after confirmation;
- total confirmation time and number of interaction clicks.

## Tests 2 and 3: Refrigerator and grocery-table photographs

### Purpose

Test 1 used a controlled eight-item photograph. Tests 2 and 3 checked whether its result, high precision with incomplete recall, holds in fuller household scenes. They were run before changing the model, prompt or confidence threshold. Neither photograph is part of the household development or frozen test sets, so the rule against tuning on frozen-test images was not affected.

### Method

- **Photographs:** one of the participant's own refrigerator (mixed packaged and unpackaged food; much of the packaging has readable text) and one of a grocery table (mostly packaged food with some produce). Both are 3024 × 4032 phone photographs. They are kept out of the repository because they show the participant's home.
- **Ground truth:** the participant recorded 15 visible food items per photograph. For the refrigerator, 14 of the 15 are known from the notes and the confirmed list; the 15th was not written down or re-entered, so it always counts as missed.
- **Runs:** one production run per photograph was scored (scans `08e413b6` and `21768e98`), as the protocol allows. Other uploads of the same photographs are reported separately for repeatability.
- **Sources:** true and false positives, quantities and edits were taken from the app's scan log, which stores the model's exact output and the confirmed list. Times, confidence and ease are the participant's own measurements.
- **Evidence type:** each returned item was classed as *text-supported* (label text quoted by the model is printed on the item and supports it), *visual-only* (no label text), or *uncertain* (the quoted text is misread, invented or does not support the name).

### Results

| Measure | Test 2: refrigerator | Test 3: grocery table |
|---|---:|---:|
| Ground-truth items | 15 | 15 |
| Items returned | 11 | 9 |
| True / false positives | 9 / 2 | 7 / 2 |
| False negatives | 6 | 8 |
| Precision | 81.8% | 77.8% |
| Recall | 60.0% | 46.7% |
| F1 | 69.2% | 58.3% |
| Quantity and unit both correct (true positives) | 4 of 9 | 4 of 7 |
| Count correct, ignoring unit | 8 of 9 | 6 of 7 |
| Items added / deleted / renamed / quantity-edited | 4 / 2 / 0 / 5 | 7 / 1 / 2 / 3 |
| Items needing a correction | 11 of 15 (73%) | 13 of 15 (87%) |
| Returned items: text-supported / visual-only / uncertain | 3 / 5 / 3 | 4 / 5 / 0 |
| Upload to results (app log; participant's stopwatch) | 34.6 s (35 s) | 14.0 s (15 s) |
| Time for corrections and additions | 50 s | 1 min 50 s |
| Confirmation time | 15 s | 15 s |
| Participant confidence (1–5) | 4 | 4 |
| Task ease (SEQ, 1–7) | 5 | 5 |

**Test 2, item by item**

| Model returned | Label text the model quoted | Evidence | Outcome |
|---|---|---|---|
| orange ×2 | — | visual-only | correct |
| chocolate, 1 box | GODIVA | text-supported | correct |
| pepper, 1 piece | "red chili pepper" (not printed on the bell-pepper bag) | uncertain: invented | right food, count edited 1 → 3 |
| sunflower seeds | "Sunstate California Walnut" (the bag says Sunshine) | uncertain: misread | wrong; this was the walnut bread; deleted |
| grapes, 1 piece | — | visual-only | correct, unit edited to box |
| cereal, 1 jar | Organic Rolled Oats | text-supported | correct, unit edited to pack |
| chocolate syrup | — | visual-only | correct |
| cookies, 1 carton | 京都市菓子工房 (the box says 京都抹茶ラングドシャ) | uncertain: garbled | correct |
| yogurt, 1 piece | FARMERS UNION GREEK STYLE | text-supported | correct, unit edited to box |
| peach | — | visual-only | wrong; most likely the guava; deleted |
| lettuce, 1 piece | — | visual-only | correct, unit edited to pack |

Missed: guava, avocado and chilli padi (no labels), salmon (labelled), the walnut bread (read as sunflower seeds) and the unrecorded 15th item.

**Test 3, item by item**

| Model returned | Label text the model quoted | Evidence | Outcome |
|---|---|---|---|
| pineapple | — | visual-only | correct |
| orange ×2 | — | visual-only | correct |
| bell pepper ×2 | — | visual-only | correct, count edited 2 → 3 |
| chocolate milk, 1 carton | Cadbury Dairy Milk | text-supported, wrong food | a chocolate bar; renamed to chocolate |
| herbs & spices, 1 carton | Arla | text-supported (brand only) | the cheese; renamed |
| california walnut bread, 1 loaf | Sunshine California Walnut | text-supported | correct, unit edited to pack |
| tomato | — | visual-only | wrong; the red pepper; deleted |
| grape, 1 piece | — | visual-only | correct, unit edited to box |
| milk, 1 bottle | meiji | text-supported | correct |

Missed: couscous, wraps, oats, honey, salmon and garlic butter (all labelled), the chocolate bar (named as chocolate milk) and the guava.

### Differences between the notes and the scan log

- **Refrigerator, wrong items:** the notes record one wrong item (sunflower seeds). The log shows a second, *peach*, which was deleted and replaced by guava. Counting peach as correct, as the notes did, gives precision 90.9%, recall 66.7% and F1 76.9%.
- **Refrigerator, label text:** the notes record 6 of 11 items with a label. Only 3 of the quoted texts are both real and supportive; the other 3 are misread, garbled or invented. The model's `visible_text` is therefore not proof that it read a label.
- **Grocery table, misses:** the notes list six missed labelled items. The guava was also missed and added during confirmation.
- **Grocery table, confidence:** the app logged 5; the participant recorded 4. The participant's value is used.
- **Units:** at least two of the six unit edits were caused by the app, not the model. The confirmation form only knows a fixed list of units and shows anything else, such as *loaf*, *packet* or plural *boxes*, as *piece*, so the bread's *loaf* appeared as *piece*. The backend had also turned the model's *package* for the refrigerator grapes into *piece*. The model's own unit for the other *piece* rows was not logged.
- **Confirmation time:** the app logged about 7.5 minutes per photograph because it measures until the confirm button is pressed, which included note-taking. The stopwatch times are used.

### Repeatability and latency

- **Refrigerator:** five uploads returned 10, 11, 13, 10 and 11 items. Sunflower seeds appeared in all five and peach in four. Guava, avocado and salmon never appeared; chilli appeared twice, as *chili pepper*. The first three uploads (12:06–12:09) overlapped and waited for each other and for the model to load, taking 279, 204 and 219 seconds. The next took 57 seconds and the scored run 35 seconds. Users who re-upload while a scan seems stuck will make it slower.
- **Grocery table:** three uploads returned 9, 8 and 9 items in 14–15 seconds. Salmon was read correctly once ("N-WAY SALMON PORTION") and called *chicken breast* once; couscous and guava appeared once. The three runs together found 10 of the 15 items; oats, honey, garlic butter, wraps and the chocolate bar never appeared.

### Photograph results across scene types

| Scene | Precision | Recall | F1 | Upload to results |
|---|---:|---:|---:|---:|
| Test 1: controlled, 8 items (3 runs) | 1.00 | 0.67 | 0.80 | 4–5 s |
| Test 2: refrigerator, 15 items | 0.82 | 0.60 | 0.69 | 35 s |
| Test 3: grocery table, 15 items | 0.78 | 0.47 | 0.58 | 14 s |
| Round 2 target | 0.85 | 0.80 | — | — |

The frozen household test ([vision-model-evaluation.md](vision-model-evaluation.md)) shows the same pattern for the selected Qwen2.5-VL 3B. Recall was 0.23 for refrigerators, 0.28 for shelves, 0.15 for pantries and 0.09 for grocery tables. Grocery tables returned nothing in 44% of runs.

Across all three tests, precision was acceptable and recall was below target, falling as the scene got fuller. Corrections were far above the 20% target (73% and 87% of ground-truth items), mostly because missed items had to be typed in. Ease met its target. The condition for changing the pipeline, a pattern across more than one scene type, was met.

### Why items were missed

Diagnostic runs on the two photographs and on development images (never frozen-test images) found four causes:

1. **Answers cut off and discarded.** On crowded photographs the model tried to list 24–25 items, reached the 1,200-token output limit (`done_reason: "length"`) and stopped mid-item. The backend parsed the answer as one JSON object, so the whole list was lost and the user saw no suggestions. Recovering the complete items turned a 16-item development refrigerator from 0 suggestions into 16 (7 correct). On a 24-item grocery table, the model had started repeating the same items until the limit. This is the likely cause of the frozen test's empty grocery-table runs.
2. **A list-length ceiling.** Every scan returned about 8–13 items regardless of how many were visible, and which items made the list changed from run to run. The model could read the missed labels (salmon, couscous and guava each appeared in some run); it did not list everything in one answer.
3. **Small unlabelled produce** (guava, avocado, chilli) was rarely named in a whole-photograph view.
4. **Brand names taken literally.** "Dairy Milk" became chocolate milk, and the walnut-bread label became sunflower seeds or walnuts.

The confidence threshold was not a cause: every returned item scored 0.8–1.0, so the 0.45 cut-off removed nothing.

A trial with the unchanged prompt on four overlapping quarters of each photograph (close-ups) found 14 of 15 grocery-table items and the refrigerator's guava, avocado, chilli and salmon, at about 43 seconds per photograph instead of about 15.

## Photo detection iteration 1

**Date:** 27 September 2026

### What changed

The model (Qwen2.5-VL 3B), prompt, temperature, image size and confidence threshold were not changed. Only how the app calls the model and handles its answer changed.

| Step | Problem it addresses | Change | Code |
|---|---|---|---|
| 1. Keep cut-off answers | Crowded photos lost the whole list when the answer hit the output limit | The answer is streamed and every complete item is kept. An answer that repeats earlier items three times in a row is stopped. The output limit rose from 1,200 to 2,048 tokens. How each pass ended, its output length, time and items added are saved with the scan (`vision_scans.pass_log`). | `vision_suggestions.salvage_items`, `is_repeating`; `model_services.ask_vision_model` |
| 2. Close-ups | The model lists only about 8–13 foods per image | After the whole photo, the same prompt is run on four overlapping quarters of the photo (15% overlap). The whole-photo list is shown straight away; each close-up adds only new foods, below the rows already shown, with a progress line. The user can confirm at any time, which stops the remaining close-ups. The photo is held in memory and its file deleted before any model runs. | `model_services.scan_pantry_photo`; streamed `/upload-image`; `IngredientSheet.tsx` |
| 3. Names and duplicates | Brand names taken literally; the same food named differently by different passes | Brand, store and marketing words are removed (*meiji milk* → milk). Product lines become their food (*Cadbury Dairy Milk* → chocolate), and a label renames an item only if it shares a word with the model's name, so "Nescafe" wrongly attached to a pepper changes nothing. Across passes, the same food is dropped; a less specific name is dropped (*pepper* after *bell pepper*); a more specific one is offered as a one-tap rename. Names stay apart when the shorter one lacks the food word (*chocolate* vs *chocolate syrup*) or a modifier makes a different food (*milk* vs *chocolate milk*, *butter* vs *peanut butter*). | `vision_suggestions.clean_food_name`, `SuggestionMerger` |
| 4. Units | The form showed any unit outside its list as *piece* | Model units are mapped onto the form's units: *package*, *packet*, *pouch*, *tray* and *loaf* → pack; *tub*, *container* and *punnet* → box; *jug* → bottle; *tin* → can. The form now reads plural units (*2 boxes*). | `vision_suggestions.form_unit`; `parseQuantity` in `utils.ts` |

One fix came from the development split, before the frozen test: the model sometimes copied the prompt's own words ("plain food name", "plain bread"), so the word *plain* and vague names (*unspecified*, *vegetables*) are removed.

`backend/tests/test_vision_suggestions.py` covers cut-off and looping answers, units, brand and label names, template words and cross-pass merging, and `test_photo_workflow.py` covers the streamed endpoint. All 73 backend tests pass.

### Results on the two photographs

The old and new pipelines were each run five times per photograph on the same machine, with the model already loaded. The old pipeline was rebuilt exactly (one request, 1,200-token limit, whole-answer parsing, old units), so both are scored identically against the participant's ground truth. The scored app run in Tests 2 and 3 is one sample of the old pipeline.

Five runs were needed because the model's answer to the same photograph varies widely. On the refrigerator it mostly gave one of two different lists, depending on the first item it named: one with the Godiva box and the cookies, the other with guava, avocado and salmon instead. Streaming and the output limit were ruled out as causes by testing them separately. All five of the participant's app scans gave the first kind, which is why guava, avocado and salmon never appeared there.

| Measure (5 runs each) | Refrigerator, old | Refrigerator, new | Grocery table, old | Grocery table, new |
|---|---:|---:|---:|---:|
| Precision | 0.82 | 0.64 | 0.80 | 0.74 |
| Recall | 0.49 | 0.75 | 0.55 | 0.81 |
| F1 | 0.62 | 0.69 | 0.65 | 0.78 |
| Recall range across runs | 0.00–0.73 | 0.67–0.80 | 0.47–0.60 | 0.73–0.93 |
| Correct / wrong suggestions per run | 7.4 / 1.6 | 11.2 / 6.2 | 8.2 / 2.0 | 12.2 / 4.2 |
| Missed items per run | 7.6 | 3.8 | 6.8 | 2.8 |
| Quantity and unit both correct | 49% | 41% | 54% | 61% |
| Count correct | 92% | 91% | 88% | 90% |
| First results, median (range) | 9.5 s (5.8–14.5) | 8.4 s (6.0–14.7) | 6.5 s (6.0–7.5) | 6.6 s (5.9–13.2) |
| All close-ups done, median (range) | — | 22.3 s (19.8–55.8) | — | 22.1 s (20.8–57.6) |

- **Cut-off answers:** one of the five old refrigerator runs hit the 1,200-token limit and returned nothing, as the participant would have seen. None of the 50 new passes were cut off or stopped for repeating on these photographs.
- **Items now found:** on the grocery table, couscous, the chocolate bar and salmon went from 0 of 5 runs to 5, 5 and 4; honey from 2 to 4; wraps from 0 to 2. On the refrigerator, oats went from 1 to 5, the bread from 1 to 4 and guava from 2 to 5. The guava on the grocery table was never found, and oats only once.
- **Whole-photo pass alone:** precision 0.79 and 0.88, recall 0.56 and 0.59. The close-ups added the rest of the recall, but only 41% (refrigerator) and 53% (grocery table) of their additions were correct.
- **Wrong suggestions that remain:**
  - Duplicates of listed items: *california walnut* beside *california walnut bread*, *cheese* beside *herbs & spices*, and a green bell pepper beside a yellow one.
  - Misreads that the old pipeline also made: the bread label as sunflower seeds, and the red pepper as a tomato.
  - Close-up guesses: egg, protein powder, apple for the guava half.
  - *Coffee* appeared in every refrigerator run. A Nescafé bottle is in the photograph but not on the participant's list; counting it as correct would raise refrigerator precision to 0.70.
- **Correction effort:** per run, the rows to fix (misses plus wrong suggestions) went from 9.2 to 10.0 on the refrigerator and from 8.8 to 7.0 on the grocery table. What changed is the kind of fix. About four typed additions per photograph became deletions, which take one tap. Whether that makes confirmation faster needs a timed repeat of Tests 2 and 3.
- **Units:** the form no longer shows every unknown unit as *piece*. Exact agreement with the participant's units improved on the grocery table (54% → 61%) but not on the refrigerator (49% → 41%), because the model's own unit often differs from the participant's choice: grapes as *bunch* not box, salmon as *pack* not piece, lettuce as *bag* not pack.
- **Speed:** first results arrive as quickly as before. In the real app, the grocery-table list appeared after 6.8 seconds and the close-ups finished at 23 seconds. The first run of each photograph took 55–58 seconds in total; later runs about 22 seconds.

### Results on the household development split

Twelve development images, one run each. The old figures are the recorded 3B development run from [vision-model-evaluation.md](vision-model-evaluation.md). The new figures include the *plain*/vague-name fix, applied to the stored answers.

| Pipeline | Precision | Recall | F1 | Empty | First results, median | Total, median |
|---|---:|---:|---:|---:|---:|---:|
| Old (recorded run) | 0.604 | 0.223 | 0.326 | 25% | 13.9 s | 13.9 s |
| New, whole photo only | 0.642 | 0.262 | 0.372 | 17% | 11.4 s | — |
| New, with close-ups | 0.357 | 0.431 | 0.390 | 0% | 11.4 s | 36.9 s |

The close-ups nearly doubled recall but only 21% of their additions matched a label, compared with 41–53% on the participant's photographs. Some of those "wrong" additions are right foods under a different name, because label matching is strict (*blueberries* against the label *blueberry*, *table salt* against *salt*); the old pipeline was scored the same way. Others are zoomed-in guesses: watermelon, cherries, corn, and one toaster. Ten of 60 passes were stopped for repeating and none hit the output limit.

### Results on the frozen household test

The 35-image frozen test was run once with the final code, after every change above, including the development-split fix, was settled. It had previously been used only for the 3B-versus-7B decision. Having now been seen, it is **no longer a blind test** for photo-pipeline changes; later changes need fresh photographs. The old figures are the recorded 3B runs (three per image; their F1 varied only from 0.218 to 0.222). Intervals are 2,000-sample image-cluster bootstraps, as in the model comparison.

| Pipeline | Runs per image | Precision | Recall | F1 (95% CI) | Empty | F1 change vs old (95% CI) |
|---|---:|---:|---:|---:|---:|---:|
| Old | 3 | 0.334 | 0.163 | 0.219 | 11.4% | — |
| New, whole photo only | 1 | 0.387 | 0.218 | 0.279 (0.212–0.334) | 6% | +0.060 (+0.009 to +0.121) |
| New, with close-ups | 1 | 0.225 | 0.317 | 0.263 (0.199–0.311) | 0% | +0.044 (−0.032 to +0.123) |

| Scene (images) | Old recall / F1 | Whole photo recall / F1 | With close-ups recall / F1 |
|---|---:|---:|---:|
| Refrigerator (11) | 0.233 / 0.278 | 0.254 / 0.308 | 0.317 / 0.238 |
| Refrigerator shelf (9) | 0.278 / 0.300 | 0.286 / 0.324 | 0.357 / 0.248 |
| Pantry (9) | 0.152 / 0.181 | 0.152 / 0.182 | 0.239 / 0.172 |
| Grocery table (3) | 0.086 / 0.152 | 0.235 / 0.325 | 0.370 / 0.400 |
| Drawer (1) and other (2) | 0.033 / 0.061 | 0.050 / 0.091 | 0.200 / 0.195 |

- **Steps 1, 3 and 4 improved held-out results.** Whole-photo F1 rose by 0.060 and the interval excludes zero. Empty results halved, and grocery-table recall nearly tripled, which is the cut-off fix at work.
- **Close-ups did not pay off on held-out photos.** They nearly doubled recall over the old pipeline (0.163 → 0.317), but only 25 of their 214 additions (12%) were correct: about 0.7 correct and 5.4 wrong suggestions per photograph. Compared with the whole-photo pass alone, F1 changed by −0.016 (−0.060 to +0.023). They raised F1 only on grocery tables and on the three drawer and other images. On the participant's two photographs, 41–53% of close-up additions were correct. Those photographs held fewer, larger, clearly labelled items, and they were used to design the close-ups, so they flattered them.
- **Timing is not representative.** After the run the test Mac's battery was at 7% and it was swapping heavily. Ollama's model runner had grown from about 2.5 GB to 12 GB after roughly 250 image requests in the session, and output speed fell about tenfold from the first images to the last. A grocery-table call that took about 6 seconds earlier took 23–49 seconds afterwards. The measured medians (first results 18.4 s, all passes 70.9 s, grocery tables 188 s) are upper bounds. On the first three test images, first results took 6–11 seconds and all passes 24–36 seconds, in line with the participant's photographs. Latency needs re-measuring on a charged, freshly started machine.

### Trade-offs and limitations

- **Close-ups add mostly wrong suggestions on typical scenes.** Each is one tap to delete, but many of them undermine trust in the list.
- **Longer total wait.** First results arrive as before, but all close-ups take about 15 more seconds on a healthy machine, and more on crowded scenes.
- **Large run-to-run variation.** The same photograph can give quite different lists, so one run per image is a noisy measure of a single photograph. The aggregate over 35 images is stable.
- **Development evidence.** The participant's two photographs and the development split were used to design and check this iteration. The brand and product lists include brands seen there (Cadbury, meiji, Godiva, Nescafé, Arla, FairPrice, Sunshine, Farmers Union) and will need additions for other shops.
- **Duplicates remain:**
  - a label copied as a name beside the real item (*california walnut* next to *california walnut bread*);
  - colour variants (a green and a yellow bell pepper);
  - two names for one item (*herbs & spices* and *cheese*).
- **Units.** The form now shows the model's unit, but the model's choice often differs from the user's.
- **Memory use.** Ollama's runner grew to about 12 GB over a long session. Close-ups send five image requests per photograph, so this should be watched in longer use.
- **Participant measures not repeated.** Correction time, confirmation time, confidence and ease with the new form need a new session.

### Recommended next steps

1. Keep steps 1, 3 and 4: they improved held-out F1 and have no known downside.
2. Stop running close-ups automatically on every photograph. Options, in order: a *Look closer for more items* button after the first list, so the user chooses extra recall along with its wrong suggestions; marking close-up rows as *found in a close-up, please check*; trying two larger halves instead of four quarters. Until then, `MEALMATCH_VISION_CLOSE_UPS=0` switches them off.
3. Repeat Tests 2 and 3 with the participant using the new form, timing corrections and confirmation, and test on new photographs that no one has used.
4. Re-time the pipeline on a charged, freshly started machine.

### Report-ready summary

> Round 2 refrigerator and grocery-table photographs confirmed the frozen-test pattern: Qwen2.5-VL 3B was reasonably precise (0.82 and 0.78) but missed many items (recall 0.60 and 0.47), and 73–87% of ground-truth items needed a correction. Diagnosis found pipeline faults rather than a model limit: answers on crowded photographs were cut off and discarded, the model lists only about 8–13 foods per image, brand names were taken literally, and the form showed unknown units as "piece". The iteration kept the model, prompt and threshold. It recovers cut-off answers, cleans names, maps units and adds four close-up passes streamed into the confirmation form. On the frozen test, the whole-photo changes raised F1 from 0.219 to 0.279 (paired difference +0.060, 95% CI +0.009 to +0.121) and halved empty results. The close-ups raised recall from 0.163 to 0.317 but cut precision to 0.225, leaving F1 unchanged relative to the whole-photo pass. On the participant's photographs recall reached 0.75 and 0.81, but those photographs had informed the design. Close-ups should therefore become an optional user action rather than run on every photograph, and human confirmation remains essential.

### Change after iteration 1: close-ups on request

Next step 2 has been carried out with the first option (see [Decision 36](decision-log.md#decision-36-close-ups-on-request-shorter-model-hold-and-pinned-model-versions)).

- **What the user sees.** Uploading a photograph runs the whole-photo pass only. Under the list, a *Look closer for missed items* button runs the four close-ups on the same photograph. It warns that extra items are more often wrong. New items are added below the list, and the button disappears once the close-ups have run.
- **What is recorded.** The close-ups are added to the same scan record, and each pass notes whether the user asked for it. The vision-study summary reports `looked_closer` per scan, so a repeat of Tests 2 and 3 can show how often participants choose the extra check and what it costs them in corrections.
- **Memory.** Ollama reported 4.6 GB for the photo model while loaded, 2.6 GB for the text model and 7.1 GB for both. The photo model now leaves memory 5 minutes after the last scan instead of 30. Loading it took 1.4 seconds once cached, and loading starts when the Photo tab opens.
- **Browser check** (grocery-table photograph, once). The whole photo gave 12 suggestions and no close-ups ran. *Look closer* added 5 more: *couscous*, *wholemeal wraps* and *salmon* were correct, while *green apple* (probably the guava) and the label duplicate *california walnut* were not. The machine was at 20% battery during this check: the whole-photo pass took 18 seconds and the close-ups 47 seconds, about twice the times above. Latency still needs re-timing on a charged, freshly started machine (next step 4).
- **Where the time goes.** On the fridge photograph, each pass spent about 7 seconds reading the image (about 2,900 input tokens at 1,600 pixels) and 2–5 seconds writing the list. A smaller image size would shorten the reading step. It has not been evaluated and would need the development split before any use.

The frozen-test numbers above are unchanged: `evaluate_photo_pipeline.py` now always runs the close-ups, so it still measures both stages.

## Design iteration 2: AI recipe ideas and hands-free cooking

Round 2 participant feedback raised two further problems, outside photo detection. Both were diagnosed in the code and fixed. The same participant cohort subsequently re-tested the affected features; the post-iteration findings are reported below.

### AI recipe ideas

**What the participant saw.** Asking the AI recipe generator for *ice cream* returned "Creamy Tomato Ice Cream Pie" and "Quick Ice Cream Tomato Bites". The pictures for the ideas took a long time to appear. Some recipes appeared twice in the recipe collection, as two cards for the same dish.

**Diagnosis.**

- *Nonsense recipes.* Before writing a recipe, MealMatch picks which pantry foods to offer the model by comparing the request with the reference recipe collection. "ice cream" was split into "ice" and "cream". *Cream* appears in savoury reference dishes (creamy soups, gratins), so the participant's pantry was offered *whipped cream, ice cream, red onion, onion, grape tomato, tomatoes, avocado, potatoes, cheese*. The 3B model then used them. The same batch-level problem produced two brownies with black pepper and chilli flakes.
- *Duplicates.* There were two causes. First, within one batch of three ideas, the model sometimes ignored the instruction to give a different dish: two "Classic Brownie" recipes were saved from one request. Second, `/recipes` and `/recommend` listed "recipes with a photo" and then "all AI recipes". Every AI recipe that had been given a photo was therefore listed twice, which the browser reported as a duplicate card key.
- *Slow pictures.* FLUX.2 Klein through Ollama holds 5.7 GB whenever it renders, whatever the picture size. On the reference M4 Pro (idle, charged) one photo took 15–16 s at 768×576 including loading, 9.9 s at 512×384, and 5.9 s at 512×384 with two denoising steps. The photos also waited until all three recipes had been written, because the text and image models slow each other down on the same GPU.

**What changed.**

1. Compound foods stay one term ("ice cream", "sour cream", "sweet potato"). A sweet request is compared only with sweet reference dishes. Savoury pantry foods (onion, garlic, tomato, potato, meat, fish, chilli…) are never offered for it unless the request names them. For the participant's pantry, *ice cream* now offers *ice cream, eggs, milk, almonds, lemon*.
2. After generation, a dessert that still contains savoury ingredients is rejected and regenerated with the reason. It is never kept as a fallback. The prompt now says that the title must name the requested dish and that sweet and savoury are kept apart.
3. An idea that repeats one already shown in the batch is regenerated. A repeat is the same title words, or three-quarters of the same main ingredients. If the same dish was created by an earlier request, the saved recipe is reused instead of saved again. Each recipe is listed once, and the app also removes duplicate cards.
4. AI recipes saved before these checks that fail the dessert check are hidden. In the participant's database that is 4 of 12: both ice cream dishes and both peppered brownies. Nothing is deleted.
5. Recipe photos are off by default. AI recipes show a title card, drawn at once and using no memory. The photo model can be switched back on (`MEALMATCH_LOCAL_IMAGE_MODEL=x/flux2-klein`) and then renders at 512×384.

**Evidence.** Tests in `backend/tests/test_recipes_and_cooking.py` cover the ice cream offer, the savoury-dessert rejection, a repeated idea under a new name, the reuse of an earlier identical recipe, and a photographed AI recipe appearing once.

**Participant re-test.** The same participant cohort described the redesigned AI
recipe-generation flow as quicker. This is a qualitative result: post-iteration
timestamps were not retained, so no numerical latency reduction or median is
claimed for recipe generation.

### Hands-free cooking

**What the participant saw.**

- Saying "Hey Mimi" did not turn on hands-free mode until it had been turned on once with the button.
- Any phrase containing "next" made Mimi read out the next step, but sometimes the step card on screen stayed where it was.
- On the last step, saying "done" (or anything similar) left the session stuck. Only the "Meal is ready" button finished it.

This matches the round 2 plan's rule that a correct spoken answer is not a success if the visible step does not change.

**Diagnosis.**

- *Next without moving.* "What's next" matched a read-only rule: Mimi spoke the next step without moving to it. Other phrases with "next" that were not exact commands ("okay next", "next please") went to the language model. It had the recipe as context, so it also read out the next step, while the session stayed on the current one.
- *Stuck on the last step.* "Done" was not a command, so it also went to the language model. Finishing by voice needed the exact phrase "finish cooking" plus a spoken confirmation, while the button finishes at once.
- *Wake word.* The listener had several faults, all found in code review. The participant's exact browser could not be re-run, so which one they hit is not certain.
  - In development React mounts components twice. The first listener was stopped, but its restart handler still ran, so two listeners kept restarting and cutting each other off.
  - Only the exact text "hey mimi" counted, while recognisers often return "Hey, Mimi" or "hey mimmy".
  - A refused or unanswered microphone permission switched the listener off without telling the user.
  - The recognition language was fixed to en-SG.
  - When started by voice instead of a tap, the audio set-up could wait for a user gesture.

**What changed.**

1. Each transcript becomes exactly one action (`frontend/src/voiceCommands.ts`).
   - Any phrase with "next", and "done" or "finished" before the last step, moves the card.
   - The card moves at the moment Mimi starts reading, and the server then confirms.
   - "Go back", "go to step three" and "wait, not yet" are also understood.
2. On the last step, "done", "finished", "next", "that's it" and "the meal is ready" do what the "Meal is ready" button does. Before the last step, "the meal is ready" asks for confirmation because steps remain.
3. The wake listener was rebuilt:
   - each listener stops for good when it is removed;
   - punctuation and common mishearings still count;
   - the browser's own English variant is used, with en-US as a fallback;
   - a refused microphone shows "Tap Start voice once to let Mimi hear 'Hey Mimi'";
   - starting by voice never waits for a gesture.

**Evidence.** `frontend/tests/voiceCommands.test.ts` covers more than 30 phrases: next phrasing, last-step finishing, navigation, questions and wake-word variants. Speech recognition itself cannot run in the automated tests.

**Participant re-test.** The same participants tested the feature again after
the redesign. Every attempted natural verbal indication that the participant
wanted to move on caused the visible recipe card to advance. This addresses the
earlier failure in which Mimi could speak the next instruction while the card
remained on the previous step. The exact number and wording of re-test attempts
were not retained, so this finding is reported descriptively and is not expressed
as a new success percentage. It applies to the phrases tested, not every possible
utterance.

### Post-iteration timing summary

The three retained photo-analysis runs in Test 1 took `5`, `4` and `5` seconds,
giving a mean of `4.67` seconds, a median of `5` seconds and a range of `4–5`
seconds. The earlier ten participant observations had an approximate median of
`23.75` seconds. The observed median therefore decreased by `18.75` seconds, or
`78.9%`.

This is useful iteration evidence, but it is not a paired same-image comparison:
the post-iteration result contains three repeated runs of one photograph, while
the initial values came from different participant photographs and included
ranges. Hardware state, model warm-up and image complexity may also affect the
result. The comparison should not be presented as a population-level latency
estimate.

### Further testing

In a future session, retain each hands-free transcript, predicted intent and
visible-card state so that a post-iteration success rate can be calculated. Also
record instrumented recipe-generation time and repeat the photo task with the
same images and hardware conditions before making a causal or general latency
claim.

## Design iteration 3: taste requests, pictures, returning from a recipe and swaps

Further testing of the iterated build raised seven problems. Each was diagnosed in the code and changed. The decisions are 42 to 46 in the [decision log](decision-log.md). The same participant cohort then re-tested the changes; the results are in [Participant re-test of iteration 3](#participant-re-test-of-iteration-3).

### Sweet requests

**What was seen.** "Sweet dish with what I have in my pantry" returned "Limey Beef Fritters", "Beef and Carrot Fritters", "Sweet Potato and Carrot Cake" and "Sweet Beef and Carrot Fritters".

**Diagnosis.** "Sweet" was on the list of filler words, so the request named no food or dish. The pantry selector then built the recipe around the food expiring first, the beef sirloin due that day, with the foods that go with it in reference dishes: onion, garlic butter, carrot and potatoes. Because the request was not recognised as sweet, the dessert check from iteration 2 did not run.

**What changed.**

1. A taste word sets what the dish must taste like, unless it is part of a food's name ("sweet potato", "sweet chilli"). Next to a named savoury food it describes a sauce ("sweet and sour chicken"). "Savoury" works the same way in the other direction.
2. A sweet request that names no dish is offered the sweet foods that expire first, then the dessert basics that sweet reference dishes use. Each food is offered once, and expired or savoury food never.
3. The prompt states the taste, and "with what I have" asks for pantry foods and basic staples only.
4. A recipe is regenerated when:
   - its taste is wrong;
   - it has nothing sweet in a sweet dish;
   - its title names a pantry food it does not use.
5. If one of the three ideas fails its checks, the next one is still tried.

**Evidence.** For the participant's pantry the request now offers blueberries, raspberries, strawberries, banana, dates, kiwi, eggs, milk and almonds. Two live runs used a copy of the participant's database:

- The first gave "Berry Crumble Muffins", "Almond Banana Pancakes" and "Banana Date Bites". The last listed neither banana nor dates, which led to the title check.
- The second gave "Strawberry Banana Pancakes", "Strawberry Almond Crumble Parfait" and "Almond Berry Crumble Muffins", in 1, 2 and 3 attempts.

`backend/tests/test_recipes_and_cooking.py` covers the taste words, the dessert offer and each check.

### Recipe pictures

**What was asked.** Remove photo generation unless there is a quicker way. Keep the text part of the AI idea cards, and use the ingredient emojis as the picture on the recipe page.

**Decision.** FLUX.2 Klein, the smallest image model offered through Ollama, holds 5.7 GB and took about 10 s a photo. A faster distilled model would still add a second image library, a multi-gigabyte download and gigabytes of memory, so generation was removed. AI idea cards now show the idea number, time, name, pantry match and actions. Recipe pages, recipe cards and the cooking header show the recipe's main foods as emojis on a plate, with foods named in the title first.

### Loading screen

The pink icon with three orbiting emojis was removed. The loading screen shows the green MealMatch mark and "MealMatch is loading".

### Cooking screen

The cooking screen's panels were plain white. They now use the panel colours of the other screens:

- a green header;
- a gold timer;
- an apricot voice panel;
- a cream step card;
- alternating step cards.

This applies in both light and dark themes.

### Returning from a recipe

**What was seen.** Going back from a recipe returned to the top of the list. The other AI ideas had disappeared.

**Diagnosis.** The recipe page replaced the whole screen. The list and its ideas were removed, then rebuilt from nothing on the way back.

**What changed.** The screen stays mounted, hidden, under the recipe, and its scroll position is restored. AI ideas are held by the app for the browser session until a new request or the new "Clear ideas" button. Recipe cards made in the assistant chat are kept with the chat history.

**Evidence.** In a browser run:

- the list was scrolled to 2,600 px, a recipe was opened and closed, and the list was back at 2,600 px;
- the three ideas remained after opening one and after switching tabs;
- "Clear ideas" removed them.

### Swaps

**What was seen.** Swap often found no substitute.

**Diagnosis.** Several faults combined:

- swaps were worked out only for missing ingredients, so tapping Swap on a food the cook had always failed;
- all missing ingredients went to the model in one call, and it skipped some and renamed others ("fresh basil leaves" came back as "basil"), which then matched nothing;
- the 13-food fallback list was used only when the model's whole answer failed.

**What changed.** Swaps are fetched for the ingredient tapped, in this order:

1. pantry foods of the same kind;
2. a table of standard substitutions for about 100 foods, each with how to use it;
3. the model, told the dish, only when fewer than three swaps are found.

Allergies and diets are checked, and at most three swaps are shown, pantry foods first.

**Evidence.** In a browser run, all 8 ingredients of an AI pancake recipe had swaps.

### Participant re-test of iteration 3

The same participant cohort used the iteration 3 build for the same tasks. This was a formative re-test of the redesigned prototype, not a new, independent sample.

| Area | Before iteration 3 | After iteration 3 | Evidence |
|---|---|---|---|
| AI recipe generation time | Two of nine text-feature participants felt that loading all three ideas took longer than expected | The median generation time was lower than before | Observed timings; the before and after values were not added to this repository, so the size of the reduction is not stated here |
| Relevance of AI recipes | A sweet request returned beef and vegetable dishes | Participants found that the generated recipes matched what they asked for and made better use of their pantry ingredients | Participant observation |
| Swap feature | Mean usefulness 3.86/5 (n = 7); some ingredients had no swap | Participants rated the swap feature as more useful than before | Participant ratings; the post-iteration values were not supplied |
| Overall usability | Returning from a recipe lost the scroll position and the other AI ideas | Participants reported higher usability. The AI idea cards stayed after opening one, and the recipe list kept its scroll position | Participant observation; SUS was not administered |

These results support iteration 3 for the tasks tried. They are formative: the cohort had already seen the application, and the numeric values behind the timing and rating changes are not retained here. A future round should record per-request generation time and per-participant swap ratings so that the change can be quantified.

### Changes after iteration 3

- **The tour opens by itself.** "See how it works" now plays once per browser session when the app first loads, after the opening film, on whichever screen the app opens. It was previously shown only the first time a browser reached the Home screen, so returning users never saw it again. Its screenshots were re-captured from the current design, and the capture script now reads streamed photo results. `?skipTour=1` skips it.
- **Swap tags readable in dark mode.** In-pantry swaps had a light green card that made the text unreadable in the dark theme. Every swap now uses the same card, and only its tag differs: green "In pantry" and amber "Alternative", each with a dark-theme colour.

