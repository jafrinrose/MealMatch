# MealMatch Combined Formative User-Testing Results

## 1. Scope and evidence boundary

This report consolidates the supplied formative observations for ten anonymous
participants (`P01`–`P10`). `P01` is the participant previously reported in
the Round 1 pilot and is counted once in the combined totals. The evidence has
three related but differently sized components:

| Component | Participants | Evidence available |
|---|---:|---|
| Integrated MealMatch usability session | 10 | Task observations, approximate photograph-analysis time, photograph ease rating, comments across receipt, pantry, recipes, cooking, settings and food-waste relevance |
| Text-feature validation | 9 | AI recipe generator, substitution feature and cooking assistant observations; numeric ratings are incomplete for some participants |
| Hands-free cooking validation | 10 | Aggregate result for seven core commands per participant and ten detailed representative interaction records |

The supplied notes are treated as task-based formative sessions using a
convenience/purposive sample. They identify usability problems, repeated
preferences and promising workflows; they do not estimate population-level
performance. No participant demographics, recruitment details, SUS responses,
full task-completion times or complete ground-truth inventories were supplied.
Those measures are therefore not reconstructed.

The cleaned participant-level observation record is retained in
[Anonymised participant evidence](user-testing-participant-evidence.md).

Some questions in the original notes were positively framed, including “Do you
think confirmation is useful?” and “Will this help reduce the friction...?”.
Answers to those questions are treated as qualitative indications rather than
unbiased estimates of benefit. The revised neutral interview guide and its
rationale are documented in `docs/user-testing-round-2-plan.md`.

## 2. Integrated usability results

### 2.1 Onboarding

Seven participants (`P01`, `P02`, `P03`, `P05`, `P06`, `P07`, `P08`) described
the call to action or core purpose as immediately clear. Three identified some
workflow ambiguity: `P04` was initially unsure whether MealMatch was primarily
a pantry or recipe application, `P09` wanted a short first-use sequence, and
`P10` understood the complete workflow only after exploring. `P03` did not
initially notice receipt scanning. These findings support retaining the direct
call to action while adding a short statement or optional sequence such as
“Add pantry → review ingredients → find a recipe → cook.”

### 2.2 Photograph-assisted pantry entry

Reported analysis times were approximate. Where a participant supplied a range,
the midpoint was used only to calculate the descriptive mean and median.

| Participant | Reported time | Midpoint used | Ease /10 | Selected observation |
|---|---:|---:|---:|---|
| P01 | 30 s | 30.0 | 7.0 | Three incorrect suggestions removed, three visible ingredients missed and some quantities incorrect |
| P02 | 15–20 s | 17.5 | 8.0 | Two partly hidden ingredients missed; packaged quantities inaccurate |
| P03 | 25–30 s | 27.5 | 7.0 | Small items such as garlic/chilli missed; spinach quantity incorrect |
| P04 | 10–15 s | 12.5 | 9.0 | Large items recognised; packaged goods sometimes labelled too generally; two manual changes |
| P05 | About 35 s | 35.0 | 6.0 | Four items missed; transparent packaging and quantities performed poorly |
| P06 | About 20 s | 20.0 | 9.0 | One occluded item missed; egg quantity inaccurate |
| P07 | About 25 s | 25.0 | 7.5 | Packaged items difficult; one duplicate and two misses |
| P08 | 12–15 s | 13.5 | 9.0 | One small packet missed; three quantities inaccurate |
| P09 | 30–40 s | 35.0 | 5.0 | Three correct, two incorrect and three missed suggestions |
| P10 | 20–25 s | 22.5 | 8.0 | Similar leafy vegetables confused and quantities inaccurate |

