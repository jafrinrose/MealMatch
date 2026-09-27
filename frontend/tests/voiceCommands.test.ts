import test from "node:test";
import assert from "node:assert/strict";
import { confirms, cookingIntent, declines, isWakePhrase } from "../src/voiceCommands.ts";

const kind = (text: string, onFinalStep = false) => cookingIntent(text, onFinalStep).kind;

test("any phrase with 'next' moves the step card (round 2 finding)", () => {
  for (const phrase of ["Next.", "next step", "Okay, next", "next please", "What's next?", "what is the next step", "Alright, next one", "go to the next step", "read the next step"]) {
    assert.equal(kind(phrase), "next", phrase);
  }
  assert.equal(kind("I'm done with this step"), "next");
  assert.equal(kind("continue"), "next");
  assert.equal(kind("wait, not next yet"), "hold");
});

test("on the last step, finishing words match the Meal is ready button", () => {
  for (const phrase of ["done", "I'm done", "finished", "next", "all done", "It's ready", "the meal is ready", "that's it", "let's eat"]) {
    assert.equal(kind(phrase, true), "finish", phrase);
  }
  // Before the last step, "done" is the end of a step, but "the meal is ready" still means finish.
  assert.equal(kind("done"), "next");
  assert.equal(kind("the meal is ready"), "finish");
});

test("other commands and questions", () => {
  assert.equal(kind("go back"), "previous");
  assert.equal(kind("previous step"), "previous");
  assert.deepEqual(cookingIntent("go to step 3", false), { kind: "goto", step: 3 });
  assert.deepEqual(cookingIntent("Step four", false), { kind: "goto", step: 4 });
  assert.equal(kind("repeat that"), "repeat");
  assert.equal(kind("how much time is left?"), "time");
  assert.equal(kind("which step am I on"), "where");
  assert.equal(kind("stop listening"), "stop-listening");
  assert.equal(kind("cancel cooking"), "cancel");
  assert.equal(kind("how do I know when the chicken is cooked?"), "question");
  assert.equal(kind("is this the last step?", true), "question");
});

test("wake phrase variants and confirmations", () => {
  for (const phrase of ["Hey Mimi", "hey, Mimi!", "hey mimmy", "Hi Mimi", "okay mimi", "a mimi", "Mimi, are you there?"]) {
    assert.equal(isWakePhrase(phrase), true, phrase);
  }
  assert.equal(isWakePhrase("hey mom"), false);
  assert.equal(isWakePhrase("the minimum"), false);
  assert.equal(confirms("Yes, confirm finish"), true);
  assert.equal(declines("never mind"), true);
});
