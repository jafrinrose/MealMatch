# MealMatch Round 2 Usability Test Protocol

## 1. Aim

Round 2 should validate whether the changes made after Round 1 reduce correction effort, improve trust and preserve state across pantry, recipe, chat and cooking workflows. It should also generate evidence that can be triangulated with the image, text and audio model evaluations.

## 2. Participants

Target 10 completed participants, with 8–12 as the acceptable range for the
next moderated formative round. Include a mixture of:

- people who cook frequently and infrequently;
- people who regularly manage household groceries;
- different levels of technical confidence;
- at least two mobile users and two desktop users.

Use fictional dietary and allergy scenarios rather than asking participants to
disclose actual health, religious or dietary information. Eight to twelve
participants can reveal repeated usability problems and provide useful
descriptive summaries across the integrated workflow while remaining feasible
for a final-year project. Report the sample as purposive, not statistically
representative.

Confirm only that participants are aged 18 or over. Record device, cooking
frequency, household grocery responsibility, technical confidence and prior
use of recipe or pantry applications. Do not collect names in the research
dataset or identifying and special-category data that are unnecessary for the
study.

## 3. Test materials

Prepare:

- two household-food photographs with 8–12 known visible items, including at least one occluded item and one packaged item;
- one receipt containing food, a non-food item, an abbreviation such as `ARTISAN BGT`, and a repeated food line;
- a ground-truth sheet listing visible food names and quantities for each photograph and receipt;
- a pantry state containing at least two soon-to-expire ingredients;
- one recipe with several steps for the voice task;
- a structured observer worksheet completed under an anonymous participant
  code.

Use the same core materials for every participant so results are comparable.
For the approved low-risk study, use researcher-provided photographs and
receipts rather than images from participants' homes. Do not make video, screen
or persistent voice recordings. MealMatch may process microphone audio
temporarily for local transcription, but the uploaded audio is deleted
immediately and only the resulting transcript, intent, timing and interface
outcome are recorded.

## 4. Tasks

Give task goals rather than interface instructions.

1. **First-use comprehension:** Open MealMatch, enter the application and explain what you think it helps you do.
2. **Photograph entry:** Add the food shown in the prepared photograph. Review the suggestions until the pantry matches the photograph.
3. **Quantity correction:** Change one detected item from one piece to three and set its unit to `carton` or `box`.
4. **Missed and incorrect items:** Remove one false detection, add one missed food and correct a category.
5. **Receipt entry:** Upload the prepared receipt and make the saved pantry match it, including the abbreviated and repeated items.
6. **Waste-aware discovery:** Find a recipe that uses an ingredient approaching expiry and explain why it was recommended.
7. **Recipe filtering:** Find a recipe matching a stated cuisine, time limit and pantry-availability requirement.
8. **AI recipe choices:** Request a meal for a stated craving, compare the generated options and choose one to inspect.
9. **Substitution and shopping:** Find an in-pantry substitution for one missing ingredient and add a different missing ingredient to the shopping list.
10. **Hands-free cooking:** Start cooking and, without touching the screen, say “Next”, “Repeat that”, “How much time is left?” and one step-specific clarification. Confirm that the visible step matches the spoken response after every command.
11. **Session recovery:** Leave cooking mode, return to it and confirm that the timer, step and recipe context remain available. Then cancel and verify that pantry quantities are restored.
12. **Assistant-to-recipe flow:** Ask the general assistant for a recipe, convert the request into recipe cards and open one full method.
13. **Conversation persistence:** Navigate away or reload, return to the assistant and find the earlier general conversation; then clear it.
14. **Custom preferences:** Add a custom dietary preference and return Home using the MealMatch brand mark.

## 5. Measures

### Task-level usability

For every task record:

- completion: success, partial success or failure;
- completion time;
- number of errors;
- number and type of facilitator prompts;
- navigation reversals or dead ends;
- Single Ease Question (SEQ), 1 = very difficult and 7 = very easy.

### AI-assisted pantry entry

Compare the initial model output with ground truth and record:

- true positives, false positives and false negatives;
- item-level precision, recall and F1;
- exact quantity accuracy;
- number of renamed, deleted, added, re-categorised and quantity-edited items;
- model inference time and total confirmation time;
- confidence in the final pantry state on a 1–5 scale.

Treat model inference time and human confirmation time as separate measures. A model with better recall may still produce a worse user experience if correction time is excessive.

### Receipt processing

Record food-item precision and recall, non-food exclusion rate, abbreviation-normalisation success and repeated-line quantity accuracy.

### Hands-free cooking

For each scripted command record transcription correctness, intent correctness, visible-state correctness and response time. State synchronisation should be measured separately: a correct spoken answer is not a success if the visible cooking step does not change.

### Overall experience

Administer the 10-item System Usability Scale (SUS) after all tasks. Add one 1–5 trust question for each AI input method and one 1–5 question for perceived usefulness in reducing food waste and meal-decision effort.

## 6. Suggested success criteria

Set criteria before testing and report misses honestly:

