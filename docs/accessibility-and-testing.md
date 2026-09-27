# Accessibility, inclusion and software-testing evidence

**Audit date:** 28 September 2026  
**Scope:** MealMatch web prototype, model pipelines and formative user study

## 1. Accessibility and inclusion position

MealMatch treats accessibility as both a technical quality requirement and a
question of who has power, who is represented and who may be excluded. The
three concepts below are complementary rather than interchangeable.

### 1.1 Inclusive Design: broad, empathetic perspective

Inclusive Design asks the project to understand different contexts, abilities,
preferences and temporary constraints. MealMatch demonstrates this through:

- manual ingredient entry, receipt upload and photograph upload, so no single
  AI input method is compulsory;
- visible buttons for every hands-free cooking action, so speech is an optional
  convenience rather than the only route;
- editable AI detections and mandatory confirmation before pantry data changes;
- responsive desktop/mobile layouts, light/dark themes, persistent recipe-step
  context and reduced-motion behaviour;
- dietary, allergy, disliked-food, cuisine and custom `Other` preferences;
- iterative participant testing in which correction burden, trust, natural
  speech, decision fatigue and differing preferences changed the design.

This is meaningful inclusive practice, but the evidence has limits. Participant
demographics and disability/access-needs data were not collected, and the study
does not demonstrate inclusion across disability, age, literacy, language,
culture or socioeconomic groups. The current interface and speech benchmark are
English-language. Future recruitment should include participants who use
assistive technology and people with varied accents, cooking experience,
devices and access needs, without collecting unnecessary sensitive data.

### 1.2 Born-Accessible Design: concrete technical standards

The implementation was audited against a WCAG 2.2 AA-oriented checklist. It
currently provides:

- an English document language and semantic `main`, navigation, section,
  heading, form, fieldset and dialog structures;
- a keyboard-visible skip link to `#main-content`;
- labelled primary navigation and `aria-current="page"` on the active route;
- native buttons, inputs and selects for primary actions, with visible keyboard
  focus indicators;
- accessible names for icon-only controls and non-text charts;
- `role="status"`, `role="alert"`, `aria-live`, `aria-busy`, `aria-expanded`
  and `aria-pressed` where state changes need to be conveyed;
- text equivalents for freshness, progress, pantry categories and cooking
  status instead of relying only on colour or animation;
- a `prefers-reduced-motion` mode and a non-speech alternative for voice tasks;
- user confirmation, correction and cancellation around fallible AI output.

Changes made during this audit added the skip link, main-content focus target,
navigation labels/current-page state and an announced toast status. A later fix
(design iteration 4) removed a low-contrast case: in the dark theme, in-pantry
swap suggestions sat on a light card with light text. All swaps now share the
theme's card colour, and "In pantry" and "Alternative" are told apart by tag
text and colour, not by the card alone. The
production build and automated tests pass after these changes.

This is not a claim of WCAG conformance. No complete screen-reader audit,
keyboard-only audit, 200%/400% zoom audit or automated/manual contrast report
has been retained. Dialog focus trapping and focus restoration also need a
dedicated audit. Those checks are required before describing the product as
WCAG 2.2 AA conformant.

### 1.3 Radical Inclusion: social-justice accountability

Radical Inclusion asks not only whether a control can be operated, but whose
food, language, body, home and resources the system assumes. MealMatch applies
this lens by:

- keeping human authority over AI-detected pantry data and displaying
  uncertainty rather than silently treating the model as correct;
- processing the core models locally, reducing the need to send household food
  photographs, receipts or speech to a commercial cloud service;
- retaining manual and touch controls where vision, receipt or speech models
  fail;
- treating allergy conflicts as exclusions and making dietary conflicts
  explicit rather than optimising only for model relevance;
- supporting custom preferences instead of limiting every person to a fixed
  taxonomy;
- documenting model failures, synthetic-data limits, missing demographic data
  and contradictory participant preferences instead of presenting AI as
  universally reliable.

