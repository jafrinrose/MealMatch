import { useEffect, useRef, useState } from "react";
import { INTRO_IMAGES, preloadIntro, startFridgeIntro } from "./fridgeIntroEngine";
import "./fridge-intro.css";

/** Each word in its own span, so captions can land one word at a time. */
function Words({ text }: { text: string }) {
  return <>{text.split(/(\s+)/).filter(Boolean).map((part, index) => /^\s+$/.test(part) ? part : <span className="fi-word" key={index}>{part}</span>)}</>;
}

/**
 * The landing film: scroll to open the fridge. "Open my kitchen" calls onEnter;
 * once the app sets leaving, the film holds its last frame and fades out, then
 * calls onGone so it can be removed.
 */
export default function FridgeIntro({ leaving, onEnter, onGone }: { leaving: boolean; onEnter: () => void; onGone: () => void }) {
  const root = useRef<HTMLDivElement>(null);
  const handle = useRef<ReturnType<typeof startFridgeIntro> | null>(null);
  const callbacks = useRef({ onEnter, onGone });
  callbacks.current = { onEnter, onGone };
  const [loaded, setLoaded] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void preloadIntro((ratio) => { if (!cancelled) setLoaded(ratio); })
      // Decode the film's own images before it starts, so none is first decoded mid-scroll (a dropped frame).
      .then(() => Promise.all(Array.from(root.current?.querySelectorAll("img") || []).map((image) => image.decode().catch(() => undefined))))
      .then(() => {
        if (cancelled || !root.current) return;
        handle.current = startFridgeIntro(root.current, { onEnter: () => callbacks.current.onEnter() });
      });
    return () => {
      cancelled = true;
      handle.current?.destroy();
      handle.current = null;
    };
  }, []);

  useEffect(() => {
    if (!leaving) return;
    if (handle.current) handle.current.leave();
    else root.current?.classList.add("is-leaving");
    const timer = window.setTimeout(() => callbacks.current.onGone(), 800);
    return () => window.clearTimeout(timer);
  }, [leaving]);

  return (
    <div className="fi" ref={root}>
      <div className="fi-preloader" role="status" aria-label="Loading the MealMatch intro">
        <div className="fi-preloader-track"><span style={{ transform: `scaleX(${loaded.toFixed(3)})` }} /></div>
        <span className="fi-preloader-count">{Math.round(loaded * 100)}%</span>
      </div>
      <div data-fi="experience" className="fi-experience">
        <section data-fi="stage" className="fi-stage" aria-label="MealMatch introduction">
          <div data-fi="camera" className="fi-camera">
            <div data-fi="kitchen" className="fi-scene fi-kitchen">
              <img data-fi="kitchen-bg" className="fi-cover fi-kitchen-bg" src={INTRO_IMAGES.kitchenBg} alt="A dark modern kitchen at night" />
              <img data-fi="kitchen-bg-blur" className="fi-cover fi-kitchen-bg-blur" src={INTRO_IMAGES.kitchenBgBlur} alt="" aria-hidden="true" />
              <div data-fi="floor-light" className="fi-floor-light" />
              <div data-fi="rays" className="fi-rays" />
              <div data-fi="light-wash" className="fi-light-wash" />
              <div data-fi="flare" className="fi-flare" />
              <div data-fi="fridge-camera" className="fi-fridge-camera">
                <div className="fi-fridge">
                  <div data-fi="fridge-bloom" className="fi-fridge-bloom" />
                  <img data-fi="fridge-open" className="fi-fridge-interior" src={INTRO_IMAGES.fridgeOpen} alt="An open refrigerator filled with fresh ingredients" />
                  <div data-fi="door" className="fi-door">
                    <div className="fi-door-face fi-door-face--front"><img data-fi="fridge-door" src={INTRO_IMAGES.fridgeDoor} alt="A closed graphite refrigerator" /><div data-fi="door-sheen" className="fi-door-sheen" /></div>
                    <div className="fi-door-face fi-door-face--back"><img data-fi="fridge-door-inside" src={INTRO_IMAGES.fridgeDoorInside} alt="The inside of a refrigerator door" /></div>
                    <div className="fi-door-edge" />
                  </div>
                  <div data-fi="door-seam" className="fi-door-seam" />
                </div>
              </div>
            </div>
            <img data-fi="zoom-plate" className="fi-zoom-plate" src={INTRO_IMAGES.fridgeZoomPlate} alt="Fresh ingredients on a refrigerator shelf" />
            <div data-fi="void" className="fi-scene fi-void" aria-hidden="true">
              <div className="fi-fog fi-fog--a" />
              <div className="fi-fog fi-fog--b" />
              <div data-fi="ingredients" className="fi-ingredients" />
            </div>
            <div data-fi="table" className="fi-scene fi-table">
              <img data-fi="table-bg" className="fi-cover fi-table-bg" src={INTRO_IMAGES.tableBg} alt="An intimate candlelit dinner table" />
              <div data-fi="dish-glow" className="fi-dish-glow" />
              <div data-fi="dish-wrap" className="fi-dish-wrap">
                <div data-fi="contact-shadow" className="fi-contact-shadow" />
                <img data-fi="dish" className="fi-dish" src={INTRO_IMAGES.heroDish} alt="Spaghetti pomodoro with burrata, basil and parmesan" />
                <div data-fi="dish-sheen" className="fi-dish-sheen" />
                <div data-fi="steam" className="fi-steam" aria-hidden="true"><i /><i /><i /></div>
              </div>
            </div>
          </div>

          <canvas data-fi="dust" className="fi-dust" aria-hidden="true" />
          <div data-fi="grade-cool" className="fi-grade fi-grade--cool" />
          <div data-fi="grade-warm" className="fi-grade fi-grade--warm" />
          <div data-fi="vignette" className="fi-vignette" />
          <div data-fi="scrim" className="fi-scrim" />
          <div data-fi="grain" className="fi-grain" aria-hidden="true" />
          <div className="fi-flash" aria-hidden="true">
            <div data-fi="flash-white" className="fi-flash-white" />
            <div data-fi="flash-orb" className="fi-flash-orb" />
            <div data-fi="flash-streak" className="fi-flash-streak" />
          </div>

          <div className="fi-captions" aria-live="polite">
            <article data-fi="caption-open" className="fi-caption">
              <p className="fi-eyebrow">A little kitchen magic</p>
              <h1><Words text="Open the " /><em><Words text="fridge." /></em></h1>
              <p className="fi-note">Scroll slowly.</p>
            </article>
            <article data-fi="caption-ready" className="fi-caption"><h2><Words text="Everything you need" /><br /><Words text="is already " /><em><Words text="here." /></em></h2></article>
            <article data-fi="caption-seen" className="fi-caption"><p className="fi-eyebrow">One photo</p><h2><Words text="Every ingredient," /><br /><em><Words text="seen." /></em></h2></article>
            <article data-fi="caption-waste" className="fi-caption"><h2><Words text="Nothing forgotten." /><br /><Words text="Nothing " /><em><Words text="wasted." /></em></h2></article>
            <article data-fi="caption-together" className="fi-caption"><h2><Words text="Good things" /><br /><Words text="come " /><em><Words text="together." /></em></h2></article>
          </div>

          <section data-fi="brand" className="fi-brand" aria-label="MealMatch">
            <p className="fi-brand-kicker">From pantry to plate</p>
            <h2>MealMatch<span>.</span></h2>
            <p className="fi-brand-tagline">Smarter fridge. Better meals.</p>
            <div className="fi-brand-actions">
              <button data-fi="enter" className="fi-button fi-button--primary" type="button">Open my kitchen <span aria-hidden="true">→</span></button>
              <button data-fi="replay" className="fi-button fi-button--ghost" type="button">Replay <span aria-hidden="true">↺</span></button>
            </div>
          </section>

          <div data-fi="letterbox-top" className="fi-letterbox fi-letterbox--top" />
          <div data-fi="letterbox-bottom" className="fi-letterbox fi-letterbox--bottom" />
          <header data-fi="topbar" className="fi-topbar">
            <button data-fi="mini-mark" className="fi-mini-mark" type="button" aria-label="Back to the start of the intro"><i /><span>MealMatch</span></button>
            <p data-fi="tagline">From pantry to plate</p>
            <div className="fi-topbar-actions">
              <button data-fi="sound" className="fi-text-button fi-sound" type="button" aria-pressed="false" aria-label="Turn sound on"><span className="fi-eq" aria-hidden="true"><i /><i /><i /></span><span data-fi="sound-label">Sound off</span></button>
              <button data-fi="skip" className="fi-text-button" type="button">Skip intro ↗</button>
            </div>
          </header>
          <footer data-fi="bottombar" className="fi-bottombar">
            <p data-fi="chapter" className="fi-chapter">01 — The fridge</p>
            <div data-fi="scroll-hint" className="fi-scroll-hint"><i /><span>Scroll</span></div>
          </footer>
          <div data-fi="progress" className="fi-progress"><i data-fi="progress-fill" /></div>
          <output data-fi="debug" className="fi-debug" aria-hidden="true" />
        </section>
      </div>
    </div>
  );
}