| Derived measure | Result |
|---|---:|
| Participants with a photograph ease rating | 10/10 |
| Mean ease | 7.55/10 |
| Median ease | 7.75/10 |
| Ease range | 5–9/10 |
| Ease ratings at least 7/10 | 8/10 (80%) |
| Approximate midpoint mean analysis time | 23.85 s |
| Approximate midpoint median analysis time | 23.75 s |
| Full reported endpoint range | 10–40 s |
| Explicitly described the wait as slow/slightly too slow | 4/10 |
| Requested progress/status feedback during analysis | 3/10 |
| Explicitly reported inaccurate quantities | 7/10 |
| Raised quantity/unit editing as an issue or requested a control | 10/10 |
| Recognition difficulty linked to small, hidden, packaged or visually similar items | 9/10 |
| Considered human confirmation necessary or valuable, sometimes conditionally | 10/10 |

The time summary is an approximation, not an instrumented latency measure. An
aggregate precision, recall or F1 score cannot be calculated because the notes
do not record the ground-truth item count and full true-positive, false-positive
and false-negative counts for every participant. At least 18 misses were
explicitly enumerated across the eight participants who gave a count or named
two specific missed items, but this is not a common-denominator accuracy metric.
`P09` is the only participant with a complete recognition confusion count:
three true positives, two false positives and three false negatives, giving
precision `0.600`, recall `0.500` and F1 `0.545` for that one photograph.

The common design request was faster correction rather than removal of the
confirmation stage. Participants suggested direct `+`/`−` controls, editable
quantity text, ingredient-specific units, compact or spreadsheet-like editing,
bulk deletion and low-confidence highlighting. Preferences differed: some
wanted steppers and presets while others preferred typing. The interface should
therefore support both direct text entry and quick increment/unit controls.

### 2.3 Receipt entry

Nine of ten participants mentioned difficulty with retailer abbreviations; the
examples included `ARTISAN BGT`, `ART BGT` and `CHKN BRST`. Six explicitly
reported or requested correction of duplicate-line quantities. Seven described
receipt scanning as a preferred or particularly convenient method in at least
one context, usually immediately after shopping. `P04` preferred photographs
because they do not retain receipts, while `P07` was less confident in receipt
interpretation than photograph recognition.

Repeated requests were to show the original receipt line beside its
interpretation, aggregate duplicate quantities, ignore prices, allow multiple
images for long receipts, surface uncertain lines and remember retailer-
specific corrections. The evidence supports retaining confirmation and showing
provenance, for example `ART BGT → artisan baguette`, rather than silently
normalising an uncertain line.

### 2.4 Pantry organisation

Requested improvements included:

- finer categories such as fruit, vegetables, protein, dairy, carbohydrates,
  condiments, frozen food and snacks;
- fridge/freezer/cupboard locations;
- easier expiry editing, stronger expiring-soon styling and reminders;
- search, sorting and bulk editing;
- `used up`, opened/unopened and automatic consumption controls;
- movement of zero-quantity items to a shopping list; and
- optional icons without visual clutter.

These are participant suggestions, not a single agreed specification. Search,
expiry visibility and correction efficiency address repeated problems; the
larger inventory-automation ideas require separate validation.

### 2.5 Recommendations and AI recipe creation

All ten participants described recommendations as useful, relevant or at least
potentially valuable, although `P09` said they did not always reflect personal
taste. Pantry availability mattered to all participants, but the preferred
ranking was not uniform. Some wanted exact matches first; others would accept a
missing ingredient for a more appealing recipe. Repeated requests included
pantry-match explanations, missing-ingredient counts, expiry priority, cuisine,
time, difficulty, cravings, novelty and learning from likes/dislikes.

Seven participants (`P01`, `P02`, `P03`, `P05`, `P07`, `P08`, `P10`) preferred
several AI recipe concepts before full generation. Two (`P04`, `P06`) preferred
one complete recipe to avoid creating another choice problem. `P09` prioritised
trust and labelling of AI recipes rather than clearly choosing either format.
This disagreement supports a small default set with a direct “choose for me” or
“regenerate” path rather than assuming one presentation suits everyone.

### 2.6 Cooking mode, hands-free interaction and assistant integration