| Measure | Proposed target |
|---|---:|
| Unassisted task completion | At least 85% across core tasks |
| Median SEQ | At least 5/7 |
| Photograph food-item precision | At least 0.85 |
| Photograph food-item recall | At least 0.80 |
| Receipt non-food exclusion | At least 0.95 |
| Receipt repeated-item quantity | Correct for every controlled receipt |
| Confirmation corrections | No more than 20% of ground-truth items, median |
| Hands-free intent success | At least 90% of scripted commands |
| Voice/display step synchronisation | 100% after correctly recognised navigation commands |
| SUS | At or above 68, interpreted with sample size stated |

These are project targets, not universal benchmarks. If local inference cannot consistently meet the latency target, report the hardware and focus the design iteration on honest progress feedback and correction efficiency.

## 7. Interview questions

Ask the same core questions in the same order. Begin with open questions, then
administer ratings after the participant has explained the experience in their
own words. Neutral follow-ups include “Can you tell me more about that?” and
“What happened next?”

### Before tasks

1. Before today, how, if at all, did you keep track of food available at home?
2. Tell me about any recent occasion, if any, when food at home was not used
   before it spoiled.
3. How do you usually decide what to cook?
4. What information do you consider when choosing a recipe?

### After photograph entry

1. Please describe what happened after you selected the photograph.
2. How did you approach checking and editing the returned ingredients?
3. Which parts, if any, were easy or difficult?
4. How confident were you that the final list matched the photograph? What
   influenced that confidence?
5. How did the analysis time affect your experience, if at all?
6. What, if anything, would you change about this process?

After the open questions, ask: “On a scale from 1 to 10, where 1 means very
difficult and 10 means very easy, how easy or difficult was it to upload the
photograph and finish checking the ingredients?”

### After receipt entry

1. Please describe your experience of adding items from the receipt.
2. How did the returned items compare with what appeared on the receipt?
3. What did you do when an item was unclear or incorrect?
4. In what circumstances, if any, would you use receipt entry rather than
   another entry method?
5. What, if anything, would you change about this process?

### After recommendations and AI recipe generation

1. How did you decide which recommendation or generated recipe to inspect?
2. How well did the options reflect the pantry and request?
3. What, if anything, did not match what you expected?
4. What information did you need before choosing a recipe?
5. How did the number and variety of options affect your decision?
6. What role, if any, should missing or expiring ingredients have in the order
   of recommendations?

### After substitutions

1. Please describe how you used the substitution feature.
2. Which suggestions, if any, seemed appropriate or inappropriate? Why?
3. Were there ingredients for which you expected a substitution but did not
   receive one, or received one you did not need?
4. What information would help you decide whether to use a substitute?

### After cooking and hands-free tasks

1. Please describe what happened when you used the voice controls.
2. Which phrases felt natural or unnatural to use?
3. How did the spoken response compare with what changed on the screen?
4. In what situations, if any, would you use or avoid hands-free mode?
5. How did the assistant use the current recipe or cooking-step context?
6. What, if anything, would you change about the cooking interface or
   assistant?

### Closing questions

1. Which features, if any, would you be most likely to use? Why?
2. Which features, if any, would you be least likely to use? Why?
3. What is the first change you would make to MealMatch?
4. How, if at all, might MealMatch affect the way you manage food at home?
5. How, if at all, might MealMatch affect the way you decide what to cook?
6. Is there anything important about your experience that the questions did
   not cover?

### Question-design rationale

The earlier pilot included formulations such as “Do you think confirmation is
useful?”, “Will this help you use ingredients before they go bad?” and “Does it
help while cooking?”. These questions imply that the feature is useful or that
the product will have a beneficial effect. They encourage agreement and make a
positive answer easier than a critical one.

The revised guide uses open prompts before numeric ratings, asks participants
to describe behaviour and specific events, and adds “if any” where a problem or
benefit may not exist. It does not name a desired solution such as quantity
buttons, multiple recipe cards or conversation history before the participant
comments. Separate questions address ease, confidence, correctness, usefulness
and preference so that one favourable impression does not automatically answer
every construct. The interviewer should not defend the design, complete a
participant's sentence or reveal problems reported by earlier participants.

Standardised scale anchors are stated in full and used consistently. Questions
about future behaviour are framed as possibilities rather than predictions,
because a short moderated session cannot establish long-term food-waste
reduction. This structure reduces acquiescence, confirmation and social-
desirability bias while still allowing neutral clarification.

## 8. Longer-term field test

As an optional future extension, a 5–7 day diary study with 3–5 participants
could use participants' own pantry photographs and receipts, log what they
cooked, and record any food discarded. This would collect different and more
personal data than the approved low-risk laboratory protocol, so it requires a
separate ethics review or approved amendment, revised consent/privacy materials
and an explicit storage/deletion plan. If approved, capture:

- pantry additions and corrections over time;
- recipes viewed, saved and started;
- expiring ingredients used in completed meals;
- shopping-list use;
- ingredients discarded and stated reason;
- short daily ratings for recommendation relevance and decision effort.

This field study is important because a laboratory session can show usability, but it cannot demonstrate whether MealMatch changes household food-waste behaviour over time.

## 9. Analysis and design iteration

Aggregate task metrics using counts, medians and ranges; do not use inferential statistics for a small formative sample. Code qualitative observations into themes such as trust, correction burden, discoverability, control, recommendation relevance and state consistency. Prioritise a change when it causes task failure, appears across participants, creates safety/allergy risk, or substantially increases time and correction effort.

For the report, maintain a traceability table linking each observation to a design change, the relevant model or software component, and the Round 2 result after the change.
