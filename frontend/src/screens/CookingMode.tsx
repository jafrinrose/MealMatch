import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { confirms, cookingIntent, declines } from "../voiceCommands";
import type { CookingSession } from "../types";
import { fallbackStepMinutes, formatClockTime } from "../utils";
import { CountdownText, Icon } from "../components/ui";
import { RecipeArtwork } from "../components/FoodArt";
import { HandsFreeCooking, type HandsFreeResult } from "../components/HandsFreeCooking";

function CookingTimeline({ startedAt, readyAt }: { startedAt: string; readyAt: string }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const start = new Date(startedAt).getTime();
  const finish = new Date(readyAt).getTime();
  const duration = Math.max(finish - start, 1000);
  const remaining = Math.max(0, finish - now);
  const elapsedPercent = Math.min(100, Math.max(0, ((now - start) / duration) * 100));
  const totalSeconds = Math.floor(remaining / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const countdown = remaining > 0 ? `${hours ? `${hours}:` : ""}${String(minutes).padStart(hours ? 2 : 1, "0")}:${String(seconds).padStart(2, "0")} remaining` : "Ready now";
  return <section className="cooking-timeline" aria-label="Overall cooking time"><div><strong>Overall cooking time</strong><span>{countdown}</span></div><div className="cooking-time-track"><span style={{ width: `${elapsedPercent}%` }} /></div><small>Started {formatClockTime(startedAt)} · Estimated finish {formatClockTime(readyAt)}</small></section>;
}

export function CookingMode({ session, onBack, onSessionUpdate, onCancel, onComplete }: { session: CookingSession; onBack: () => void; onSessionUpdate: (session: CookingSession) => void; onCancel: () => Promise<void>; onComplete: () => Promise<void> }) {
  const [updating, setUpdating] = useState(false);
  const [pendingVoiceConfirmation, setPendingVoiceConfirmation] = useState<"cancel" | "finish" | null>(null);
  const [stepError, setStepError] = useState("");
  const recipe = session.recipe;
  const stepDetails = recipe.step_details || (recipe.instruction_steps || recipe.instructions.split(/(?<=[.!?])\s+/).filter(Boolean)).map((instruction, index, all) => ({ instruction, minutes: fallbackStepMinutes(instruction, index, all.length, recipe) }));
  const currentStep = Math.min(session.current_step, Math.max(stepDetails.length - 1, 0));

  async function moveToStep(step: number) {
    setUpdating(true);
    // The card moves at once, so it changes as Mimi starts to read the step; the server then confirms.
    onSessionUpdate({ ...session, current_step: step });
    try {
      const response = await api.put(`/cooking-session/${session.user_id}/step`, { current_step: step });
      onSessionUpdate(response.data);
    } catch (error) {
      onSessionUpdate(session);
      throw error;
    } finally { setUpdating(false); }
  }

  // Buttons: the card moves back if the server did not save the step, and the cook is told why.
  function goToStep(step: number) {
    setStepError("");
    void moveToStep(step).catch((error) => setStepError(errorMessage(error, "Could not save your step. Check your connection and try again.")));
  }

  function timeRemainingForSpeech() {
    const remaining = Math.max(0, new Date(session.ready_at).getTime() - Date.now());
    if (!remaining) return "The overall recipe timer has finished.";
    const totalMinutes = Math.ceil(remaining / 60000);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    if (hours) return `About ${hours} hour${hours === 1 ? "" : "s"}${minutes ? ` and ${minutes} minutes` : ""} remain.`;
    return `About ${minutes} minute${minutes === 1 ? "" : "s"} remain.`;
  }

  async function handleVoiceCommand(transcript: string): Promise<HandsFreeResult> {
    const lastStep = stepDetails.length - 1;
    const onFinalStep = currentStep >= lastStep;

    if (pendingVoiceConfirmation) {
      if (declines(transcript)) {
        setPendingVoiceConfirmation(null);
        return { response: "Okay, no changes made. We can keep cooking." };
      }
      if (confirms(transcript) && pendingVoiceConfirmation === "cancel") {
        setPendingVoiceConfirmation(null);
        return { response: "Cooking cancelled. Your pantry stays as it is.", stopListening: true, afterSpeech: onCancel };
      }
      if (confirms(transcript) && pendingVoiceConfirmation === "finish") {
        setPendingVoiceConfirmation(null);
        return { response: "Your meal is ready. Enjoy! I've updated your pantry.", stopListening: true, afterSpeech: onComplete };
      }
      return { response: `Please say confirm ${pendingVoiceConfirmation}, or say never mind.` };
    }

    // One intent per transcript (voiceCommands.ts), so what Mimi says and what the card shows always agree.
    const intent = cookingIntent(transcript, onFinalStep);
    switch (intent.kind) {
      case "stop-listening":
        return { response: "Hands-free mode is off.", stopListening: true };
      case "cancel":
        setPendingVoiceConfirmation("cancel");
        return { response: "Cancelling stops this cooking session and leaves your pantry as it is. Say confirm cancel, or say never mind." };
      case "finish":
        if (onFinalStep) {
          // The same as pressing "Meal is ready".
          return { response: "Your meal is ready. Enjoy! I've updated your pantry.", stopListening: true, afterSpeech: onComplete };
        }
        setPendingVoiceConfirmation("finish");
        return { response: `You still have ${lastStep - currentStep} step${lastStep - currentStep === 1 ? "" : "s"} to go. Say confirm finish to finish now, or say never mind.` };
      case "next": {
        const nextStep = currentStep + 1;
        await moveToStep(nextStep);
        const finalNote = nextStep === lastStep ? " This is the last step. Say done when your meal is ready." : "";
        return { response: `Step ${nextStep + 1}. ${stepDetails[nextStep].instruction} Suggested time: about ${stepDetails[nextStep].minutes} minutes.${finalNote}` };
      }
      case "previous": {
        if (currentStep === 0) return { response: "You are already on the first step." };
        const previousStep = currentStep - 1;
        await moveToStep(previousStep);
        return { response: `Back to step ${previousStep + 1}. ${stepDetails[previousStep].instruction}` };
      }
      case "goto": {
        const target = intent.step - 1;
        if (target < 0 || target > lastStep) return { response: `This recipe has ${stepDetails.length} steps.` };
        await moveToStep(target);
        return { response: `Step ${target + 1}. ${stepDetails[target].instruction}` };
      }
      case "hold":
        return { response: `Okay, staying on step ${currentStep + 1}.` };
      case "repeat":
        return { response: `Step ${currentStep + 1}. ${stepDetails[currentStep]?.instruction || "Your meal is ready."} Suggested time: about ${stepDetails[currentStep]?.minutes || 1} minutes.` };
      case "time":
        return { response: timeRemainingForSpeech() };
      case "where":
        return { response: `You are on step ${currentStep + 1} of ${stepDetails.length}. ${stepDetails[currentStep]?.instruction || "Your meal is ready."}` };
      case "help":
        return { response: "You can say next, go back, go to step three, repeat, how much time, done when the meal is ready, cancel cooking, or ask any recipe question." };
      case "question": {
        const response = await api.post(`/cooking-session/${session.user_id}/ask`, { question: transcript });
        onSessionUpdate(response.data);
        const assistantMessage = [...response.data.messages].reverse().find((message: { role: string; text: string }) => message.role === "assistant");
        return { response: assistantMessage?.text || "I couldn't find an answer, but I am still listening." };
      }
    }
  }

  return (
    <article className="cooking-mode screen">
      <div className="cooking-topbar"><button className="cooking-close" onClick={onBack} aria-label="Leave cooking view"><Icon name="close" /></button><span className="cooking-step-position">Cooking · Step {currentStep + 1} of {stepDetails.length}</span></div>
      <header className="cooking-header">
        <div className="cooking-photo"><RecipeArtwork recipe={recipe} /></div>
        <div><p className="eyebrow">Mimi is cooking with you</p><h1>{recipe.title}</h1><p>Take it one step at a time. Your progress and assistant conversation will stay saved.</p></div>
        <div className="ready-timer"><small>Ready by</small><strong>{formatClockTime(session.ready_at)}</strong><span><CountdownText readyAt={session.ready_at} /> left</span></div>
      </header>
      <CookingTimeline startedAt={session.started_at} readyAt={session.ready_at} />
      <HandsFreeCooking onCommand={handleVoiceCommand} />
      <section className="current-instruction">
        <span className="step-number">{currentStep + 1}</span>
        <div><p className="eyebrow">Step {currentStep + 1}</p><h2>{stepDetails[currentStep]?.instruction || "Your meal is ready to serve."}</h2><small>Suggested time: about {stepDetails[currentStep]?.minutes || 1} minutes</small></div>
      </section>
      <div className="cooking-step-list">
        {stepDetails.map((step, index) => <button className={index === currentStep ? "active" : index < currentStep ? "done" : ""} key={`${index}-${step.instruction}`} onClick={() => goToStep(index)}><span>{index < currentStep ? <Icon name="check" /> : index + 1}</span><p>{step.instruction}<small>{step.minutes} min</small></p></button>)}
      </div>
      {stepError && <p className="cooking-step-error" role="alert"><Icon name="alert" />{stepError}</p>}
      <div className="cooking-controls">
        <button className="cancel-cooking" disabled={updating} onClick={() => void onCancel()}><Icon name="close" /> Changed my mind — stop cooking</button>
        <div>
          {currentStep > 0 && <button className="secondary-button" disabled={updating} onClick={() => goToStep(currentStep - 1)}>Previous</button>}
          {currentStep < stepDetails.length - 1 ? <button className="primary-button" disabled={updating} onClick={() => goToStep(currentStep + 1)}>Next step <Icon name="arrow" /></button> : <button className="primary-button finish-button" onClick={() => void onComplete()}><Icon name="check" /> Meal is ready</button>}
        </div>
      </div>
    </article>
  );
}