All ten participants described hands-free control as useful or potentially
useful, especially when hands were occupied or handling raw ingredients. Five
(`P01`, `P02`, `P05`, `P07`, `P10`) specifically observed that “next” was less
reliable than “next step” and wanted natural command variants. Seven raised the
simultaneous visibility or layout of the current instruction, timer, progress
and voice controls. Preferences again differed: several wanted the voice area
smaller or collapsible, while `P04` wanted a larger recognition indicator.

Eight participants (`P01`, `P02`, `P03`, `P05`, `P06`, `P07`, `P08`, `P10`)
requested stronger assistant context, same-session history or integration with
the current pantry, recipe, step or recipe card. `P04` did not need permanent
history, and `P09` wanted help for short questions but not long-term history.
The common requirement is therefore session-scoped context, not indefinite
conversation retention.

### 2.7 Food-waste and decision-support relevance

Participants described several existing problems: forgotten vegetables,
sauces, herbs, dairy or opened ingredients; duplicate purchasing; unused
remainders from a previous recipe; and difficulty combining unrelated food.
`P04` and `P09` rarely discarded food and expected greater value from meal
discovery than waste reduction. The remaining accounts varied in frequency and
were not collected with a common numeric scale, so no waste-rate percentage is
reported.

The most consistent proposed mechanisms were pantry visibility, expiry-aware
recommendations, follow-up recipes for leftovers and a useful starting point
for meal decisions. These are expectations after a short session, not evidence
that MealMatch has reduced real household waste. Demonstrating that outcome
would require a longitudinal diary or field study.

### 2.8 Additional interface and minority findings

Less frequent comments remain useful design evidence even when they do not form
a majority:

- `P01` and `P05` found the AI recipe input affordance unclear; examples or a
  true placeholder could make the field visibly editable.
- `P01` and `P10` expected the MealMatch mark to navigate Home.
- `P01`, `P06` and `P10` requested an `Other` dietary option; `P08` and `P10`
  also requested disliked-food preferences, and `P10` requested a metric-unit
  preference.
- `P02` and `P05` wanted fridge/freezer/pantry locations. `P07` wanted automatic
  pantry deductions after cooking, and `P10` wanted opened/unopened status.
- `P07` requested expiry notifications and a dedicated leftover workflow;
  `P09` requested barcode and grocery-list integration.
- `P06` wanted the screen to remain awake while cooking. `P09` suggested visual
  demonstrations for difficult techniques.
- `P09` wanted AI-generated recipes labelled and supported by ratings, while
  `P10` wanted generated recipes to be saveable and rateable.

These suggestions should enter a prioritised backlog rather than being treated
as validated requirements. Frequency, severity, implementation cost and fit
with the project's goal should determine which are implemented and re-tested.

## 3. Text-feature participant validation

### 3.1 Data completeness

Nine participants (`P01`–`P09`) were described. The supplied note states that
no corrections were required across these text-feature sessions. Numeric
ratings were incomplete: `P03` supplied no feature ratings, `P02` supplied no
cooking-assistant ratings, and `P01` supplied no substitution-usefulness score.
The phrase “usefulness 3.8 out of five and is five out of five” for `P01`'s AI
recipe task is interpreted as usefulness `3.8/5` and ease `5/5`.

No timed text-model latency observations were supplied, so mean or median text
latency cannot be calculated. Six participants described responses as quick,
immediate or having no noticeable delay; `P01` and `P07` said generating all
three recipe ideas felt slow; `P03` did not provide a latency observation. This
is reported as perceived responsiveness rather than measured inference time.

### 3.2 Ratings

| Feature | Measure | Valid n | Mean /5 | Median /5 | Range |
|---|---|---:|---:|---:|---:|
| AI recipe generator | Usefulness | 8 | 4.35 | 4.25 | 3.5–5.0 |
| AI recipe generator | Ease | 8 | 4.81 | 5.00 | 4.0–5.0 |
| Substitution feature | Usefulness | 7 | 3.86 | 4.00 | 3.0–4.5 |
| Substitution feature | Ease | 8 | 5.00 | 5.00 | 5.0–5.0 |
| Cooking assistant | Usefulness | 7 | 4.71 | 5.00 | 4.0–5.0 |
| Cooking assistant | Ease | 7 | 4.93 | 5.00 | 4.5–5.0 |

