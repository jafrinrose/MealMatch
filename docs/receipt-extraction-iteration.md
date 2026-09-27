# Receipt extraction: design iteration 2

**Date:** 27 September 2026
**Related:** [Decision 34](decision-log.md#decision-34-parse-receipt-lines-in-code-and-let-the-model-only-name-them),
[User testing round 1, §5.3](user-testing-round-1.md)

## Summary

Receipt scanning moved from one free-form language-model step to a split
pipeline. Deterministic code now finds the product lines on the receipt,
reads the quantities printed on it and expands abbreviations. Llama 3.2 3B
only gives each numbered line a plain ingredient name and says whether it is
food. The model can no longer skip a line, invent an item, or lose a
repeated purchase, and every confirmation row shows the receipt text it came
from.

## Iteration history

| Iteration | Trigger | Design | Outcome |
|---|---|---|---|
| 0: initial prototype | — | Tesseract OCR, then one prompt asking Llama for a JSON array of ingredient names; duplicates removed | Two shrimp became one item (Round 1) |
| 1: after Round 1 | Round 1 findings on abbreviations and repeats | Prompt rules for abbreviations and "one array entry per purchased unit"; the browser counted repeated names into "N pieces" | Still missed abbreviations and invented items on a participant's real receipt |
| 2: this change | Participant's real wholesale receipt | Code parses lines and quantities; the model only names numbered lines | All 49 expected rows correct on four receipts; limits below |

## What triggered this iteration

Iteration 1 was run on a real 16-unit wholesale receipt from a participant. The
confirmation page showed:

- **Missed abbreviations:** `B/S THIGHS` (boneless skinless chicken thighs) and
  `ARTISAN BGT` (baguette) did not appear.
- **Wrong product:** `KALAMATA OLV` (olives) became *olive oil*.
- **Invented item:** *water* was listed although no water was on the receipt.
- **Quantities at risk:** repeated lines (`ARTISAN BGT` ×3, `16/20 SHRIMP` ×2)
  only produced a quantity if the model happened to repeat the name the same
  number of times.

## Root cause

One prompt did five jobs at once: find the items, expand abbreviations, count
repeats, drop non-food products and clean the names. The model's answer was a
flat list of strings with no link back to receipt lines, so:

- nothing stopped it from leaving lines out or adding products;
- counting depended on the model repeating strings exactly;
- two different foods with the same base name (whole and skim milk) could be
  collapsed into one;
- sizes and weights printed on the receipt (`4L`, `1.24 kg`) were ignored, so
  every row defaulted to pieces;
- the backup non-food filter matched substrings, so `bag` also blocked
  *bagel* and *cabbage*;
- the model ran at default temperature, so the same receipt could give
  different results on different runs.

## New design

```
receipt photo
  → OCR preprocessing + Tesseract            (ocr_services.py)
  → product lines, quantities, hints          (receipt_parsing.py, no model)
  → Llama names each numbered line            (ai_services.py, JSON schema)
  → name guard + non-food check               (ai_services.py)
  → one row per ingredient and unit           (receipt_parsing.py)
  → confirmation page, user edits and saves   (IngredientSheet.tsx)
```

1. **OCR preprocessing.** The photo is turned upright, converted to greyscale,
   contrast-stretched and upscaled to about 2000 px on its long side (at most
   2×) before Tesseract reads it. This removed most garbled prices and item
   codes on phone photos.
2. **Line parsing in code.** `parse_receipt_lines` keeps lines that have a
   price or item code and appear before the total. It drops header, address,
   date, payment, discount and "items sold" lines. It strips item codes and
   prices, and attaches weight lines (`1.24 kg @ $1.52/kg`) to the product
   above them.
3. **Quantities in code.** The parser counts repeated lines and reads stated
   counts (`3 @ 1.29`, `x3`, `2 x`, `QTY 2`), weights (`kg @`, `lb @`) and pack
   sizes (`4L`, `750G`, `12CT`, `6PK`, `10LB`). Pounds and ounces are converted
   to kilograms and grams.
4. **Abbreviation hints.** `expand_abbreviations` combines hard-coded lists
   with rules that work out abbreviations missing from those lists (see
   [How abbreviations are expanded](#how-abbreviations-are-expanded)). The
   result is passed to the model as a hint, not used as the final name.
5. **The model names lines, nothing more.** Llama 3.2 3B answers a JSON schema
   with one required key per line number: the receipt text, the ingredient name
   and a food flag, in that order. It runs at temperature 0 with a fixed seed
   and a capped output length. Because the keys are fixed, it cannot add a line
   (the invented *water*) or skip one. Naming comes before the food flag because
   deciding "food" first marked baguettes as non-food.
6. **Name guard.** If the model only dropped words from the receipt line
   (*milk* for `WHL MLK`), the receipt's own words are restored, so whole and
   skim milk stay separate. Brand and marketing words are removed, and a line
   naming only a cut (`B/S THIGHS`) becomes *chicken thigh*.
7. **Non-food check.** A line is dropped if the model says it is not food, or
   if its name or expanded receipt text contains a whole word from the non-food
   list (soap, paper towel, batteries, toothpaste, pet food…).
8. **Merge.** Rows with the same ingredient and unit are merged and their
   quantities added. Each row carries its receipt text, shown on the
   confirmation page as *On receipt: "ARTISAN BGT ×3"*.
9. **Warnings.** A warning is shown if the model did not answer for some lines
   (their receipt words are used instead) or if the receipt's "items sold"
   count is higher than the number of units read.

### How abbreviations are expanded

Abbreviations are handled by a mix of hard-coded lists and code rules. Each
word on a product line is tried against these steps in order, and the first
one that gives an answer is used:

| Step | Kind | How it works | Example |
|---|---|---|---|
| 1. Table | Hard-coded | `ABBREVIATIONS` maps 102 known receipt abbreviations to words, including a few non-food ones so the model can see what the line is | `BGT` → baguette, `B/S` → boneless skinless |
| 2. OCR letter swap | Rule over the table | Swaps one letter Tesseract often misreads (Y↔V, O↔0, S↔5, B↔8…) and looks the result up in the table again. The swap list `OCR_CONFUSIONS` is hard-coded | `OLY` → `OLV` → olives |
| 3. Vowel-less match | Worked out by code | A word with no vowels is compared with 309 grocery words spelled out in full (`GROCERY_WORDS`). A word matches if it starts with the same letter and contains the abbreviation's letters in order, and the abbreviation keeps at least 75% of its consonants. The closest match wins; if two words match equally well, no hint is given | `BRKFST` → breakfast, `CHDR` → cheddar, `SPNCH` → spinach |
| 4. No match | — | The word is passed on unchanged | `PTTO` stays `ptto` |

The results of steps 1–3 are never used as the final name. The model gets the
receipt text and the hint side by side, writes the ingredient name itself, and
the name guard (step 6 above) checks it. So the model can still fix a wrong
hint or work out an abbreviation that no step matched.

Step 3 was added after the holdout receipt showed that the table alone missed
unseen abbreviations. It covers most unseen abbreviations without growing the
table, because receipts usually shorten words by dropping vowels.

### Who does what

| Task | Iteration 1 | Iteration 2 |
|---|---|---|
| Find product lines | Model | Code |
| Count repeated lines | Model repeats names; browser counts them | Code |
| Read sizes, weights, counts | Not done | Code |
| Expand abbreviations | Model, from prompt examples | Code gives a hint (hard-coded lists + rules); model writes the name |
| Name the ingredient | Model | Model, checked by the name guard |
| Decide food or non-food | Model + substring denylist | Model + whole-word denylist |
| Link row to receipt text | None | Every row |

## Evidence

Test receipts: three rendered receipts in `backend/tests/fixtures/receipts/`
(photographed look: tilt, blur, JPEG noise) and the participant's real
receipt, which is kept out of the repository because it contains personal
data. Together they have 49 expected rows and 11 non-food products. Rows were
checked on the confirmation page itself.

| Receipt | Rows correct | Non-food products | Tests covered |
|---|---|---|---|
| Participant's real receipt | 13/13 | — | `B/S THIGHS`, `ARTISAN BGT` ×3, `16/20 SHRIMP` ×2, `KALAMATA OLV`, `PRSDNT BRIE`; no invented water |
| Market (rendered) | 13/13 | 4 of 4 removed | whole vs skim milk, red vs yellow onion, olive oil vs olives, `750G` ×2 → 1500 g, `1.24 kg @`, `3 @` |
| Wholesale (rendered) | 11/11 | 3 of 3 removed | `10LB` → 4.54 kg, `8KG`, `3CT`, `24PK`, item codes, discount line |
| Holdout (rendered) | 8/12 first run, 12/12 after fixes | 4 of 4 removed | `2 x`, `x3`, `£/kg`, unlisted abbreviations (`BRKFST`, `CHDR CHS`, `BBY`) |

- The first line-based version scored 32/37 on the first three receipts with
  both Llama 3.2 3B and Qwen2.5 3B; Qwen merged whole and skim milk. The final
  version scores 37/37 with Llama.
- The holdout receipt was written after tuning and run once unchanged. Its
  four misses came from an OCR misread the parser did not handle (`0.512 kg`
  read as `@.512 kg`) and abbreviations missing from the table, which led to
  the vowel-skeleton match.
  After those general fixes it scored 12/12, so it is **no longer a blind
  test**.
- On the confirmation page each receipt took 5–8 seconds.
- `backend/tests/test_receipt_parsing.py` holds 11 unit tests covering line
  parsing, stated quantities, abbreviations, the name guard, non-food removal,
  invented items and warnings. All 58 backend tests pass.

## Code removed or replaced

| Old code | Status |
|---|---|
| `extract_ingredients_from_receipt_text` (`ai_services.py`) | Replaced by `extract_receipt_items` |
| `extract_json_array` (`ai_services.py`) | Removed; it only served the old flat list |
| Inline substring non-food list | Replaced by `NON_FOOD_TERMS` and whole-word `is_non_food` |
| `aggregateReceiptIngredients` (`App.tsx`) | Removed; the backend now returns merged rows with quantities |
| `detected_ingredients` field in `/upload-receipt` and `/upload-image` responses | Removed; only the removed fallback read it |

`receipt_prompt` in `backend/text_evaluation/evaluate_text_models.py` still
uses the old free-form task. It is kept on purpose: it belongs to the frozen
text-model comparison (Decision 33), and changing it would alter that
recorded result.

## Trade-offs and limitations

- **Tuned on the test receipts.** The rules were developed on these four
  receipts, and the holdout was used for fixes. Accuracy on other stores is
  not yet measured.
- **Units only come from the receipt.** Rows without a printed size or weight
  use pieces, because the model's unit guesses were mostly wrong. If OCR
  misreads the size, the unit is lost: on the real receipt `WHIP CREAM1L` was
  read as `WHIP CREAMIL`, so the row shows 1 piece instead of 1 l.
- **Upkeep.** The abbreviation table, letter-swap list and grocery word list
  are hard-coded and need occasional additions for new stores.
- **Abbreviations that keep a vowel.** The vowel-less match skips any word
  containing a vowel, so an unlisted abbreviation such as `PTTO` (potato) gets
  no hint and only the model can work it out.
- **No numeric baseline.** Iteration 1 was not scored on the same receipt set,
  so the improvement is shown by the failures it fixed, not by a before/after
  score.
- **One unexplained slow run.** During evaluation one run took 560 seconds and
  two uploads stalled. This did not happen again in nine later uploads; an
  output-length cap was added as a precaution.
- **Human confirmation stays.** The user still checks, edits and confirms every
  row before anything is saved.

## Next evidence

In Round 2, participants should scan their own receipts. For each receipt,
record rows added, deleted and edited on the confirmation page and the time to
confirm. This checks the pipeline on unseen stores and answers the Round 1
action "requires Round 2 validation" for receipt abbreviations.
