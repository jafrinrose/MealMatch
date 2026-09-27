# Propels integration

Upstream: https://github.com/Propels-AI/Propels
Pinned commit: `241dfb9189e82c2c3f8785bde9ec55fee389af50`.

`HotspotOverlay.tsx` is the upstream component with keyboard access added to
hotspots. Its image sizing, normalized coordinates, animation and tooltip
rendering are used directly by `src/components/ExperienceWalkthrough.tsx`, the
MealMatch product tour. The tour player around it (story-style auto-advance,
camera moves toward each feature, the animated cursor, chapters, keyboard
controls, focus management and the MealMatch frame) is local work.

The full upstream AGPL-3.0 license is retained alongside the source. Preserve
upstream notices and applicable source-availability obligations when distributing
or hosting this derivative. This does not deploy Propels' AWS editor or recorder.

Captures are made from the actual MealMatch UI by `scripts/capture-walkthrough.mjs`
(`npm run capture:tour`). A few endpoints answer with the sample kitchen in
`scripts/walkthrough-fixtures.json` so capturing never writes to the database;
the three AI recipes, their photos and substitutions in it are real MealMatch model
output. They are demonstration assets, not model-evaluation observations.
