/**
 * Hands-free cooking commands: each transcript becomes exactly one action.
 *
 * User testing (round 2) found the voice and the screen disagreeing. Phrases with
 * "next" that were not an exact command ("okay next", "what's next", "next
 * please") went to the language model, which read out the next step while the
 * step card stayed where it was. On the last step, "done" also went to the
 * model, so the session could only be finished with the button. Now any "next"
 * moves the card, and finishing words on the last step do what the "Meal is
 * ready" button does.
 */

type CookingIntent =
  | { kind: "next" }
  | { kind: "previous" }
  | { kind: "goto"; step: number }
  | { kind: "hold" }
  | { kind: "repeat" }
  | { kind: "where" }
  | { kind: "time" }
  | { kind: "help" }
  | { kind: "stop-listening" }
  | { kind: "finish" }
  | { kind: "cancel" }
  | { kind: "question" };

const NUMBER_WORDS: Record<string, number> = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
  eleven: 11, twelve: 12, first: 1, second: 2, third: 3, fourth: 4, fifth: 5, sixth: 6,
};

function normalizeCommand(text: string): string {
  return text.toLowerCase().replace(/[’`]/g, "'").replace(/[^a-z0-9'\s]/g, " ").replace(/\s+/g, " ").trim();
}

const STOP_LISTENING = /\b(stop listening|pause listening|stop (the )?voice|turn off (the )?(voice|hands ?free|mic|microphone)|disable (the )?(voice|hands ?free)|mute (the )?(mic|microphone))\b/;
const CANCEL = /\b(cancel (the )?(cooking|recipe|session)|stop cooking|changed my mind|abandon (the )?(recipe|cooking)|restore (my |the )?pantry)\b/;
// Said at any step: the meal is finished.
const FINISH = /\b((the )?(meal|food|dinner|lunch|breakfast|dish) is (ready|done)|it'?s ready|finish(ed)? cooking|done cooking|complete (the )?(recipe|cooking|meal)|i'?m (all )?(done|finished)|i am (all )?(done|finished)|we'?re (all )?(done|finished)|all done|that'?s (it|everything)|let'?s eat|time to eat|ready to (eat|serve)|meal'?s ready)\b/;
// On the last step these words also finish, like the "Meal is ready" button.
const FINAL_STEP_FINISH = /\b(next|done|finished|finish|complete|completed|ready|served|serve it|over)\b/;
// "done with this step" is the end of a step, never the end of the meal.
const STEP_DONE = /\b(done|finished|through) with (this|the|that) step\b/;
const HOLD = /\b(wait|hold on|not yet|don'?t|do not|stay)\b/;
const NEXT = /\b(next|continue|move on|go on|go forward|carry on|keep going|onward|onwards|proceed|done|finished|completed?)\b/;
const PREVIOUS = /\b(previous|go back|back (a|one) step|one step back|step back|back up|undo)\b/;
const GOTO = /\b(?:go to|jump to|skip to|take me to|back to|show)? ?step (\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b/;
const REPEAT = /\b(repeat|say (that|it) again|again please|read (this|the current|the) step|what am i doing|pardon|come again|what did you say)\b/;
const TIME = /\b(how much time|time left|how long (is )?left|how long until|how long (will|does) it take|when (will|is) (it|the food|this|the meal) (be )?ready|check (the )?timer|timer)\b/;
const WHERE = /\b(what step|which step|where am i|what number)\b/;
const HELP = /\b(what can i say|voice help|help me use|voice commands|help)\b/;

export function cookingIntent(transcript: string, onFinalStep: boolean): CookingIntent {
  const command = normalizeCommand(transcript);
  if (!command) return { kind: "question" };
  if (STOP_LISTENING.test(command)) return { kind: "stop-listening" };
  if (CANCEL.test(command)) return { kind: "cancel" };
  if (STEP_DONE.test(command)) return { kind: onFinalStep ? "finish" : "next" };
  if (FINISH.test(command)) return { kind: "finish" };
  if (PREVIOUS.test(command)) return { kind: "previous" };
  const goto = command.match(GOTO);
  if (goto && (goto[0].startsWith("step") ? command === goto[0] || /^(go|jump|skip|take|back|show)/.test(command) : true)) {
    const step = Number(goto[1]) || NUMBER_WORDS[goto[1]];
    if (step) return { kind: "goto", step };
  }
  const saysNext = NEXT.test(command);
  if (saysNext && HOLD.test(command)) return { kind: "hold" };
  if (onFinalStep && FINAL_STEP_FINISH.test(command)) return { kind: "finish" };
  if (saysNext) return { kind: "next" };
  if (REPEAT.test(command)) return { kind: "repeat" };
  if (TIME.test(command)) return { kind: "time" };
  if (WHERE.test(command)) return { kind: "where" };
  if (HELP.test(command)) return { kind: "help" };
  return { kind: "question" };
}

// "Hey Mimi", as speech recognisers tend to write it.
const WAKE = /\b(hey|hi|hay|hei|heh|ay|a|ok|okay|yo|hello) (mimi|mimmy|mimmi|mimmie|mimie|mimy|meemee|mee mee|me me|mi mi|mini|minnie|memmi|mimis|mimi's)\b/;

export function isWakePhrase(transcript: string): boolean {
  const command = normalizeCommand(transcript);
  return WAKE.test(command) || /^(mimi|mimmy|mimmi|mimie)\b/.test(command);
}

export function confirms(transcript: string): boolean {
  const command = normalizeCommand(transcript);
  return /^(yes|yeah|yep|confirm|confirmed|do it|please do|go ahead|sure|ok|okay)\b/.test(command) || /\bconfirm (cancel|finish)\b/.test(command);
}

export function declines(transcript: string): boolean {
  return /^(no|nope|don'?t|do not|never mind|nevermind|keep cooking|cancel that)\b/.test(normalizeCommand(transcript));
}
