import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, errorMessage } from "../api";
import type { Recipe, CookingSession } from "../types";
import { readStorage, useStoredState, writeStorage } from "../storage";
import { CountdownText, PageHeader, Icon } from "../components/ui";
import { IngredientEmoji } from "../components/FoodArt";
import { RecipeCard } from "../components/RecipeCard";

export function ChatScreen({ userId, recipes, activeCooking, onSessionUpdate, onResumeCooking, onEndCooking, onCreateRecipes, onOpenRecipe, onToggleSaved }: { userId: number; recipes: Recipe[]; activeCooking: CookingSession | null; onSessionUpdate: (session: CookingSession) => void; onResumeCooking: () => void; onEndCooking: () => Promise<void>; onCreateRecipes: (request: string, onProgress?: (recipes: Recipe[]) => void) => Promise<Recipe[]>; onOpenRecipe: (recipe: Recipe) => void; onToggleSaved: (recipe: Recipe) => void }) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; text: string }[]>(() => readSavedChat());
  const [sending, setSending] = useState(false);
  const [creatingRecipes, setCreatingRecipes] = useState(false);
  // Recipe cards made from a chat request stay with the chat history until it is cleared.
  const [recipeOptionIds, setRecipeOptionIds] = useStoredState<number[]>("mealmatch-assistant-recipe-options", [], "local");
  const recipeOptions = recipeOptionIds.map((id) => recipes.find((recipe) => recipe.id === id)).filter((recipe): recipe is Recipe => Boolean(recipe));
  const suggestions = ["What can I cook with ingredients expiring soon?", "Suggest a quick 15-minute dinner", "How can I make my next meal healthier?"];

  useEffect(() => {
    if (activeCooking) {
      setMessages(activeCooking.messages.map((message) => ({ role: message.role, text: message.text })));
    } else {
      setMessages(readSavedChat());
    }
  }, [activeCooking]);

  useEffect(() => {
    if (!activeCooking) writeStorage("mealmatch-assistant-history", JSON.stringify(messages.slice(-30)));
  }, [activeCooking, messages]);

  async function ask(question: string) {
    const cleanQuestion = question.trim();
    if (!cleanQuestion || sending) return;
    setMessages((current) => [...current, { role: "user", text: cleanQuestion }]);
    setInput("");
    setSending(true);
    try {
      if (activeCooking) {
        const response = await api.post(`/cooking-session/${activeCooking.user_id}/ask`, { question: cleanQuestion });
        onSessionUpdate(response.data);
        setMessages(response.data.messages.map((message: { role: "user" | "assistant"; text: string }) => ({ role: message.role, text: message.text })));
      } else {
        const response = await api.post(`/assistant/${userId}`, { question: cleanQuestion });
        setMessages((current) => [...current, { role: "assistant", text: response.data.answer }]);
      }
    } catch {
      setMessages((current) => [...current, { role: "assistant", text: "I’m having trouble reaching the cooking model right now. Your pantry is still safely saved." }]);
    } finally { setSending(false); }
  }

  function submit(event: FormEvent) { event.preventDefault(); void ask(input); }

  async function createRecipeCards() {
    const latestRequest = [...messages].reverse().find((message) => message.role === "user")?.text;
    if (!latestRequest || creatingRecipes) return;
    setCreatingRecipes(true);
    try {
      const created = await onCreateRecipes(latestRequest, (progress) => setRecipeOptionIds(progress.map((recipe) => recipe.id)));
      setRecipeOptionIds(created.map((recipe) => recipe.id));
    } catch (error) {
      setMessages((current) => [...current, { role: "assistant", text: errorMessage(error, "I couldn’t turn that into recipes right now. Check that Ollama is running, then try again.") }]);
    } finally {
      setCreatingRecipes(false);
    }
  }

  function clearHistory() {
    writeStorage("mealmatch-assistant-history", null);
    setMessages([]);
    setRecipeOptionIds([]);
  }

  return (
    <div className="screen chat-screen">
      <PageHeader eyebrow="Ask anything about cooking" title="Cooking assistant" subtitle="I know what’s in your pantry" action={!activeCooking && messages.length > 0 ? <button className="clear-chat" onClick={clearHistory}>Clear history</button> : undefined} />
      {activeCooking && <div className="chat-context-wrap"><button className="chat-recipe-context" onClick={onResumeCooking}><IngredientEmoji name={activeCooking.recipe.ingredients.split(",")[0]} /><div><small>Questions are linked to your active recipe</small><strong>{activeCooking.recipe.title}</strong><span>Ready in <CountdownText readyAt={activeCooking.ready_at} /></span></div><Icon name="arrow" /></button><button className="end-chat-session" onClick={() => void onEndCooking()}><Icon name="check" /> I’ve finished cooking</button></div>}
      {messages.length === 0 ? (
        <div className="chat-empty"><span className="assistant-orb"><Icon name="sparkles" /></span><h2>{activeCooking ? `Cooking ${activeCooking.recipe.title}` : "What are we making?"}</h2><p>{activeCooking ? "Ask about the current step, timing, substitutions, or doneness. This conversation stays attached to this cooking session." : "Ask me about recipes, substitutions, cooking techniques, or how to use ingredients before they expire."}</p><div className="prompt-list">{(activeCooking ? ["What should I do next?", "How do I know when it is cooked?", "Can I substitute a missing ingredient?"] : suggestions).map((suggestion) => <button key={suggestion} onClick={() => void ask(suggestion)}>{suggestion}<Icon name="arrow" /></button>)}</div></div>
      ) : (
        <div className="messages">{messages.map((message, index) => <div className={`message ${message.role}`} key={index}>{message.role === "assistant" && <span><Icon name="chef" /></span>}<p>{message.text}</p></div>)}{sending && <div className="message assistant"><span><Icon name="chef" /></span><p className="typing">Thinking…</p></div>}{!activeCooking && !sending && <button className="assistant-recipe-action" disabled={creatingRecipes} onClick={() => void createRecipeCards()}><Icon name="sparkles" />{creatingRecipes ? "Creating three recipe cards…" : "Turn my request into 3 recipe choices"}</button>}{recipeOptions.length > 0 && <section className="assistant-recipe-options"><div><p className="eyebrow">Saved to Recipes</p><h3>Choose a recipe to see the full method</h3></div><div>{recipeOptions.map((recipe, index) => <RecipeCard key={recipe.id} recipe={recipe} index={index} onClick={() => onOpenRecipe(recipe)} onToggleSaved={() => onToggleSaved(recipe)} />)}</div></section>}</div>
      )}
      <form className="chat-composer" onSubmit={submit}><VoiceRecorder onTranscript={setInput} /><div><Icon name="sparkles" /><input value={input} onChange={(event) => setInput(event.target.value)} placeholder="Ask or speak about cooking…" /></div><button aria-label="Send question" disabled={!input.trim() || sending}><Icon name="send" /></button></form>
    </div>
  );
}

