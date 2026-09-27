# MealMatch User Study: Observer Worksheet

> Use only after ethics approval. Complete one copy per participant. Do not
> write the participant's name on this worksheet.

## Session details

| Field | Entry |
|---|---|
| Participant code | P__ |
| Date | |
| Device/viewport | |
| Session start/end | |
| Aged 18 or over confirmed | Yes / No |
| Consent form signed | Yes / No |
| Cooking frequency | Rarely / Sometimes / Often |
| Grocery-management frequency | Rarely / Sometimes / Often |
| Technical confidence | 1 2 3 4 5 |
| Prior recipe/pantry-app use | None / Some / Frequent |

Stop the session if adult status or informed consent is not confirmed.

## Core task record

Use `S` for success without help, `P` for partial success and `F` for failure.
Facilitator prompts are hints or instructions not included in the task wording.

| Task | S/P/F | Time (s) | Errors | Prompts | SEQ 1–7 | Key observation |
|---|---|---:|---:|---:|---:|---|
| Explain MealMatch's purpose | | | | | | |
| Add pantry items from supplied photo | | | | | | |
| Correct quantities/categories | | | | | | |
| Add pantry items from supplied receipt | | | | | | |
| Find a waste-aware recipe | | | | | | |
| Apply recipe filters | | | | | | |
| Request and choose an AI recipe | | | | | | |
| Find a safe in-pantry substitution | | | | | | |
| Complete hands-free cooking commands | | | | | | |
| Recover and cancel a cooking session | | | | | | |
| Convert assistant request to recipe cards | | | | | | |
| Set a fictional custom preference | | | | | | |

## Photograph and receipt results

| Measure | Photograph | Receipt |
|---|---:|---:|
| Ground-truth food items | | |
| True positives | | |
| False positives | | |
| False negatives | | |
| Quantity corrections | | |
| Renames/category corrections | | |
| Model inference time (s) | | |
| Total confirmation time (s) | | |

Receipt-specific checks:

| Check | Result |
|---|---|
| Non-food item excluded | Yes / No |
| Abbreviation normalised | Yes / No |
| Repeated line preserved/aggregated | Yes / No |

## Text-model tasks

Use only the approved fictional scenarios. Copy the exact input and output to
the coded study file; do not enter personal details here.

| Task | Output valid/correct? | Participant corrections | Latency (s) | Correctness 1–5 | Usefulness 1–5 | Clarity 1–5 | Appeal/relevance 1–5 |
|---|---|---|---:|---:|---:|---:|---:|
| AI recipe | | | | | | | |
| Substitution | | | | | | | |
| Cooking answer | | | | | | | |

## Hands-free command attempts

Do not retain raw audio. Record the participant's wording from observation and
the transcript returned by MealMatch. Mark interface success separately from
transcription and intent success.

| Attempt | Expected action | Observed phrase | Whisper transcript | Predicted intent | Transcript correct? | Intent correct? | Interface correct? | Latency (s) | Retry? |
|---:|---|---|---|---|---|---|---|---:|---|
| 1 | Next step | | | | | | | | |
| 2 | Repeat step | | | | | | | | |
| 3 | Time remaining | | | | | | | | |
| 4 | Previous step | | | | | | | | |
| 5 | Current step | | | | | | | | |
| 6 | Help | | | | | | | | |
| 7 | Stop listening | | | | | | | | |
| 8 | Confirm/decline | | | | | | | | |
| 9 | Natural wording A | | | | | | | | |
| 10 | Natural wording B | | | | | | | | |

## Post-study ratings

Administer the standard 10 System Usability Scale items separately, preserving
their original wording and scoring. Record the calculated score here only after
checking the scoring procedure.

| Measure | Result |
|---|---:|
| SUS score (0–100) | |
| Trust in photograph suggestions (1–5) | |
| Trust in receipt suggestions (1–5) | |
| Trust in AI text outputs (1–5) | |
| Trust in hands-free commands (1–5) | |
| Confidence in final pantry state (1–5) | |
| Perceived help with food waste (1–5) | |
| Perceived help with meal decisions (1–5) | |

## Interview notes

**Most useful feature and reason:**


**Least useful or least trusted feature and reason:**


**Most difficult correction or task:**


**Whether spoken and visible cooking state felt consistent:**


**One priority improvement:**


**Other observations:**


## Optional anonymous quotation

Record a quotation only if the participant selected the quotation permission on
the consent form. Remove names, workplaces, locations and other identifying
details before using it.

> 

## Session close-out

- [ ] Participant was reminded of the withdrawal deadline and contact method.
- [ ] Temporary uploads were checked/deleted according to the protocol.
- [ ] Free-text records were reviewed for accidental personal information.
- [ ] Worksheet was moved to the approved encrypted storage location.
- [ ] Consent form was stored separately.