No imputation was used for missing ratings. The perfect substitution-ease mean
therefore refers to the eight participants who supplied that rating, not all
nine participants. Six of eight AI-recipe usefulness ratings were at least
`4/5` (75%); five of seven substitution-usefulness ratings were at least `4/5`
(71.4%); and all seven recorded assistant-usefulness ratings were at least
`4/5` (100%). These thresholds are descriptive and were not predeclared pass
criteria.

### 3.3 Qualitative findings

- Seven of nine explicitly valued receiving three recipe choices. Participants
  associated choice with comparison, control and motivation, although the
  integrated study also contains a minority preference for a single result.
- Six of nine raised image-to-recipe mismatch or artificial-looking generated
  food imagery. `P05` said the description mattered more than the image.
- Substitution breadth produced conflicting feedback. `P01` and `P06` wanted
  more obvious or fallback swaps. `P02` and `P08` thought restraint preserved
  flavour and reduced confusion. Others requested common household options,
  flavour/texture impact or focus on non-obvious substitutions.
- All nine described the cooking assistant positively. Its strongest value was
  current-recipe context for cooking time, consistency, substitutions and
  troubleshooting. Voice access and same-session follow-up context were also
  valued.

These sessions assess perceived usefulness and interaction success of the
deployed text workflow. They are not a blinded comparison between Llama, Qwen
and Phi, and should not be presented as an additional model-selection
benchmark.

## 4. Hands-free Whisper and cooking-assistant validation

### 4.1 Aggregate command result

The session notes state that each of ten participants tested seven core routes:
`next_step`, `repeat_step`, `time_remaining`, `previous_step`, `current_step`,
`help` and `stop_listening`. This represents 70 reported core-command attempts.
All were reported as transcribed and executed successfully, none required a
retry, and every response completed within five seconds under a mixture of clean
and noisy conditions.

| Aggregate measure | Result |
|---|---:|
| Participants | 10 |
| Reported core-command attempts | 70 |
| Intent/action successes | 70/70 (100%) |
| Retries | 0/70 (0%) |
| Responses within 5 s | 70/70 (100%) |

Only ten representative interactions were retained at row level. Consequently,
the 70-attempt success result can be reported as a session tally, but WER,
per-intent latency and clean-versus-noisy accuracy cannot be independently
recalculated for all 70 attempts.

### 4.2 Detailed representative interactions

| ID | Intended action | Phrase | Returned transcript | Recorded category | Correct action | Retry | Time | Rating |
|---|---|---|---|---|---|---|---:|---:|
| P01 | Next step | Can we move on to the next step? | can we move on to the next step | `next_step` | Yes | No | 1.4 s | 5/5 |
| P02 | Repeat step | Wait, can you repeat that again? | wait can you repeat that again | `repeat_step` | Yes | No | 1.8 s | 5/5 |
| P03 | Time remaining | How much longer is left on the timer? | how much longer is left on the timer | `time_remaining` | Yes | No | 2.0 s | 5/5 |
| P04 | Previous step | Go back one step, I missed it. | go back one step I missed it | `previous_step` | Yes | No | 1.6 s | 5/5 |
| P05 | Current step | What am I supposed to be doing right now? | what am I supposed to be doing right now | `current_step` | Yes | No | 2.1 s | 4/5 |
| P06 | Help | Help, I'm not sure what I'm meant to do here. | help I'm not sure what I'm meant to do here | `help` | Yes | No | 2.4 s | 5/5 |
| P07 | Stop listening | Okay, stop listening now. | okay stop listening now | `stop_listening` | Yes | No | 1.2 s | 5/5 |
| P08 | Cooking question | What would this dish taste like? | what would this dish taste like | `cooking_query` | Yes | No | 2.8 s | 5/5 |
| P09 | Conversational question | Would you like to try my food after I cook it? | would you like to try my food after I cook it | `conversational_cooking_query` | Yes | No | 3.0 s | 5/5 |
| P10 | Conversational statement | I'm hungry. | I'm hungry | `conversational_cooking_query` | Yes | No | 1.7 s | 5/5 |

