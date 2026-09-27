import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { api } from "../api";
import { readStorage } from "../storage";
import { isWakePhrase } from "../voiceCommands";
import { Icon } from "./ui";

export type HandsFreeResult = { response: string; stopListening?: boolean; afterSpeech?: () => void | Promise<void> };
type WakeRecognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: (() => void) | null;
  onresult: ((event: { resultIndex: number; results: ArrayLike<{ [index: number]: { transcript: string } }> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
};
export function HandsFreeCooking({ onCommand }: { onCommand: (transcript: string) => Promise<HandsFreeResult> }) {
  const [enabled, setEnabled] = useState(false);
  // ?voicePreview=listening|speaking shows the panel mid-conversation (used for the product tour screenshots).
  const preview = new URLSearchParams(window.location.search).get("voicePreview");
  const [status, setStatus] = useState<"off" | "connecting" | "listening" | "processing" | "speaking" | "error">(() => preview === "speaking" || preview === "listening" ? preview : "off");
  const [lastHeard, setLastHeard] = useState("");
  const [lastResponse, setLastResponse] = useState("");
  const [error, setError] = useState("");
  const [wakeStatus, setWakeStatus] = useState<"starting" | "ready" | "needs-permission" | "unavailable">("starting");
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedVoiceUri] = useState(() => readStorage("mealmatch-cooking-voice") || "auto");
  const enabledRef = useRef(false);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const monitorFrameRef = useRef<number | null>(null);
  const restartTimerRef = useRef<number | null>(null);
  const onCommandRef = useRef(onCommand);
  const selectedVoiceRef = useRef<SpeechSynthesisVoice | null>(null);
  const wakeRecognitionRef = useRef<WakeRecognition | null>(null);
  const wakeActiveRef = useRef(true);
  // False after the browser refused the microphone; true again once "Start voice" is allowed.
  const wakeAllowedRef = useRef(true);
  const wakeRestartTimerRef = useRef<number | null>(null);
  const activationRef = useRef(0);
  const connectingRef = useRef(false);
  const transcriptionRef = useRef<AbortController | null>(null);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const waveformRef = useRef<HTMLDivElement | null>(null);
  const speechPulseRef = useRef(0);
  const naturalVoices = useMemo(() => {
    const uniqueVoices = Array.from(new Map(voices.filter((voice) => voice.lang.toLowerCase().startsWith("en")).map((voice) => [voice.voiceURI, voice])).values());
    return uniqueVoices.sort((first, second) => naturalVoiceScore(second) - naturalVoiceScore(first));
  }, [voices]);
  const recommendedVoice = naturalVoices[0] || null;
  const selectedVoice = selectedVoiceUri === "auto" ? recommendedVoice : naturalVoices.find((voice) => voice.voiceURI === selectedVoiceUri) || recommendedVoice;

  useEffect(() => { onCommandRef.current = onCommand; }, [onCommand]);
  useEffect(() => { selectedVoiceRef.current = selectedVoice; }, [selectedVoice]);

  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const loadVoices = () => setVoices(window.speechSynthesis.getVoices());
    loadVoices();
    window.speechSynthesis.addEventListener("voiceschanged", loadVoices);
    return () => window.speechSynthesis.removeEventListener("voiceschanged", loadVoices);
  }, []);

  useEffect(() => () => {
    wakeActiveRef.current = false;
    activationRef.current += 1;
    connectingRef.current = false;
    if (wakeRestartTimerRef.current != null) window.clearTimeout(wakeRestartTimerRef.current);
    wakeRecognitionRef.current?.abort();
    enabledRef.current = false;
    transcriptionRef.current?.abort();
    if (monitorFrameRef.current != null) window.cancelAnimationFrame(monitorFrameRef.current);
    if (restartTimerRef.current != null) window.clearTimeout(restartTimerRef.current);
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    void audioContextRef.current?.close();
    stopSpeaking();
  }, []);

  function stopSpeaking() {
    const utterance = utteranceRef.current;
    if (utterance) {
      utterance.onstart = null;
      utterance.onend = null;
      utterance.onerror = null;
      utteranceRef.current = null;
    }
    window.speechSynthesis?.cancel();
  }

  function stopMonitoring() {
    if (monitorFrameRef.current != null) window.cancelAnimationFrame(monitorFrameRef.current);
    monitorFrameRef.current = null;
    waveformRef.current?.querySelectorAll<HTMLElement>("i").forEach((bar) => bar.style.setProperty("--voice-level", "0.08"));
  }

  function disableHandsFree() {
    activationRef.current += 1;
    connectingRef.current = false;
    enabledRef.current = false;
    transcriptionRef.current?.abort();
    transcriptionRef.current = null;
    stopMonitoring();
    if (restartTimerRef.current != null) window.clearTimeout(restartTimerRef.current);
    restartTimerRef.current = null;
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
    recorderRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    void audioContextRef.current?.close();
    audioContextRef.current = null;
    analyserRef.current = null;
    stopSpeaking();
    setEnabled(false);
    setStatus("off");
    startWakeListener();
  }

  function startWakeListener() {
    const recognition = wakeRecognitionRef.current;
    if (!recognition || !wakeActiveRef.current || !wakeAllowedRef.current || enabledRef.current || connectingRef.current) return;
    try { recognition.start(); } catch { /* Already listening. */ }
  }

  function scheduleListening() {
    if (!enabledRef.current || !streamRef.current) return;
    if (restartTimerRef.current != null) window.clearTimeout(restartTimerRef.current);
    restartTimerRef.current = window.setTimeout(() => {
      if (enabledRef.current && streamRef.current) startListeningCycle(streamRef.current);
    }, 350);
  }

  function speakAndContinue(text: string, stopAfter = false, afterSpeech?: () => void | Promise<void>) {
    const displayText = text.replace(/[*#_`]/g, "").trim();
    const spokenText = makeSpeechNatural(displayText);
    setLastResponse(displayText);
    if (!enabledRef.current) return;
    const activation = activationRef.current;
    let finished = false;
    const finishResponse = async () => {
      if (finished || !enabledRef.current || activation !== activationRef.current) return;
      finished = true;
      utteranceRef.current = null;
      setStatus("processing");
      if (stopAfter) disableHandsFree();
      try { await afterSpeech?.(); } finally {
        if (!stopAfter) scheduleListening();
      }
    };
    if (!("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
      void finishResponse();
      return;
    }
    stopSpeaking();
    const utterance = new SpeechSynthesisUtterance(spokenText);
    utteranceRef.current = utterance;
    const voice = selectedVoiceRef.current;
    if (voice) {
      utterance.voice = voice;
      utterance.lang = voice.lang;
    } else {
      utterance.lang = "en-SG";
    }
    utterance.rate = 0.92;
    utterance.pitch = 1.03;
    utterance.volume = 0.96;
    utterance.onstart = () => {
      if (enabledRef.current && activation === activationRef.current) setStatus("speaking");
    };
    utterance.onend = () => void finishResponse();
    utterance.onerror = () => void finishResponse();
    // Word boundaries drive the "Mimi is speaking" waveform in time with the voice.
    utterance.onboundary = () => { speechPulseRef.current = 1; };
    window.speechSynthesis.speak(utterance);
  }

  function startListeningCycle(stream: MediaStream) {
    if (!enabledRef.current || recorderRef.current?.state === "recording") return;
    const listeningActivation = activationRef.current;
    setError("");
    setStatus("listening");
    const preferredType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : MediaRecorder.isTypeSupported("audio/mp4") ? "audio/mp4" : "";
    const recorder = new MediaRecorder(stream, preferredType ? { mimeType: preferredType } : undefined);
    const chunks: BlobPart[] = [];
    let shouldProcess = false;
    recorderRef.current = recorder;
    recorder.ondataavailable = (event) => event.data.size && chunks.push(event.data);
    recorder.onstop = async () => {
      if (listeningActivation !== activationRef.current) return;
      stopMonitoring();
      if (recorderRef.current === recorder) recorderRef.current = null;
      if (!enabledRef.current) return;
      if (!shouldProcess || chunks.length === 0) {
        scheduleListening();
        return;
      }
      setStatus("processing");
      const transcription = new AbortController();
      const activation = activationRef.current;
      transcriptionRef.current = transcription;
      try {
        const mimeType = recorder.mimeType || "audio/webm";
        const extension = mimeType.includes("mp4") ? "mp4" : mimeType.includes("ogg") ? "ogg" : "webm";
        const formData = new FormData();
        formData.append("file", new File(chunks, `hands-free-command.${extension}`, { type: mimeType }));
        const response = await api.post("/transcribe-audio", formData, { headers: { "Content-Type": "multipart/form-data" }, signal: transcription.signal });
        if (!enabledRef.current || activation !== activationRef.current) return;
        const transcript = String(response.data.text || "").trim();
        if (!transcript) {
          speakAndContinue("I didn't catch that. I'm listening again.");
          return;
        }
        setLastHeard(transcript);
        const result = await onCommandRef.current(transcript);
        if (!enabledRef.current || activation !== activationRef.current) return;
        speakAndContinue(result.response, Boolean(result.stopListening), result.afterSpeech);
      } catch (commandError) {
        if (transcription.signal.aborted || !enabledRef.current || activation !== activationRef.current) return;
        const detail = (commandError as { response?: { data?: { detail?: string } } }).response?.data?.detail;
        setError(detail || "I couldn't process that voice command.");
        setStatus("error");
        speakAndContinue("I couldn't process that. I'll listen again.");
      } finally {
        if (transcriptionRef.current === transcription) transcriptionRef.current = null;
      }
    };
    recorder.start(250);

    const analyser = analyserRef.current;
    if (!analyser) return;
    const levels = new Uint8Array(analyser.fftSize);
    const cycleStarted = performance.now();
    let speechStartedAt = 0;
    let silenceStartedAt = 0;
    let lastWaveformUpdate = 0;
    const waveformBars = waveformRef.current?.querySelectorAll<HTMLElement>("i");

    const monitor = () => {
      if (!enabledRef.current || listeningActivation !== activationRef.current || recorder.state !== "recording") return;
      analyser.getByteTimeDomainData(levels);
      let energy = 0;
      for (const level of levels) {
        const sample = (level - 128) / 128;
        energy += sample * sample;
      }
      const volume = Math.sqrt(energy / levels.length);
      const now = performance.now();
      // The listening waveform is measured microphone energy. Update the DOM at
      // 20fps so the recording loop does not cause React or the timer to rerender.
      if (waveformBars && now - lastWaveformUpdate > 50) {
        const samplesPerBar = Math.max(1, Math.floor(levels.length / waveformBars.length));
        waveformBars.forEach((bar, index) => {
          let barEnergy = 0;
          for (let offset = 0; offset < samplesPerBar; offset += 1) {
            const sample = (levels[index * samplesPerBar + offset] - 128) / 128;
            barEnergy += sample * sample;
          }
          const level = Math.min(1, Math.max(0.08, Math.sqrt(barEnergy / samplesPerBar) * 7));
          bar.style.setProperty("--voice-level", level.toFixed(3));
        });
        lastWaveformUpdate = now;
      }
      if (volume > 0.022) {
        if (!speechStartedAt) speechStartedAt = now;
        silenceStartedAt = 0;
      } else if (speechStartedAt) {
        if (!silenceStartedAt) silenceStartedAt = now;
        if (now - silenceStartedAt > 1250 && now - speechStartedAt > 500) {
          shouldProcess = true;
          recorder.stop();
          return;
        }
      }
      if (speechStartedAt && now - speechStartedAt > 18000) {
        shouldProcess = true;
        recorder.stop();
        return;
      }
      if (!speechStartedAt && now - cycleStarted > 30000) {
        recorder.stop();
        return;
      }
      monitorFrameRef.current = window.requestAnimationFrame(monitor);
    };
    monitorFrameRef.current = window.requestAnimationFrame(monitor);
  }

  async function enableHandsFree() {
    if (enabledRef.current || connectingRef.current) return;
    const activation = ++activationRef.current;
    connectingRef.current = true;
    setStatus("connecting");
    if (wakeRestartTimerRef.current != null) window.clearTimeout(wakeRestartTimerRef.current);
    wakeRecognitionRef.current?.stop();
    setError("");
    let requestedStream: MediaStream | null = null;
    let requestedContext: AudioContext | null = null;
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") throw new Error("Hands-free cooking is not supported in this browser.");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      requestedStream = stream;
      if (activation !== activationRef.current) { stream.getTracks().forEach((track) => track.stop()); return; }
      const audioContext = new AudioContext();
      requestedContext = audioContext;
      // Started by "Hey Mimi" rather than a tap, resume() can wait for a gesture: never wait forever.
      await Promise.race([audioContext.resume(), new Promise((resolve) => window.setTimeout(resolve, 600))]);
      if (activation !== activationRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        await audioContext.close();
        return;
      }
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.76;
      audioContext.createMediaStreamSource(stream).connect(analyser);
      streamRef.current = stream;
      audioContextRef.current = audioContext;
      analyserRef.current = analyser;
      enabledRef.current = true;
      wakeAllowedRef.current = true;
      setWakeStatus("ready");
      setEnabled(true);
      setStatus("processing");
      speakAndContinue("Hey, Mimi here!");
    } catch (permissionError) {
      requestedStream?.getTracks().forEach((track) => track.stop());
      if (requestedContext && requestedContext.state !== "closed") void requestedContext.close();
      if (activation !== activationRef.current) return;
      const message = permissionError instanceof Error ? permissionError.message : "Microphone access failed.";
      setError(message);
      setStatus("error");
    } finally {
      if (activation === activationRef.current) connectingRef.current = false;
    }
  }

  // "Hey Mimi" listener, running while hands-free mode is off.
  // Round 2 found it never worked before hands-free had been turned on once. Fixes:
  // each listener instance stops for good when unmounted (React's development
  // double mount left two instances restarting and cutting each other off);
  // punctuation and common mishearings ("hey, Mimi", "hey mimmy") still count;
  // the browser's English variant is used, with en-US as a fallback; and a
  // refused microphone shows how to allow it instead of failing silently.
  useEffect(() => {
    const speechWindow = window as unknown as {
      SpeechRecognition?: new () => WakeRecognition;
      webkitSpeechRecognition?: new () => WakeRecognition;
    };
    const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setWakeStatus("unavailable");
      return;
    }
    let disposed = false;
    wakeActiveRef.current = true;
    const recognition = new Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = navigator.language?.toLowerCase().startsWith("en") ? navigator.language : "en-US";
    recognition.onstart = () => { if (!disposed) setWakeStatus("ready"); };
    recognition.onresult = (event) => {
      if (disposed || enabledRef.current || connectingRef.current) return;
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        if (isWakePhrase(event.results[index][0]?.transcript || "")) {
          recognition.stop();
          void enableHandsFree();
          return;
        }
      }
    };
    recognition.onerror = (event) => {
      if (disposed) return;
      if (event.error === "language-not-supported" && recognition.lang !== "en-US") {
        recognition.lang = "en-US"; // restarted by onend
      } else if (["not-allowed", "service-not-allowed", "audio-capture"].includes(event.error)) {
        // Browsers only let a page listen once the microphone is allowed; one tap on Start voice does that.
        wakeAllowedRef.current = false;
        setWakeStatus("needs-permission");
      } else if (!["no-speech", "aborted", "network"].includes(event.error)) {
        setWakeStatus("unavailable");
      }
    };
    recognition.onend = () => {
      if (disposed || !wakeActiveRef.current) return;
      if (wakeRestartTimerRef.current != null) window.clearTimeout(wakeRestartTimerRef.current);
      wakeRestartTimerRef.current = window.setTimeout(() => { if (!disposed) startWakeListener(); }, 400);
    };
    wakeRecognitionRef.current = recognition;
    startWakeListener();
    return () => {
      disposed = true;
      wakeActiveRef.current = false;
      if (wakeRestartTimerRef.current != null) window.clearTimeout(wakeRestartTimerRef.current);
      recognition.onstart = recognition.onresult = recognition.onerror = recognition.onend = null;
      recognition.abort();
      if (wakeRecognitionRef.current === recognition) wakeRecognitionRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one listener per mount; it reads live refs
  }, []);

  const statusCopy = status === "connecting" ? "Opening your microphone…" : status === "listening" ? "Listening to you…" : status === "processing" ? "Thinking…" : status === "speaking" ? "Mimi is answering" : status === "error" ? "Check microphone access" : "Cook hands-free";

  return (
    <section id="mimi-hands-free" className={`cooking-voice-control ${status}`} aria-label="Hands-free cooking">
      <button className="cooking-voice-button" onClick={() => enabled || status === "connecting" ? disableHandsFree() : void enableHandsFree()} aria-pressed={enabled} aria-label={enabled || status === "connecting" ? "Turn off hands-free cooking" : "Turn on hands-free cooking"}>
        <Icon name="microphone" /><span>{enabled ? "End voice" : status === "connecting" ? "Cancel" : "Start voice"}</span>
      </button>
      <div className="cooking-voice-copy"><strong role="status">{statusCopy}</strong><small>{enabled ? "Say “next”, “go back”, “repeat” or ask a question. On the last step, say “done”." : wakeStatus === "ready" ? "Say “Hey Mimi” or tap to begin." : wakeStatus === "needs-permission" ? "Tap Start voice once to let Mimi hear “Hey Mimi”." : wakeStatus === "starting" ? "Getting ready to hear “Hey Mimi”…" : "Tap the mic, then ask for the next step."}</small></div>
      <VoiceWaveform status={status} analyser={analyserRef} pulse={speechPulseRef} preview={Boolean(preview)} />
      {(lastHeard || lastResponse || error) && <div className="cooking-voice-transcript" aria-live="polite" aria-atomic="false">{lastHeard && <p><b>You</b><span>{lastHeard}</span></p>}{lastResponse && <p><b>Mimi</b><span>{lastResponse}</span></p>}{error && <p className="voice-error" role="alert">{error}</p>}</div>}
    </section>
  );
}

