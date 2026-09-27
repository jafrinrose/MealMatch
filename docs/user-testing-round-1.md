# MealMatch Round 1 Formative Usability Study

## 1. Study purpose

The first usability study examined whether a new user could understand MealMatch, add pantry items through photographs and receipts, evaluate recipe recommendations, use hands-free cooking, and manage personal preferences. It also explored whether the product appeared capable of reducing household food waste and decision fatigue.

## 2. Method

This was a moderated, task-based formative usability session with one participant (`n = 1`). The participant interacted with the working application and answered short retrospective questions after each workflow. Observations, completion time, correction behaviour, perceived ease and verbatim comments were recorded.

Because only one participant was involved, the results identify usability problems and design opportunities; they do not establish population-level usability or statistical significance.

## 3. Tasks covered

The participant was asked to:

1. Enter the application and explain its purpose.
2. Upload a household food photograph, review the model output and correct it before saving.
3. Upload a grocery receipt and review the extracted food items and quantities.
4. Review pantry-based recipe recommendations and filters.
5. Generate a recipe with AI.
6. Start cooking and use voice commands in hands-free mode.
7. Ask the cooking assistant for help.
8. Review and edit preference settings.
9. Reflect on existing food-waste and meal-decision behaviours.

## 4. Quantitative observations

| Measure | Round 1 result | Interpretation |
|---|---:|---|
| Photograph analysis time | Approximately 30 seconds | The participant perceived the wait as too long. |
| Ease of uploading and confirming a photograph | 7/10 | The overall flow was usable, but correction effort reduced satisfaction. |
| Incorrect detections removed | 3 | These are user-observed false positives. |
| Visible ingredients missed | 3 | These are user-observed false negatives. |
| Quantity corrections | Present; exact count not recorded | Quantity estimation requires a clearer and faster correction control. |

The number of food objects in the photograph was not recorded, so precision and recall cannot be calculated retrospectively from this session. Future sessions will use a known ground-truth inventory.

## 5. Findings

### 5.1 Onboarding and product comprehension

The entry screen's primary call-to-action was easy to identify. The participant could also explain that MealMatch tracks pantry food and recommends ways to use it. No onboarding barrier was observed.

### 5.2 Photograph-assisted pantry entry

The photograph was successfully uploaded, but the approximately 30-second inference time produced high perceived latency. Human verification was considered necessary and valuable, particularly because the model produced quantity errors, three false-positive items and three false-negative items.

The participant rated the upload-and-confirm workflow 7/10, but described checking for omissions as annoying. They requested direct increment/decrement controls and a unit selector containing household units such as jar, box, piece and carton. This indicates that correction efficiency—not the presence of a confirmation stage—is the main interaction problem.

### 5.3 Receipt-assisted pantry entry

Receipt extraction did not reliably normalise retailer abbreviations such as `artisan BGT` to `artisan baguette`. Repeated lines were also collapsed: two shrimp entries were represented as one item. The participant therefore did not trust receipt or photograph output without human review.

The category taxonomy was considered too broad and sometimes incorrect. The participant requested recognisable groups such as fruit, vegetables and meat, with more representative ingredient icons.

### 5.4 Recipe discovery and generation

Pantry-based recommendations were judged positively. The participant expected recipes using all available ingredients to appear first and valued cuisine/craving filters and ingredient substitutions. They also endorsed prioritising recipes that use food approaching expiry.

The AI recipe request field had weak affordance because pre-filled text looked like content rather than an editable prompt. After generation, the participant wanted multiple recipe concepts to compare before opening a full method, rather than being sent immediately to one generated recipe.

### 5.5 Cooking mode and hands-free interaction

Hands-free assistance was considered helpful when the user's hands were occupied. However, the hands-free panel competed visually with the progress indicator and remaining time. The participant wanted these elements visible together.

There was also an intent/state synchronisation defect. Saying “Next” did not advance the visible step; only the more specific phrase “Next step” did. A successful spoken navigation command must update both the spoken response and the on-screen current-step state.

### 5.6 Cooking assistant

The participant wanted a recipe suggested in chat to become the same actionable recipe card used elsewhere in the product. They also wanted general assistant history to persist long enough to revisit previous advice.

### 5.7 Settings and navigation

The participant requested an `Other` input for dietary preferences, matching the existing custom allergy and cuisine controls. They also expected the MealMatch brand mark to navigate to Home.

### 5.8 Perceived value

The participant reported frequently forgetting ingredients and discarding them after expiry. They believed MealMatch could help by making inventory visible and recommending unfamiliar ways to combine ingredients, especially when expiring food is prioritised. They also believed multiple relevant suggestions could reduce the friction of deciding how to use a set of ingredients.

## 6. Prioritised usability issues and design response

| Priority | Finding | Usability terminology | Design response | Status |
|---|---|---|---|---|
| Critical | “Next” did not advance the visible cooking step | Voice intent recognition and state synchronisation failure | Accept concise navigation utterances and update the persisted cooking step before speaking the result. | Implemented |
| High | Photograph review required several additions, deletions and quantity edits | High correction burden caused by false positives, false negatives and quantity error | Retain human-in-the-loop confirmation; add quantity steppers, unit selectors, category editing and a prominent “add missed ingredient” action. | Implemented |
| High | Receipt duplicates became one item | Quantity aggregation/data-loss defect | Preserve repeated model outputs and aggregate them into an editable quantity in the confirmation interface. | Implemented |
| High | Receipt abbreviations were not expanded reliably | OCR post-processing and semantic normalisation limitation | Add explicit abbreviation and repeated-line requirements to the text-model prompt; retain human confirmation. | Implemented; requires Round 2 validation |
| High | AI generation returned one recipe immediately | Insufficient choice and premature navigation | Generate three differentiated recipe cards and let the user select one before viewing the method. | Implemented |
| Medium | AI prompt looked pre-filled | Poor input affordance | Use an empty field with example placeholder text and a descriptive accessible label. | Implemented |
| Medium | Voice controls obscured cooking status | Weak information hierarchy | Condense the voice control, collapse optional settings, and display it beside step progress. | Implemented |
| Medium | Assistant advice could not become an actionable recipe | Cross-flow discontinuity | Add an action that converts the latest request into standard recipe choices saved to Recipes. | Implemented |
| Medium | General assistant context was too short | Lack of conversational persistence | Persist the most recent 30 general-chat messages locally and provide an explicit clear-history control. | Implemented |
| Medium | Pantry categories were broad or incorrect | Information-architecture/taxonomy mismatch | Expand the taxonomy and allow category correction before saving. | Implemented |
| Low | No custom dietary input | Incomplete preference flexibility | Add an `Other` dietary preference control. | Implemented |
| Low | Brand mark did not return Home | Conventional navigation expectation not met | Make the desktop MealMatch brand mark a Home control. | Implemented |

## 7. Limitations

- The sample contained one participant and cannot represent the broader target population.
- Participant demographics, device, viewport, prior cooking experience and technical confidence were not recorded.
- Only photograph analysis time was measured; other task times were not captured.
- Photograph and receipt ground truth were not documented before the session, so model precision, recall and quantity accuracy cannot be computed.
- Facilitator intervention and think-aloud effects were not recorded.
- The session assessed initial use rather than repeated, real-world household use over several days.

## 8. Conclusion

Round 1 supports the core interaction concept: onboarding was understandable, recommendations were useful, human verification increased trust, and hands-free assistance had clear value. The main weaknesses were not conceptual; they were correction efficiency, receipt quantity handling, voice-to-interface synchronisation, and continuity between AI suggestions and actionable recipe views. These findings informed the first design iteration and define the hypotheses for Round 2.