The project must also acknowledge unresolved structural exclusions. Local AI
requires relatively capable hardware; food labels, cuisines and household units
reflect the available datasets and developer taxonomy; speech performance has
not been analysed by accent or speech difference; and pantry ownership itself
must not be treated as a measure of personal responsibility or moral worth.
Food-waste messaging should avoid blaming people experiencing poverty, limited
storage, disability, care responsibilities or unstable access to food. Future
co-design should compensate participants and involve relevant communities in
setting priorities, not only in validating a nearly finished interface.

## 2. Testing levels

| Level | What MealMatch tests | Evidence and current status |
|---|---|---|
| Unit testing | Ingredient identity, receipt parsing, recommendation scoring, dietary/allergy rules, substitutions, quantity conversion, command routing, model-evaluation metrics and frontend recipe/voice rules | Implemented. `backend/tests/` and `frontend/tests/`; current run: 100 backend tests and 8 frontend tests passed |
| Integration testing | API routes integrated with temporary SQLite data, photo-scan streaming and confirmation, cooking-session/pantry updates, AI-recipe safety/retry logic, substitutions and CORS | Implemented. Twelve API/database boundary tests in `test_photo_workflow.py` and the `ApiTests` class in `test_recipes_and_cooking.py` pass with model calls mocked where appropriate |
| System testing | Browser, React application, Vite proxy, live FastAPI service and temporary database exercised as one system | Implemented as `frontend/scripts/system-smoke.mjs`. It verifies API availability, accessible shell, manual ingredient entry, database persistence, navigation/current-page state, recipe search and cleanup |
| Acceptance testing | Whether intended users can complete and understand realistic pantry, recipe, cooking-assistant and hands-free tasks | Completed as formative acceptance/usability testing with ten participants overall, a nine-participant text-feature subset and a ten-participant hands-free study. Findings and re-testing are in the combined report; this is formative acceptance evidence, not formal client sign-off or population-level proof |

### 2.1 Reproduction commands

From the repository root:

```bash
backend/venv/bin/python -m unittest discover -s backend/tests -t . -v
cd frontend
npm test
npm run lint
npm run build
```

For the full-stack system smoke test, use a disposable database, seed it, then
start the two services in separate terminals:

```bash
MEALMATCH_DATABASE_URL=sqlite:////private/tmp/mealmatch-system-test.db \
  backend/venv/bin/python backend/seed_data.py

MEALMATCH_DATABASE_URL=sqlite:////private/tmp/mealmatch-system-test.db \
  backend/venv/bin/python -m uvicorn main:app --app-dir backend \
  --host 127.0.0.1 --port 8000

cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
npm run test:system
```

The system test adds a uniquely named ingredient and deletes it before exit. A
disposable database is still required so an interrupted run cannot affect real
prototype data.

## 3. Acceptance evidence and limits

The participant study functions as formative user acceptance testing because
participants attempted core workflows and judged ease, usefulness, trust and
task outcomes. The evidence includes interface problems, model corrections,
natural-language hands-free tasks and post-iteration re-testing. See
[Combined formative user-testing results](user-testing-combined-results.md).

It should not be called summative accessibility acceptance testing. No retained
results identify assistive technologies or access needs, SUS responses were not
supplied, and some post-iteration attempt counts were not preserved. A future
accessibility acceptance round should define pass criteria for keyboard-only and
screen-reader completion, 200% zoom/reflow, reduced motion, error recovery and
speech alternatives before recruitment.

## 4. Current conclusion

All four software-testing levels now have identifiable evidence. Inclusive
Design and Radical Inclusion are visible in the multimodal, user-correctable,
privacy-conscious workflow and in honest limitations. Born-accessible practices
are present in the implementation and were strengthened by this audit. The
project should claim an **accessibility-informed prototype**, not a universally
inclusive or WCAG-conformant product, until the outstanding audits and more
diverse co-design work are completed.