/**
 * Live voice waveform. Listening: drawn from the microphone analyser (measured
 * energy). Speaking: speech synthesis exposes no audio samples, so the wave is
 * driven by the utterance's word-boundary events and follows the voice's rhythm.
 */
function VoiceWaveform({ status, analyser, pulse, preview = false }: { status: string; analyser: RefObject<AnalyserNode | null>; pulse: RefObject<number>; preview?: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const statusRef = useRef(status);
  statusRef.current = status;
  useEffect(() => {
    let frame = 0;
    let level = 0;
    let time = 0;
    const samples = new Uint8Array(1024);
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const draw = () => {
      const element = canvas.current;
      if (!element) return;
      const ratio = Math.min(2, window.devicePixelRatio || 1);
      const width = element.clientWidth;
      const height = element.clientHeight;
      if (element.width !== Math.round(width * ratio)) { element.width = Math.round(width * ratio); element.height = Math.round(height * ratio); }
      const context = element.getContext("2d");
      if (!context) return;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);
      const mode = statusRef.current;
      let target = 0.035;
      if (mode === "listening" && analyser.current) {
        analyser.current.getByteTimeDomainData(samples);
        let energy = 0;
        for (const sample of samples) energy += ((sample - 128) / 128) ** 2;
        target = Math.min(1, Math.sqrt(energy / samples.length) * 9 + 0.05);
      } else if (mode === "listening" && preview) {
        target = 0.45 + 0.35 * Math.abs(Math.sin(time * 2.3)) * Math.abs(Math.sin(time * 5.1));
      } else if (mode === "speaking") {
        if (preview && Math.random() < 0.09) pulse.current = 1;
        pulse.current *= 0.94;
        target = 0.22 + 0.7 * pulse.current;
      } else if (mode === "processing" || mode === "connecting") {
        target = 0.1 + 0.05 * Math.sin(time * 4);
      }
      level += (target - level) * 0.16;
      time += reduced ? 0 : 1 / 60;
      const color = getComputedStyle(element).color;
      for (let layer = 0; layer < 3; layer += 1) {
        context.beginPath();
        for (let x = 0; x <= width; x += 2) {
          const position = x / width;
          const envelope = Math.pow(Math.sin(Math.PI * position), 1.8);
          const y = height / 2 + Math.sin(position * (9 + layer * 4) * Math.PI - time * (4 + layer * 1.7)) * envelope * level * height * 0.42 * (1 - layer * 0.27);
          if (x === 0) context.moveTo(x, y); else context.lineTo(x, y);
        }
        context.strokeStyle = color;
        context.globalAlpha = [0.95, 0.5, 0.28][layer];
        context.lineWidth = [2.4, 1.8, 1.4][layer];
        context.stroke();
      }
      context.globalAlpha = 1;
      frame = window.requestAnimationFrame(draw);
    };
    frame = window.requestAnimationFrame(draw);
    return () => window.cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- one drawing loop; it reads live refs
  }, []);
  const speaker = status === "listening" ? "You" : status === "speaking" ? "Mimi" : "";
  return <div className={`voice-waveform ${status}`} aria-hidden="true">{speaker && <span className="voice-waveform-label">{speaker}</span>}<canvas ref={canvas} /></div>;
}

function naturalVoiceScore(voice: SpeechSynthesisVoice) {
  const name = voice.name.toLowerCase();
  const language = voice.lang.toLowerCase();
  let score = voice.default ? 12 : 0;
  if (voice.localService) score += 8;
  if (language === "en-sg") score += 24;
  else if (language.startsWith("en-gb") || language.startsWith("en-au")) score += 18;
  else if (language.startsWith("en-us")) score += 15;
  if (/natural|neural|premium|enhanced/.test(name)) score += 100;
  if (/ava|samantha|serena|karen|susan|sonia|aria|jenny|emma|olivia|google uk english female|google us english/.test(name)) score += 55;
  if (/compact|espeak|novelty|zarvox|trinoids|whisper|bad news|good news|bells/.test(name)) score -= 100;
  return score;
}

function makeSpeechNatural(text: string) {
  return text
    .replace(/\bPrep\b/gi, "Preparation")
    .replace(/\btbsp\b/gi, "tablespoon")
    .replace(/\btsp\b/gi, "teaspoon")
    .replace(/\bmins?\b/gi, "minutes")
    .replace(/\s*[:;]\s*/g, ", ")
    .replace(/\s+/g, " ")
    .trim();
}
