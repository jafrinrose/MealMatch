# Text-model identification, operationalisation and evaluation

## Product question

MealMatch's text model turns pantry and preference context into structured
recipes, food-only receipt suggestions, substitutions and step-aware cooking
answers. It reduces meal-decision fatigue and helps use available or expiring
food. Deterministic code remains responsible for recipe ranking, allergy and
diet validation, persistence and critical poultry-safety rules.

The evaluation seeks the best **viable local candidate for MealMatch**, not the
largest or globally highest-scoring language model. Candidates had to be public
pretrained instruction models near 3–4 billion parameters, runnable through the
same Ollama interface on the reference 16 GB laptop, and installable by another
repository user without a paid API.

## Literature-led candidate identification

| Final candidate | Literature basis | Why it was shortlisted |
|---|---|---|
| Llama 3.2 3B Instruct | The broader Llama 3 family is documented in [The Llama 3 Herd of Models](https://arxiv.org/abs/2407.21783); Meta's [Llama 3.2 release](https://ai.meta.com/blog/llama-3-2-connect-2024-vision-edge-mobile-devices/) specifically positions the 1B and 3B text models for local and edge use. | It was the existing application baseline, fits local memory, supports instruction following and establishes whether replacement is justified. |
| Qwen2.5 3B Instruct | The [Qwen2.5 Technical Report](https://arxiv.org/abs/2412.15115) reports improvements in instruction following, structured data and JSON output across a range of model sizes. | MealMatch relies heavily on valid recipe and substitution JSON, making structured-output behaviour directly relevant. |
| Phi-3.5 Mini 3.8B Instruct | The [Phi-3 Technical Report](https://arxiv.org/abs/2404.14219) introduces a capable 3.8B model designed for local deployment and extends the family with Phi-3.5 Mini. | It supplies a third distinct local model family at a comparable resource level rather than another capacity point from Llama or Qwen. |

This is a constrained, literature-backed shortlist rather than a claim that
these are the three best language models for every task. Larger Mistral, Llama,
Qwen and Phi variants were screened out because they would change the memory
and latency envelope. Hosted proprietary models were excluded because network,
pricing and provider changes would weaken reproducibility.

Before the final breadth comparison, Llama 3.2 1B was tested as a resource
screening baseline. It scored `0.580`, achieved only `42.9%` structured validity
and `80.0%` constraint safety, and was rejected. That result is retained as
evidence that simply choosing the smallest runnable model was inadequate; it
does not occupy one of the three final cross-family positions.

## Operationalisation

The evaluator is `backend/text_evaluation/evaluate_text_models.py`. All three
candidates use the same local Ollama `/api/generate` endpoint, prompt text,
temperature zero, seed `20260924`, 8,192-token context request, 900-token output
limit and 120-second timeout.

The evaluated Ollama artifacts were:

| Candidate | Local ID | Parameters | Quantisation |
|---|---|---:|---|
| `llama3.2:3b` | `a80c4f17acd5` | 3.2B | Q4_K_M |
| `qwen2.5:3b` | `357c53fb659c` | 3.1B | Q4_K_M |
| `phi3.5:3.8b` | `61819fb370a3` | 3.8B | Q4_0 |

The test compares deployable tagged artifacts rather than theoretical
full-precision architectures. Quantisation differs because these are the
official/default Ollama packages a fresh project user receives; that limitation
is recorded instead of implying an isolated architecture experiment.

Recipe and substitution requests use Ollama JSON-object mode. Receipt
extraction intentionally requests a top-level array without object-only JSON
mode because that matches production. Every prompt, raw response, parse result,
violation and latency is retained. A failed or invalid response receives no
credit and stays in the denominator.

## Frozen MealMatch task dataset

Each candidate receives 18 deterministic cases:

- six recipe-generation cases covering vegetarian, vegan, gluten-free,
  dairy-allergy, peanut-allergy and pantry-first constraints;
- four mixed food/non-food receipt OCR cases;
- four diet/allergy-aware substitution cases that test pantry-first ordering;
  and
- four step-aware cooking questions.

Automated scoring records JSON/schema validity, forbidden-ingredient conflicts,
pantry grounding, varied step timing, receipt precision/recall/F1, pantry-first
substitutions, required cooking facts, failures and latency. The macro score
weights recipe, receipt, substitution and cooking equally so the six recipe
cases do not dominate.

This is a compact application benchmark, not a general language-model
leaderboard. It is intentionally aligned to the exact output structures and
failure costs used by MealMatch.

### Why a purpose-built dataset was used

The model-selection experiment uses a constructed MealMatch benchmark rather
than a public general-purpose language-model dataset. Public benchmarks can
measure broad knowledge or reasoning, but they do not test MealMatch's exact
JSON schemas, pantry-grounded recipe generation, food-only receipt filtering,
dietary and allergy constraints, pantry-first substitutions, step-aware cooking
answers or latency through the local Ollama deployment. General benchmark
scores would therefore be weak evidence that a model is safe and usable in the
implemented application workflow.

The cases are statically defined in
`backend/text_evaluation/evaluate_text_models.py`. They were constructed from
the four text tasks exposed by the product: six pantry and preference recipe
requests, four mixed food/non-food receipt transcripts, four constrained
substitution requests and four questions grounded in a current cooking step.
Each case contains explicit expected concepts, prohibited ingredients or
required facts as appropriate. The poultry cases use published food-safety
guidance for their expected behaviour. Cases, prompts, model settings and
scoring rules are frozen before the final candidate comparison, and every
candidate receives the same inputs. Raw prompts, responses, parsing outcomes,
violations and latencies are retained in the result JSON.

This approach provides direct application relevance, known test expectations,
repeatable comparisons and coverage of high-cost failures that a generic
benchmark may omit. It also allows output structure, pantry grounding,
constraint compliance, receipt precision and recall, failures and local
latency to be measured consistently across deployable model pipelines.

The benchmark is nevertheless small and project-defined. Its cases may reflect
the assumptions of their authors, cannot cover the variety of real pantries,
receipts, diets and conversational wording, and may reward behaviour that is
easy to express in deterministic checks. Automated scoring also cannot
establish whether a recipe is appealing, whether a substitution tastes good or
whether an answer feels clear and supportive. The results therefore justify a
model choice for the specified MealMatch tasks; they do not establish general
language-model superiority or user preference.

Participant testing subsequently supplemented the automated comparison by
exercising the integrated recipe, substitution and cooking-assistant workflows
and the combined text-and-audio cooking flow. It is reported separately below
because it evaluates the selected product workflow rather than comparing model
candidates. A future study could strengthen this evidence through blinded
ratings of matched outputs and instrumented text-response latency.

## Protocol audit and safety iteration

The first pilot was rejected before selection because it incorrectly forced
receipt arrays through Ollama's object-oriented JSON mode and treated coconut
milk as a vegan violation. Both were evaluator errors, not model failures. The
pilot remains under `artifacts/text_model_evaluation/` as an auditable protocol
iteration.

A corrected raw run then exposed a more serious scoring weakness: aggregate
keyword scoring could credit a response for mentioning 74°C even if it also
said chicken at 60°C was safe. Sentence-level checks were added. The raw guarded
audit found that Llama 3.2 3B advised rinsing raw chicken and Qwen2.5 3B
described chicken at 60°C as safe despite explicit prompting. No raw model was
therefore trusted with those two questions.

The deployed application now intercepts explicitly labelled poultry-temperature
and raw-poultry-washing questions with deterministic, unit-tested answers before
an LLM call. Final records mark these as `model_invoked: false`. The guard
follows the [FoodSafety.gov 165°F/74°C poultry minimum](https://www.foodsafety.gov/food-safety-charts/safe-minimum-internal-temperatures)
and [CDC guidance that raw chicken does not need washing](https://www.cdc.gov/food-safety/foods/chicken.html).
This is model orchestration: generative flexibility is used where beneficial,
while a narrow high-risk rule remains testable software.

## Metrics and frozen decision rule

Eligibility requires:

- failure rate no greater than 5%;
- structured validity of at least 90%;
- dietary/allergy constraint safety of at least 90%;
- every guarded critical-safety case to pass; and
- median inference latency no greater than 30 seconds.

Among eligible models, select the highest macro task score. When the top two
are within `0.03`, treat the difference as practically tied and select the
lower-latency candidate.

## Final cross-family results

The final run completed 16 model calls plus two deterministic safety cases per
candidate. No model inference failed.

| Model | Macro score | Recipe | Receipt | Substitution | Cooking | Structured valid | Constraint safety | Critical system safety | Median latency | Eligible? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Llama 3.2 3B | 0.944 | 1.000 | 1.000 | 0.938 | 0.838 | 100.0% | 100.0% | 100.0% | 1.11 s | Yes |
| Qwen2.5 3B | 0.960 | 1.000 | 0.964 | 0.875 | 1.000 | 100.0% | 100.0% | 100.0% | 1.53 s | Yes |
| Phi-3.5 Mini 3.8B | 0.704 | 0.642 | 0.700 | 0.475 | 1.000 | 35.7% | 80.0% | 100.0% | 1.53 s | No |

Phi-3.5 was rejected because it failed the structured-validity and constraint
safety gates. Qwen achieved the highest macro score, but its `0.016` advantage
over Llama is smaller than the frozen `0.03` practical-tie boundary. Llama's
lower matched-run median latency therefore selects **Llama 3.2 3B**. The result
confirms, rather than assumes, the existing application model.

The critical-safety column belongs to the orchestrated system, not the raw
models. The deterministic cases do not invoke a candidate. Raw unsafe outputs
remain preserved in `artifacts/text_model_evaluation_guarded_final/` and are not
rewritten as model successes.

## Participant validation of the deployed text features

Nine participants subsequently used the selected deployed workflow through the
AI recipe generator, substitution feature and step-aware cooking assistant. No
participant correction to a text response was recorded. Numeric ratings were
incomplete, so each result retains its actual denominator rather than filling
missing values:

| Feature | Measure | Valid n | Mean /5 | Median /5 |
|---|---|---:|---:|---:|
| AI recipe generator | Usefulness | 8 | 4.35 | 4.25 |
| AI recipe generator | Ease | 8 | 4.81 | 5.00 |
| Substitution feature | Usefulness | 7 | 3.86 | 4.00 |
| Substitution feature | Ease | 8 | 5.00 | 5.00 |
| Cooking assistant | Usefulness | 7 | 4.71 | 5.00 |
| Cooking assistant | Ease | 7 | 4.93 | 5.00 |

Seven participants explicitly valued receiving three recipe choices. Six raised
generated-image fidelity or artificial appearance, demonstrating that recipe-
text quality and image quality should be evaluated separately. Substitution
feedback was mixed: some wanted more common or fallback swaps, while others
preferred restraint to preserve a recipe's flavour and reduce clutter. All nine
described the cooking assistant positively, particularly when it retained the
active recipe and step context.

No instrumented latency values were captured. Six participants described text
responses as quick or immediate, two felt that loading all three recipe ideas
took longer than expected, and one supplied no latency observation. A numeric
user-test latency result is therefore not claimed. These sessions evaluate the
usability of the selected deployed workflow; they were not blinded output
comparisons between model candidates and do not alter the frozen Llama/Qwen/Phi
selection. Full denominators, qualitative findings and limitations are in
[Combined formative user-testing results](user-testing-combined-results.md#3-text-feature-participant-validation).

After redesign, the same participant cohort tested the AI recipe generator
again and described generation as quicker. Because post-iteration timestamps
were not recorded, this is reported as a qualitative usability finding rather
than a measured latency improvement. It does not replace the instrumented model
selection benchmark or support a new numerical median.

A second redesign (design iteration 3) changed how requests are interpreted,
which pantry foods the model is offered, the checks a generated recipe must pass
and how swaps are found. In the cohort's re-test the median generation time was
lower, the recipes matched what was asked and used pantry ingredients better,
and the swap feature was rated as more useful. The timings and ratings behind
these findings were not added to the repository. The model itself did not
change, so the frozen selection above stands.

## Reproduction

```bash
ollama pull llama3.2:3b
ollama pull qwen2.5:3b
ollama pull phi3.5:3.8b

source backend/venv/bin/activate
python backend/text_evaluation/evaluate_text_models.py \
  --output artifacts/text_model_evaluation_cross_family
```

The final JSON stores all prompts, responses, case scores, eligibility metrics,
latency and bootstrap intervals. Generated results remain under the Git-ignored
`artifacts/` directory and can be regenerated with the command above.

## Decision and interpretation boundary

**Selected runtime:** `llama3.2:3b`, protected by deterministic preference,
schema and poultry-safety validation.

The automated benchmark can assess known constraints and output structure, but
cannot establish taste, creativity, conversational warmth or whether a recipe
is enjoyable. The participant study adds formative ratings of the deployed
features and tests text plus audio together during cooking, but it was not a
blinded candidate comparison. Any later interface or prompt change should be
recorded as a design iteration rather than silently altering this frozen
result.