| Derived measure from the ten detailed rows | Result |
|---|---:|
| Normalised transcript matches | 10/10 (100%) |
| Word errors in retained transcript/reference pairs | 0 (WER 0.000) |
| Correct interface/assistant outcomes | 10/10 (100%) |
| Retries | 0/10 |
| Mean response time | 2.00 s |
| Median response time | 1.90 s |
| Response-time range | 1.2–3.0 s |
| Mean participant rating | 4.90/5 |
| Median participant rating | 5/5 |
| Rating range | 4–5/5 |
| Explicit clean-condition rows | 3/10 |
| Explicit noisy/background-sound rows | 6/10 |
| Condition not recorded | 1/10 |

The detailed records show successful natural phrasings rather than only exact
command strings. Three retained open-ended examples were also answered without
triggering an incorrect navigation action and remained connected to the active
recipe.

The labels `cooking_query` and `conversational_cooking_query` appear in the
participant notes, while the frozen evaluator and production command router use
the catch-all label `question`. They should therefore be treated as analysis
categories unless raw application logs confirm that those exact labels were
emitted. This does not change the observed successful response, but it prevents
the report from misrepresenting researcher coding as a model output.

### 4.3 Interpretation

The participant result addresses the principal limitation of the synthetic
audio benchmark by exercising real voices, natural phrasing and background
sound in the integrated interface. It supports the usability of the selected
Whisper pipeline for this small sample. It does not establish accent-wide or
population-level robustness because the participant characteristics, audio
files and full per-attempt logs were not retained and the noise level was not
standardised.

“No latency” should not be reported literally: the ten measured responses took
1.2–3.0 seconds. The supported conclusion is that all recorded interactions
completed within five seconds and no participant described that response delay
as unacceptable.

## 5. Post-iteration re-test with the same participant cohort

After the first evaluation, the interface and supporting pipelines were revised
and the same participant cohort tested the affected features again. This was a
formative re-test of the redesigned prototype, not a new independent participant
sample.

| Area | Earlier finding | Post-iteration finding | Strength of evidence |
|---|---|---|---|
| Hands-free next-step control | Five participants in the broader usability sessions observed that some natural phrases containing “next” produced a spoken answer without moving the visible recipe card | Every natural verbal indication of wanting to continue that was attempted in the re-test advanced the visible recipe card to the next step | Direct usability observation, but the number and wording of re-test attempts were not retained; therefore no new percentage is claimed |
| AI recipe generation | Two of nine text-feature participants felt that loading all three ideas took longer than expected | Participants perceived the redesigned generation flow as quicker | Qualitative participant evidence only; no post-iteration timestamps were recorded, so a numerical latency change or median is not claimed |
| Photo analysis | Earlier participant-observed times had an approximate median of 23.75 seconds across ten sessions | Three retained post-iteration runs took 5, 4 and 5 seconds: mean 4.67 seconds, median 5 seconds and range 4–5 seconds | Measured timings, but only three repeated runs of one photograph were retained and the earlier photographs and conditions differed |

