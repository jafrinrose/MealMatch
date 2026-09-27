# Audio-model identification, operationalisation and evaluation

## Product question

MealMatch needs automatic speech recognition (ASR) after a user starts a
recipe. The model must transcribe short navigation commands such as “next
step”, confirmations, timer questions and open cooking questions while the
user's hands are occupied. This reduces interaction effort and decision fatigue;
the downstream command router, not the ASR model, changes cooking-session state.

The aim was not to claim the three globally “best” speech models. The shortlist
was constrained to public pretrained English checkpoints that another person
can download, run locally on the reference laptop and connect to the existing
Python backend without paid services or model training.

## Literature-led candidate identification

Three established ASR approaches were shortlisted for the final comparison.

| Candidate | Literature basis | Why it is relevant to MealMatch |
|---|---|---|
| Whisper `small.en` | Radford et al. trained Whisper on 680,000 hours of multilingual and multitask weak supervision and reported strong zero-shot transfer and robustness. See [Robust Speech Recognition via Large-Scale Weak Supervision](https://arxiv.org/abs/2212.04356). | A robust encoder-decoder model is plausible for varied spoken commands and background noise. `small.en` was the winner of the preliminary local Whisper-size screen. |
| Distil-Whisper `small.en` | Gandhi, von Platen and Rush report a distilled Whisper family designed for resource-constrained inference, with fewer parameters and faster inference while retaining much of its teacher's out-of-distribution performance. See [Distil-Whisper](https://arxiv.org/abs/2311.00430). | It directly tests whether lower latency can be obtained without losing command-routing accuracy. |
| wav2vec 2.0 Base 960h | Baevski et al. established self-supervised wav2vec 2.0 and strong speech-recognition performance after fine-tuning. See [wav2vec 2.0](https://arxiv.org/abs/2006.11477). | The public English checkpoint provides an architecturally different CTC baseline and tests whether a smaller, much faster recogniser is sufficient. |

Large hosted/proprietary systems were screened out because they would make the
evaluation difficult to reproduce and introduce network, account and cost
confounds. Whisper Large and Distil-Whisper Large were screened out before
testing because the product must remain feasible on a 16 GB local machine. The
within-family stage below identifies an appropriate Whisper capacity before the
cross-family comparison, avoiding an arbitrary checkpoint choice.

## Two-stage experimental design

### Stage A: Whisper capacity screen

Whisper `tiny.en`, `base.en` and `small.en` were compared through the same
`faster-whisper` runtime. Holding architecture, language, decoder and library
constant isolated the accuracy/latency effect of model capacity. This stage
selected `small.en` as Whisper's representative for Stage B; it is retained as
screening evidence rather than presented as the final breadth comparison.

### Stage B: final cross-family comparison

Whisper `small.en`, Distil-Whisper `small.en` and
`facebook/wav2vec2-base-960h` then processed the exact same frozen audio
manifest. This adds architectural breadth without changing the application
task, data, scoring or decision rule after seeing results.

## Operationalisation

The evaluator is
`backend/audio_evaluation/evaluate_asr_models.py`.

- Whisper and Distil-Whisper load through `faster-whisper` on CPU with int8
  compute. Both use English decoding, beam size five and voice-activity
  detection. Weights are cached under `backend/.model_cache/whisper`.
- wav2vec 2.0 loads with Hugging Face `AutoProcessor` and
  `AutoModelForCTC`, pinned to model revision `22aad52`. Mono 16-bit PCM is
  normalised to floating point at 16 kHz, then decoded using greedy CTC.
  Weights are cached under `backend/.model_cache/huggingface`.
- Each model is warmed up once. Warm-up and model-load time are recorded but
  excluded from per-file latency.
- A failed inference is retained as a failure and cannot silently disappear
  from the denominator.
- The three candidates use their normal deployable decoding stacks. Therefore
  Stage B compares complete product pipelines, not isolated encoders under an
  artificial shared decoder.

## Frozen task dataset

The fast benchmark contains 18 phrases covering every deterministic cooking
route—navigation, repetition, timer, help, cancel/finish confirmation and stop
listening—plus an open food-safety question. macOS generated each phrase with
three English voices (US, UK and Indian English). Every recording was tested
clean and with deterministic white noise at 10 dB SNR, producing 108 files per
candidate.

The frozen manifest SHA-256 is
`9cb51aa2b3fd3e6df51e9b1a8eaf5380810c3500cefa2f8e4185d21e07dc6455`.
The exact transcript and expected downstream intent are stored for every file.

This is controlled synthetic speech, not participant data. It provides exact
references, complete command coverage and fast reproducibility, but it does not
represent hesitation, microphone distance, room echo, overlapping appliance
sounds or the diversity of real accents.

### Why a purpose-built synthetic dataset was used

The model-selection benchmark uses controlled synthetic recordings rather than
a public speech dataset. Public ASR corpora are valuable for measuring general
transcription performance, but their utterances are not labelled for
MealMatch's command router and do not guarantee coverage of application actions
such as advancing a recipe step, checking a timer, confirming completion or
stopping hands-free mode. A high score on general speech would therefore not by
itself show that a model can drive the MealMatch cooking workflow correctly.

The 18 phrases were defined from the commands and questions supported by the
application. The evaluation script passes each phrase to the macOS `say`
utility using the Samantha, Daniel and Rishi English voices at a fixed speaking
rate. `ffmpeg` converts the output to mono 16-bit PCM at 16 kHz. The script then
creates a second version of every recording by adding seeded Gaussian white
noise at 10 dB signal-to-noise ratio. It writes a manifest containing the file
path, exact reference transcript, expected application intent, voice,
condition and duration. This produces 18 phrases × three voices × two
conditions = 108 files. The fixed seed and manifest hash make the dataset and
comparison reproducible.

This design has several strengths. Every candidate receives exactly the same
inputs; every supported command route is represented; transcripts and intended
actions are known in advance; clean and noisy performance can be compared under
a controlled condition; and no personal voice data is needed for the initial
technical screen. It directly measures the product outcome that matters:
whether a transcription leads to the correct MealMatch action.

Its weaknesses are equally important. Synthetic voices are more regular than
natural speech and do not reproduce hesitation, false starts, emotion,
microphone variation, room echo, overlapping appliance sounds or the full
range of accents and speaking styles. The fixed phrases may also overestimate
performance when users choose unexpected wording. The results consequently
support selection for this controlled MealMatch benchmark only; they are not
evidence of population-level or universal ASR performance.

The synthetic benchmark will be supplemented by further user testing with
consenting speakers using the integrated hands-free workflow. Participants
will use natural wording at different microphone distances and, where safe and
practical, with realistic kitchen background sounds. The study will measure
end-to-end command success, transcription and intent errors, retries, response
delay, task completion and perceived responsiveness. These observations will
test whether the controlled ranking transfers to real use and will inform any
subsequent change of model, command vocabulary or interface feedback.

## Metrics and frozen decision rule

The evaluation measures:

- micro word error rate (WER);
- end-to-end command-intent accuracy after the same ordered routes used by the
  cooking interface;
- clean and noisy intent accuracy;
- inference failure rate;
- median and p95 transcription latency; and
- real-time factor, inference time divided by recording duration.

Eligibility was fixed at no more than 5% failures, at least 95% clean intent
accuracy and at least 85% noisy intent accuracy. Among eligible candidates, the
ordered criteria are highest noisy intent accuracy, lowest noisy WER, then
lowest median latency. Correct hands-free actions therefore matter more than
punctuation or verbatim transcription.

## Stage A results: Whisper size

All 324 calls completed.

| Model | WER | Overall intent | Clean intent | Noisy intent | Median latency | Median real-time factor |
|---|---:|---:|---:|---:|---:|---:|
| Whisper `tiny.en` | 0.102 | 82.4% | 88.9% | 75.9% | 192 ms | 0.171 |
| Whisper `base.en` | 0.059 | 91.7% | 96.3% | 87.0% | 351 ms | 0.319 |
| Whisper `small.en` | 0.046 | 95.4% | 98.1% | 92.6% | 3,637 ms | 2.881 |

`tiny.en` failed both accuracy gates. `base.en` was eligible, but `small.en`
won the accuracy-first rule and progressed to Stage B. Absolute latency is
machine- and run-state-sensitive, so only latencies collected within the same
stage are used for candidate comparisons.

## Stage B results: cross-family pipelines

All 324 calls again completed without an inference failure.

| Candidate | WER | Overall intent | Clean intent | Noisy intent | Median latency | Median real-time factor | Eligible? |
|---|---:|---:|---:|---:|---:|---:|---|
| Whisper `small.en` | 0.046 | 95.4% | 98.1% | 92.6% | 1,045 ms | 0.943 | Yes |
| Distil-Whisper `small.en` | 0.062 | 87.0% | 92.6% | 81.5% | 922 ms | 0.831 | No |
| wav2vec 2.0 Base 960h | 0.358 | 48.1% | 64.8% | 31.5% | 59 ms | 0.052 | No |

Distil-Whisper was 12% faster than Whisper in the matched run, but failed both
intent gates, particularly under noise. wav2vec 2.0 was much faster but its
greedy CTC transcripts were not reliable enough for MealMatch commands. Only
Whisper `small.en` met every gate, so the final cross-family evidence confirms
the existing runtime selection.

## Participant validation of the integrated hands-free flow

The controlled synthetic benchmark was subsequently supplemented by a small
formative study with ten participants using the selected Whisper pipeline in
the MealMatch cooking interface. Each participant tested seven core routes:
next step, repeat step, time remaining, previous step, current step, help and
stop listening. The session tally records 70/70 correct intent/action outcomes,
no retries and every response within five seconds across a mixture of clean and
background-noise conditions.

Ten representative attempt-level records were retained. All ten normalised
transcripts matched the spoken reference, all produced the intended interface
or assistant outcome and none required a retry. Mean response time was `2.00`
seconds, median was `1.90` seconds and the range was `1.2–3.0` seconds. The mean
participant rating was `4.90/5`. The retained examples included natural
phrasings such as “What am I supposed to be doing right now?” as well as open
cooking/conversational input without an incorrect navigation action.

This participant evidence improves ecological validity because it involves real
voices, natural wording and some everyday background sound. It remains
formative: participant characteristics and raw audio were not retained, noise
was not standardised, and only ten of the 70 core attempts have row-level
transcripts and timings. The aggregate 70/70 result can therefore be reported as
the recorded session tally, but clean/noisy accuracy, WER and latency cannot be
independently recomputed for all 70 trials. Full calculations and the retained
rows are in [Combined formative user-testing results](user-testing-combined-results.md#4-hands-free-whisper-and-cooking-assistant-validation).

### Post-iteration re-test

After the voice-command redesign, the same participant cohort tested the
hands-free flow again. Every natural verbal indication of wanting to move to the
next step that was attempted in the re-test caused the visible recipe card to
advance. This is stronger than checking transcription alone because the expected
interface state change was also observed. It indicates that the earlier mismatch
between Mimi's spoken response and the recipe card was resolved for the tested
phrasings.

The number and exact wording of these re-test attempts were not retained, so no
new percentage or confidence interval is calculated. The finding must not be
generalised to every possible phrase or accent. Future sessions should log the
audio/transcript, predicted intent, card state before and after, retry status and
response time for every attempt.

## Reproduction

Generate the frozen macOS fixtures and repeat Stage A:

```bash
source backend/venv/bin/activate
python backend/audio_evaluation/evaluate_whisper.py \
  --output artifacts/whisper_evaluation \
  --generate-macos
```

Run Stage B using that unchanged manifest:

```bash
python backend/audio_evaluation/evaluate_asr_models.py \
  --manifest artifacts/whisper_evaluation/audio-manifest.json \
  --output artifacts/asr_family_evaluation
```

Raw transcripts, expected and predicted intents, errors, model-load times and
latencies are retained in the adjacent JSON files under `artifacts/`.

## Decision and interpretation boundary

**Selected runtime:** Whisper `small.en` via `faster-whisper`.

The experiment supports this selection for the controlled local command task;
it does not prove universal ASR superiority. The completed formative study
supports the integrated flow for ten participants, but a larger or more diverse
study with fully retained per-attempt logs would still be needed for population-
level claims. If later users find delay unacceptable, `base.en` remains the
evidence-supported low-latency fallback from Stage A rather than an untested
guess.