function VoiceRecorder({ onTranscript }: { onTranscript: (text: string) => void }) {
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [error, setError] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => () => streamRef.current?.getTracks().forEach((track) => track.stop()), []);

  async function toggleRecording() {
    if (recording) {
      recorderRef.current?.stop();
      setRecording(false);
      return;
    }
    setError("");
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") throw new Error("Voice recording is not supported in this browser.");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const preferredType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : MediaRecorder.isTypeSupported("audio/mp4") ? "audio/mp4" : "";
      const recorder = new MediaRecorder(stream, preferredType ? { mimeType: preferredType } : undefined);
      const chunks: BlobPart[] = [];
      recorder.ondataavailable = (event) => event.data.size && chunks.push(event.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        setTranscribing(true);
        try {
          const mimeType = recorder.mimeType || "audio/webm";
          const extension = mimeType.includes("mp4") ? "mp4" : mimeType.includes("ogg") ? "ogg" : "webm";
          const formData = new FormData();
          formData.append("file", new File(chunks, `voice-command.${extension}`, { type: mimeType }));
          const response = await api.post("/transcribe-audio", formData, { headers: { "Content-Type": "multipart/form-data" } });
          if (response.data.text?.trim()) onTranscript(response.data.text.trim());
          else setError("Whisper did not hear any speech. Please try again.");
        } catch (uploadError) {
          const detail = (uploadError as { response?: { data?: { detail?: string } } }).response?.data?.detail;
          setError(detail || "Voice transcription failed.");
        } finally { setTranscribing(false); }
      };
      recorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch (recordingError) {
      setError(recordingError instanceof Error ? recordingError.message : "Microphone access failed.");
    }
  }

  return <div className="voice-control"><button type="button" className={recording ? "recording" : ""} disabled={transcribing} onClick={() => void toggleRecording()} aria-label={recording ? "Stop recording" : "Speak with Whisper"}><Icon name="microphone" />{recording && <i />}</button>{(transcribing || error) && <span className={error ? "error" : ""}>{transcribing ? "Whisper is transcribing…" : error}</span>}</div>;
}

function readSavedChat(): { role: "user" | "assistant"; text: string }[] {
  try {
    const stored = JSON.parse(readStorage("mealmatch-assistant-history") || "[]");
    return Array.isArray(stored) ? stored.filter((message) => (message?.role === "user" || message?.role === "assistant") && typeof message?.text === "string").slice(-30) : [];
  } catch { return []; }
}