A second re-test, after design iteration 3 (see
[Round 2 results](user-testing-round-2-results.md#participant-re-test-of-iteration-3)),
used the same cohort again:

| Area | Earlier finding | Post-iteration-3 finding | Strength of evidence |
|---|---|---|---|
| AI recipe generation time | Generation of three ideas felt slow to two of nine participants | The median generation time was lower than before | Observed timings; the values were not added to the repository, so no size of change is claimed |
| AI recipe relevance | A sweet request produced beef and vegetable dishes | Generated recipes matched the request and used pantry ingredients better | Participant observation |
| Swap feature | Mean usefulness 3.86/5 (`n=7`) | Rated as more useful than before | Participant ratings; post-iteration values not supplied |
| Overall usability | Returning from a recipe lost scroll position and the other AI ideas | Higher reported usability; AI idea cards stayed and the list kept its place | Participant observation; SUS not administered |

For the recorded photo timings, the median decreased by `18.75` seconds, from
`23.75` to `5.00` seconds, equivalent to a `78.9%` reduction. This comparison
shows a substantial improvement in the observed workflow but is not a paired,
same-image experiment across all ten participants. It should therefore be
reported as descriptive iteration evidence rather than a general performance
estimate.

The hands-free finding is important because success was defined as both correct
interpretation and the corresponding visible interface action. The re-test
therefore indicates that the earlier speech/interface state mismatch was
resolved for the natural next-step phrasings that participants actually tried.
It does not prove that every conceivable phrasing will work.

## 6. Cross-cutting design decisions

| Priority | Evidence | Design implication |
|---|---|---|
| High | Quantity/unit editing raised by 10/10 | Provide direct quantity text entry, quick `+`/`−` controls and ingredient-appropriate units |
| High | Receipt abbreviations raised by 9/10; duplicate quantities by 6/10 | Show original line and interpretation, flag uncertainty and aggregate duplicates |
| High | Five participants observed unreliable “next” behaviour initially; the same cohort's post-iteration re-test found that all attempted natural next-step indications moved the visible card | Retain the one-intent/one-action mapping and continue logging transcript, intent and visible state in future tests |
| High | Human confirmation valued by 10/10 but correction burden reduced convenience | Retain confirmation while reducing clicks, supporting bulk changes and highlighting uncertain items |
| Medium | Seven preferred several AI recipe concepts; two preferred one | Offer a small comparison set plus a “choose for me”/regenerate route |
| Medium | Six of nine text participants questioned generated-image fidelity | Improve image grounding or use a clearly labelled illustration/fallback |
| Medium | Eight requested stronger assistant context or persistence | Retain pantry/recipe/step context and history for the active cooking session |
| Medium | Substitution breadth preferences conflicted | Prioritise safe, common substitutes and explain flavour/texture impact; allow an on-demand fallback request |
| Medium | Repeated requests for expiry visibility, missing-item counts and ranking explanations | Explain recommendation rank and expose pantry match, expiring ingredients and missing-item count |

## 7. Limitations and missing metrics

- The recruitment method, participant characteristics and session dates were
  not supplied.
- Ethics-approval and informed-consent records were not included with the
  supplied results. Their status must be verified with the supervisor before
  these observations are used as assessed human-participant research; approval
  or consent must not be claimed retrospectively.
- `P01` originated in the earlier pilot; the combined report counts that person
  once and should not describe all ten as a new independent Round 2 cohort
  unless the study log confirms that.
- Several original interview questions were leading. Revised neutral wording
  should be used in future sessions.
- Photograph time was estimated by participants/observers rather than captured
  automatically, and several values were ranges.
- Complete photograph and receipt ground truth was not recorded for every
  participant, so aggregate precision, recall, F1, quantity accuracy and
  correction rate are unavailable.
- SUS was planned but no item responses or scores were supplied.
- Text ratings contain missing values and no objective latency measurements.
- The first post-iteration AI-generation speed finding is perceived rather than
  instrumented. The second (iteration 3) reports a lower median, but the timings
  behind it and the post-iteration swap ratings are not in the repository. The hands-free re-test attempt count was not retained, and the
  photo speed comparison uses three repeated runs under conditions that differ
  from the initial ten observations.
- The reported 70/70 audio result is supported by an aggregate tally, while
  only ten attempt-level rows were retained. Clean/noisy allocation, WER and
  latency cannot be audited for the remaining attempts.
- Short-session beliefs about future use or food-waste reduction are not
  behavioural outcome evidence.

These limitations should remain in the final report. They do not invalidate the
formative findings, but they define the claims the evidence can support.
