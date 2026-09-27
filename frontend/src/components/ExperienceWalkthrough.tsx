// SPDX-License-Identifier: AGPL-3.0-only
// Product tour. Hotspots use Propels-AI/Propels HotspotOverlay (see vendor notice);
// the cinematic player (camera moves, cursor, story progress, chapters) is local.
import { useEffect, useRef, useState, type CSSProperties } from "react";
import HotspotOverlay from "../vendor/propels/HotspotOverlay";
import captured from "./walkthrough-steps.json";
import "./experience-walkthrough.css";

type Capture = { image: string; x: number; y: number; zoom: { x: number; y: number; scale: number } };
const captures = captured as Record<string, Capture>;

const steps = [
  { id: "home", chapter: "Home", title: "Your kitchen, at a glance.", text: "Fresh, expiring and expired food, what to use first, and meals built around what you already have." },
  { id: "add", chapter: "Add food", title: "Snap your fridge.", text: "Take one photo, scan a receipt or type it in. A local vision model lists what it can see." },
  { id: "confirm", chapter: "Confirm", title: "You have the final say.", text: "Fix names, quantities and dates. Nothing reaches your pantry until you confirm it." },
  { id: "pantry", chapter: "Pantry", title: "A pantry that watches the dates.", text: "Every item shows how long it has left, so nothing gets forgotten at the back of the fridge." },
  { id: "recipes", chapter: "Recipes", title: "Search that understands food.", text: "Search “pasta” and find spaghetti. Filter by total time and by how much you already have." },
  { id: "ai", chapter: "AI ideas", title: "Three ideas for any craving.", text: "Ask for a dish or a taste. Only the pantry foods that belong in it are used, and the ideas stay until you clear them." },
  { id: "recipe", chapter: "Recipe", title: "Swap it, or shop it.", text: "Swap any ingredient, with what is already in your pantry first, or add what you need to your list in one tap." },
  { id: "shopping", chapter: "Shopping", title: "Lists that clear themselves.", text: "Tick things off in the shop. Finished lists disappear, or delete the whole list any time." },
  { id: "cooking", chapter: "Cooking", title: "Cook hands-free.", text: "Say “next step” or ask a question. The live waveform shows who is talking, you or Mimi." },
  { id: "impact", chapter: "Impact", title: "See the food you saved.", text: "Every ingredient cooked before it expires is counted, with an estimate of the food and CO₂e it saved." },
].filter((step) => captures[step.id]);

const STEP_MS = 5600;

export default function ExperienceWalkthrough({ onFinish, onTryIt }: { onFinish: () => void; onTryIt?: () => void }) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(() => !window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [elapsed, setElapsed] = useState(0);
  const [clicked, setClicked] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const finish = useRef(onFinish);
  finish.current = onFinish;
  const elapsedRef = useRef(0);
  const indexRef = useRef(0);
  indexRef.current = index;
  const step = steps[index] ?? { id: "", chapter: "", title: "", text: "" };
  const capture: Capture = captures[step.id] ?? { image: "", x: .5, y: .5, zoom: { x: .5, y: .5, scale: 1 } };
  const last = index === steps.length - 1;

  function go(next: number) {
    setIndex(Math.max(0, Math.min(steps.length - 1, next)));
    elapsedRef.current = 0;
    setElapsed(0);
  }
  const goRef = useRef(go);
  goRef.current = go;
  function tryIt() { (onTryIt || onFinish)(); }

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    // Focus the dialog itself (no ring on open); Tab reaches "Skip tutorial" first.
    root.current?.querySelector<HTMLElement>(".mmt")?.focus();
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function keys(event: KeyboardEvent) {
      if (event.key === "Escape") finish.current();
      if (event.key === "ArrowRight") goRef.current(indexRef.current + 1);
      if (event.key === "ArrowLeft") goRef.current(indexRef.current - 1);
      if (event.key === "Tab") {
        const targets = Array.from(root.current?.querySelectorAll<HTMLElement>('button:not(:disabled),a,[tabindex="0"]') || []);
        const first = targets[0], lastTarget = targets.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); lastTarget?.focus(); }
        if (!event.shiftKey && document.activeElement === lastTarget) { event.preventDefault(); first?.focus(); }
      }
    }
    document.addEventListener("keydown", keys);
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener("keydown", keys); previousFocus?.focus(); };
  }, []);

  // Story-style timer: the bar fills, then the tour moves on by itself.
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    let previous = performance.now();
    const tick = (now: number) => {
      elapsedRef.current += now - previous;
      previous = now;
      if (elapsedRef.current >= STEP_MS) {
        if (index < steps.length - 1) goRef.current(index + 1);
        else { setPlaying(false); setElapsed(STEP_MS); }
        return;
      }
      setElapsed(elapsedRef.current);
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, index]);

  // The banana glides to the feature, then "clicks" it.
  useEffect(() => {
    setClicked(false);
    const timer = window.setTimeout(() => setClicked(true), 1250);
    const next = steps[index + 1];
    if (next && captures[next.id]) { const image = new Image(); image.src = captures[next.id].image; }
    return () => window.clearTimeout(timer);
  }, [index]);

  const camera = {
    "--zoom-x": `${capture.zoom.x * 100}%`,
    "--zoom-y": `${capture.zoom.y * 100}%`,
    "--zoom-scale": capture.zoom.scale,
    "--step-ms": `${STEP_MS}ms`,
  } as CSSProperties;

  if (!steps.length) return null; // screens not captured yet (npm run capture:tour)
  return <div className="mmt-backdrop" ref={root}>
    <section className="mmt" role="dialog" aria-modal="true" aria-labelledby="mmt-title" tabIndex={-1}>
      <header className="mmt-header">
        <span className="mmt-brand"><i />MealMatch <small>Product tour · {steps.length} features in under a minute</small></span>
        <button className="mmt-skip" onClick={onFinish}>Skip tutorial <span aria-hidden="true">↗</span></button>
      </header>
      <div className="mmt-layout">
        <div className="mmt-screen-frame">
          <div className="mmt-window-bar" aria-hidden="true"><i /><i /><i /><span>mealmatch · {step.chapter.toLowerCase()}</span></div>
          <div className="mmt-screen">
            <div key={step.id} className="mmt-camera" style={camera}>
              <HotspotOverlay className="mmt-player" imageUrl={capture.image} zoom={100}
                hotspots={[{ id: step.id, xNorm: capture.x, yNorm: capture.y, dotSize: 22, dotColor: "#cbef72", dotStrokePx: 3, dotStrokeColor: "#0c3a35", animation: "breathe", tooltip: { title: last ? "Your turn" : "Next", description: last ? "Try it yourself" : "Click to continue" }, tooltipBgColor: "#0c3a35", tooltipTextColor: "#f0f7e9", tooltipOffsetXNorm: .03, tooltipOffsetYNorm: .05 }]}
                onHotspotClick={() => last ? tryIt() : go(index + 1)} />
              <span className={`mmt-cursor${clicked ? " clicked" : ""}`} aria-hidden="true" style={{ left: `${capture.x * 100}%`, top: `${capture.y * 100}%` }}><b>🍌</b><i /></span>
            </div>
          </div>
          <div className="mmt-screen-footer"><span>Sample kitchen · real MealMatch screens</span><a href="https://github.com/Propels-AI/Propels" target="_blank" rel="noreferrer">Hotspots by Propels ↗</a></div>
        </div>
        <aside className="mmt-copy" aria-live="polite">
          <div className="mmt-stories" role="tablist" aria-label="Tour chapters">
            {steps.map((item, i) => <button key={item.id} role="tab" aria-selected={i === index} aria-label={`${i + 1}. ${item.chapter}`} onClick={() => go(i)}><i style={{ transform: `scaleX(${i < index ? 1 : i === index ? Math.min(1, elapsed / STEP_MS) : 0})` }} /></button>)}
          </div>
          <p className="mmt-count">{String(index + 1).padStart(2, "0")} / {String(steps.length).padStart(2, "0")} · {step.chapter}</p>
          <h1 id="mmt-title" key={`title-${step.id}`}>{step.title}</h1>
          <p className="mmt-text" key={`text-${step.id}`}>{step.text}</p>
          <div className="mmt-controls">
            <button disabled={index === 0} onClick={() => go(index - 1)}>← Back</button>
            <button onClick={() => setPlaying(!playing)} aria-pressed={!playing}>{playing ? "Pause" : "Play"}</button>
          </div>
          <button className="mmt-next" onClick={() => last ? tryIt() : go(index + 1)}>{last ? "Try it yourself" : "Next"} <span aria-hidden="true">→</span></button>
        </aside>
      </div>
    </section>
  </div>;
}
