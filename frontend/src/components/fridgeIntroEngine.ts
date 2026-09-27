/**
 * "Open the fridge": the scroll-driven landing film, ported from a standalone
 * prototype page into the app.
 *
 * Changes from the prototype (user testing, round 2):
 * - The push into the fridge is one camera move. The close-up photo of a shelf is
 *   laid exactly over the fridge's top shelf and scaled with the fridge, and fades
 *   in with soft edges while the camera closes in. Before, the fridge zoomed toward
 *   its middle while an unrelated photo cross-faded over it, which read as a cut.
 * - Large windows no longer drop frames: see fridge-intro.css for the lighter
 *   layers; here the dust canvas is capped at about a million pixels, the room's
 *   focus pull crossfades a pre-blurred photo, and the camera drift is a translation.
 * - The finished dish is centred between the top bar and the MealMatch title.
 * - Scrolling is smoothed here instead of by Lenis, so wheel steps still glide.
 */
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import basilLeaf from "../assets/intro/basil-leaf.webp";
import basilSprig from "../assets/intro/basil-sprig.webp";
import burrata from "../assets/intro/burrata.webp";
import cherryTomato from "../assets/intro/cherry-tomato.webp";
import fridgeDoorInside from "../assets/intro/fridge-door-inside.webp";
import fridgeDoor from "../assets/intro/fridge-door.webp";
import fridgeOpen from "../assets/intro/fridge-open.webp";
import fridgeZoomPlate from "../assets/intro/fridge-zoom-plate.webp";
import garlic from "../assets/intro/garlic.webp";
import heroDish from "../assets/intro/hero-dish.webp";
import kitchenBgBlur from "../assets/intro/kitchen-bg-blur.webp";
import kitchenBg from "../assets/intro/kitchen-bg.webp";
import lemonHalf from "../assets/intro/lemon-half.webp";
import parmesan from "../assets/intro/parmesan.webp";
import redChili from "../assets/intro/red-chili.webp";
import spaghetti from "../assets/intro/spaghetti.webp";
import tableBg from "../assets/intro/table-bg.webp";
import tomatoVine from "../assets/intro/tomato-vine.webp";

gsap.registerPlugin(ScrollTrigger);

export const INTRO_IMAGES = {
  kitchenBg, kitchenBgBlur, fridgeOpen, fridgeDoor, fridgeDoorInside, fridgeZoomPlate, heroDish, tableBg,
};
const INGREDIENT_IMAGES: Record<string, string> = {
  "tomato-vine": tomatoVine, "cherry-tomato": cherryTomato, "basil-sprig": basilSprig, "basil-leaf": basilLeaf,
  garlic, "red-chili": redChili, burrata, parmesan, spaghetti, "lemon-half": lemonHalf,
};

const C = {
  scrollScreens: { desktop: 8, phone: 7 },
  // Seconds for the film to catch up with the scroll position (smooths mouse-wheel steps).
  smoothing: .14,
  barsInMs: 1500,
  doorCrack: [0.085, 0.12],
  doorSwing: [0.12, 0.31],
  pushIn: [0.27, 0.455],
  flashIn: [0.37, 0.44],
  flashCut: 0.455,
  flashOut: [0.465, 0.53],
  flythrough: [0.44, 0.78],
  swirl: [0.70, 0.86],
  tableIn: [0.70, 0.86],
  dishFocus: [0.76, 0.86],
  steam: [0.84, 0.93],
  final: [0.89, 1],
  brand: [0.90, 0.99],
  captions: { open: [0, 0.10], ready: [0.16, 0.33], seen: [0.49, 0.64], waste: [0.63, 0.75], together: [0.77, 0.90] },
  doorMaxDeg: 112,
  fridgeStartScale: 1.05,
  cameraZ: [0, 2600],
  dustCount: 170,
  dustMaxPixels: 1_100_000,
  ingredientStagger: 0.0028,
  ingredientSwirlDuration: 0.10,
  sounds: { pop: 0.087, flash: 0.44, land: 0.80, chime: 0.925 } as Record<string, number>,
} as const;

// Where the close-up photo sits in fridge-open.webp: the top shelf, framed 3:2 like the photo.
const SHELF = { x: .314, y: .098, w: .372, h: .165 };

type Range = readonly [number, number];
type Handle = { leave: () => void; destroy: () => void };

function clamp(value: number, min: number, max: number) { return Math.max(min, Math.min(max, value)); }
function lerp(a: number, b: number, t: number) { return a + (b - a) * t; }
function range(p: number, a: number, b: number) { return clamp((p - a) / (b - a), 0, 1); }
function smoothstep(a: number, b: number, p: number) { const t = range(p, a, b); return t * t * (3 - 2 * t); }
function easeIn(t: number) { return t * t * t; }
function easeOut(t: number) { return 1 - Math.pow(1 - t, 3); }
function easeInOut(t: number) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
function easeInOutSine(t: number) { return (1 - Math.cos(Math.PI * t)) / 2; }
function qBlur(value: number) { return Math.round(value * 4) / 4; }

export function preloadIntro(onProgress: (ratio: number) => void): Promise<void> {
  const sources = [...Object.values(INTRO_IMAGES), ...Object.values(INGREDIENT_IMAGES)];
  let done = 0;
  const total = sources.length + 1;
  const finish = () => { done += 1; onProgress(done / total); };
  const images = sources.map((src) => new Promise<void>((resolve) => {
    const image = new Image();
    image.decoding = "async";
    image.onload = image.onerror = () => { finish(); resolve(); };
    image.src = src;
  }));
  const fonts = document.fonts?.load ? Promise.all([document.fonts.load('400 1em "MM Intro Serif"'), document.fonts.load('italic 400 1em "MM Intro Serif"')]).catch(() => undefined) : Promise.resolve();
  return Promise.all([...images, fonts.then(finish)]).then(() => undefined);
}

export function startFridgeIntro(root: HTMLElement, { onEnter }: { onEnter: () => void }): Handle {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const query = new URLSearchParams(window.location.search);
  const frozenValue = query.has("introP") ? clamp(Number(query.get("introP")) || 0, 0, 1) : null;
  const debugEnabled = query.get("introDebug") === "1";
  const styleCache = new WeakMap<Element, Record<string, string>>();
  const q = <T extends HTMLElement = HTMLElement>(name: string) => root.querySelector<T>(`[data-fi="${name}"]`)!;
  const els = {
    stage: q("stage"), experience: q("experience"), camera: q("camera"), kitchenScene: q("kitchen"), kitchenBg: q("kitchen-bg"), kitchenBgBlur: q("kitchen-bg-blur"),
    floorLight: q("floor-light"), rays: q("rays"), lightWash: q("light-wash"), flare: q("flare"),
    fridgeCamera: q("fridge-camera"), fridgeOpen: q("fridge-open"), fridgeDoor: q("fridge-door"), fridgeDoorInside: q("fridge-door-inside"),
    door: q("door"), doorSeam: q("door-seam"), doorSheen: q("door-sheen"), fridgeBloom: q("fridge-bloom"), zoomPlate: q("zoom-plate"),
    voidScene: q("void"), ingredientField: q("ingredients"), tableScene: q("table"), tableBg: q("table-bg"),
    dishWrap: q("dish-wrap"), dish: q("dish"), dishGlow: q("dish-glow"), dishSheen: q("dish-sheen"), contactShadow: q("contact-shadow"), steam: q("steam"),
    flashWhite: q("flash-white"), flashOrb: q("flash-orb"), flashStreak: q("flash-streak"),
    coolGrade: q("grade-cool"), warmGrade: q("grade-warm"), dust: q<HTMLCanvasElement>("dust"), vignette: q("vignette"), scrim: q("scrim"), grain: q("grain"),
    brand: q("brand"), topBox: q("letterbox-top"), bottomBox: q("letterbox-bottom"), topbar: q("topbar"),
    progress: q("progress-fill"), progressRail: q("progress"), miniMark: q("mini-mark"), topTagline: q("tagline"), skip: q("skip"), bottombar: q("bottombar"),
    soundButton: q("sound"), soundLabel: q("sound-label"), scrollHint: q("scroll-hint"), chapter: q("chapter"), debug: q("debug"),
    enter: q("enter"), replay: q("replay"),
  };

  function style(el: HTMLElement | null, property: string, value: string) {
    if (!el) return;
    let cache = styleCache.get(el);
    if (!cache) { cache = {}; styleCache.set(el, cache); }
    if (cache[property] !== value) { el.style.setProperty(property, value); cache[property] = value; }
  }
  const opacity = (el: HTMLElement, value: number) => style(el, "opacity", clamp(value, 0, 1).toFixed(3));
  const transform = (el: HTMLElement, value: string) => style(el, "transform", value);
  const filter = (el: HTMLElement, value: string) => style(el, "filter", value);
  const visible = (el: HTMLElement, value: boolean) => style(el, "visibility", value ? "visible" : "hidden");

  let readyAt = performance.now();
  let lastNow = performance.now();
  let targetProgress = frozenValue ?? 0;
  let currentProgress = targetProgress;
  let currentLight = 0;
  let currentCamZ = 0;
  let previousCamZ = 0;
  let camSpeed = 0;
  let previousCamPos = 0;
  let dustSpeed = 0;
  let flickerStart = -1;
  let flickerArmed = true;
  let trigger: ScrollTrigger | null = null;
  let leaving = false;
  let frames = 0;
  let fps = 60;
  let fpsStamp = performance.now();

  // [image, x, y, depth, size, rotation]. The first ten rush past the camera; the last twelve
  // sit in a loose ring ahead so they are still in frame when they swirl into the dish.
  const LAYOUT: [string, number, number, number, number, number][] = [
    ["tomato-vine", -.44, -.23, 700, .92, -18], ["basil-leaf", .40, .26, 880, .72, 24],
    ["garlic", -.38, .36, 1080, .64, -12], ["red-chili", .47, -.34, 1280, .86, 38],
    ["parmesan", -.49, .06, 1510, .78, -28], ["cherry-tomato", .39, .43, 1680, .58, 7],
    ["spaghetti", -.42, -.41, 1880, .98, 32], ["basil-sprig", .45, .03, 2030, .80, -31],
    ["lemon-half", -.37, .47, 2210, .67, 16], ["burrata", .38, -.46, 2390, .78, -8],
    ["cherry-tomato", -.40, -.20, 2820, .62, -12], ["basil-leaf", .30, -.32, 3480, .66, 22],
    ["garlic", -.30, .30, 3000, .60, 12], ["red-chili", .44, .14, 3880, .76, -36],
    ["tomato-vine", .40, -.12, 3160, .72, 19], ["parmesan", -.46, .06, 4230, .66, -15],
    ["basil-sprig", -.12, -.38, 2920, .70, 33], ["lemon-half", .16, .36, 3640, .58, -20],
    ["spaghetti", -.36, -.02, 3320, .78, 44], ["burrata", .26, .30, 3060, .65, -7],
    ["cherry-tomato", .06, .40, 4080, .54, 13], ["basil-leaf", -.20, .42, 3760, .58, -24],
  ];
  els.ingredientField.replaceChildren();
  const ingredients = LAYOUT.map(([name, x, y, z, size, rot], index) => {
    const img = document.createElement("img");
    img.className = "fi-ingredient";
    img.alt = "";
    img.setAttribute("aria-hidden", "true");
    img.decoding = "async";
    img.src = INGREDIENT_IMAGES[name];
    els.ingredientField.appendChild(img);
    void img.decode().catch(() => undefined); // decoded now, not when it first flies past

    return { el: img, x, y, z, size, rot, index };
  });

  // Captions land word by word; FridgeIntro renders each word as a .fi-word span.
  const captions = ([["caption-open", C.captions.open, true], ["caption-ready", C.captions.ready], ["caption-seen", C.captions.seen], ["caption-waste", C.captions.waste], ["caption-together", C.captions.together]] as [string, Range, boolean?][])
    .map(([name, [start, end], opening]) => {
      const el = q(name);
      return {
        el, start, end, opening: Boolean(opening),
        words: Array.from(el.querySelectorAll<HTMLElement>(".fi-word")),
        extras: Array.from(el.querySelectorAll<HTMLElement>(".fi-eyebrow, .fi-note")),
      };
    });
  const brandParts = Array.from(els.brand.children) as HTMLElement[];

  // Layout, measured once per resize (the camera maths below uses it every frame).
  const L = { W: 0, H: 0, bx: 0, by: 0, origin: { x: 0, y: 0 }, shelf: { x: 0, y: 0, w: 1, h: 1 }, target: { x: 0, y: 0 }, cover: 9, dishRise: 0, dishFinalScale: .76 };
  function measure() {
    const phone = window.innerWidth < 700;
    L.W = els.stage.clientWidth;
    L.H = els.stage.clientHeight;
    const camera = els.fridgeCamera;
    const w = camera.offsetWidth, h = camera.offsetHeight;
    L.bx = camera.offsetLeft;
    L.by = camera.offsetTop;
    L.origin = { x: L.bx + .5 * w, y: L.by + .42 * h };
    L.shelf = { x: L.bx + SHELF.x * w, y: L.by + SHELF.y * h, w: SHELF.w * w, h: SHELF.h * h };
    L.target = { x: L.shelf.x + L.shelf.w / 2, y: L.shelf.y + L.shelf.h / 2 };
    L.cover = Math.max(L.W / L.shelf.w, L.H / L.shelf.h) * 1.03;
    // The close-up is laid out at full-screen size (so it stays sharp) and scaled down to the shelf.
    style(els.zoomPlate, "width", `${(L.shelf.w * L.cover).toFixed(1)}px`);
    style(els.zoomPlate, "height", `${(L.shelf.h * L.cover).toFixed(1)}px`);
    root.style.setProperty("--fi-door-t", `${(w * .04).toFixed(2)}px`);

    // The finished dish sits centred between the top bar and the MealMatch title.
    const wrapSize = els.dishWrap.offsetHeight;
    const top = els.topbar.offsetHeight * .7;
    const bottom = els.brand.offsetTop - 12;
    const visibleHeight = wrapSize * .745; // the bowl fills 74.5% of hero-dish.webp's height, centred
    L.dishFinalScale = Math.min(phone ? .68 : .76, Math.max(.3, (bottom - top) * .94 / visibleHeight));
    L.dishRise = els.dishWrap.offsetTop - (top + bottom) / 2;
  }

  function captionFrame(c: typeof captions[number], p: number, now: number) {
    const enter = c.opening ? easeOut(clamp((now - readyAt - 500) / 1700, 0, 1)) : smoothstep(c.start, c.start + 0.05, p);
    const exit = smoothstep(c.end - 0.045, c.end, p);
    const shown = enter > 0.001 && exit < 0.999;
    visible(c.el, shown);
    if (!shown) return;
    opacity(c.el, 1 - exit);
    transform(c.el, `translate3d(0,${(-exit * 16).toFixed(2)}px,0)`);
    filter(c.el, `blur(${qBlur(exit * 9)}px)`);
    c.extras.forEach((el) => opacity(el, enter));
    const n = c.words.length;
    const step = Math.min(0.16, 0.55 / Math.max(1, n - 1));
    c.words.forEach((word, i) => {
      const t = easeOut(clamp((enter - i * step) / Math.max(0.2, 1 - (n - 1) * step), 0, 1));
      opacity(word, t);
      transform(word, `translate3d(0,${((1 - t) * 0.42).toFixed(3)}em,0)`);
      filter(word, `blur(${qBlur((1 - t) * 8)}px)`);
    });
  }

  function flickerLevel(now: number, p: number) {
    if (reduced) return p >= C.doorCrack[0] ? 1 : 0;
    if (p < C.doorCrack[0] - 0.004) { flickerArmed = true; flickerStart = -1; return 0; }
    if (flickerArmed && p >= C.doorCrack[0]) { flickerArmed = false; flickerStart = now; }
    if (p >= C.doorSwing[0] || flickerStart < 0) return p >= C.doorSwing[0] ? 1 : 0;
    const elapsed = now - flickerStart;
    if (elapsed < 70) return 1;
    if (elapsed < 135) return 0.04;
    if (elapsed < 235) return 0.88;
    if (elapsed < 315) return 0.28;
    return 1;
  }

  function updateIngredients(p: number, now: number, sceneAlpha: number) {
    const width = window.innerWidth;
    const height = window.innerHeight;
    const unit = Math.min(width, height);
    const uy = width < 700 ? height * 0.82 : unit;
    const cx = width / 2;
    const cy = height * (width < 700 ? 0.44 : 0.5);
    const dishY = height * (width < 700 ? 0.48 : 0.57);
    const time = now * 0.001;
    ingredients.forEach((item) => {
      const d = item.z - currentCamZ;
      let k = 800 / Math.max(1, d);
      let screenX: number, screenY: number, scale: number, blur: number;
      if (reduced) {
        k = 0.45;
        screenX = cx + item.x * unit * 0.72;
        screenY = cy + item.y * uy * 0.58;
        scale = item.size * (width < 700 ? .92 : .7);
        blur = 0;
      } else {
        screenX = cx + item.x * unit * k;
        screenY = cy + item.y * uy * k + Math.sin(time * .75 + item.index * 1.71) * 6;
        scale = k * item.size;
        // Lens depth of field plus a little motion blur for whatever is rushing past.
        let screenBlur = Math.min(26, Math.abs(1 / Math.max(d, 1) - 1 / 820) * 3.6 * unit);
        screenBlur += Math.min(14, camSpeed / 1000 * k * 2.6);
        blur = screenBlur / Math.max(scale, .12);
      }
      const swirlStart = C.swirl[0] + item.index * C.ingredientStagger;
      const swirl = easeInOut(range(p, swirlStart, swirlStart + C.ingredientSwirlDuration));
      const dx = screenX - cx;
      const dy = screenY - dishY;
      const turn = (item.index % 2 ? 1 : -1) * 1.4 * swirl;
      const radius = Math.pow(1 - swirl, 1.3);
      const cos = Math.cos(turn), sin = Math.sin(turn);
      screenX = cx + (dx * cos - dy * sin) * radius;
      screenY = dishY + (dx * sin + dy * cos) * radius;
      scale *= lerp(1, .15, swirl);
      blur *= 1 - swirl * .82;
      const fog = smoothstep(1500, 3300, d);
      const nearFade = smoothstep(45, 240, d);
      let alpha = sceneAlpha * nearFade * (1 - fog) * (1 - smoothstep(.72, 1, swirl));
      if (reduced) alpha = sceneAlpha * (1 - smoothstep(.72, 1, swirl)) * lerp(.72, 1, 1 - fog);
      const offscreen = screenX < -unit || screenX > width + unit || screenY < -unit || screenY > height + unit;
      const hide = !reduced && (d < 45 || scale > 7 || offscreen);
      alpha = hide ? 0 : alpha;
      visible(item.el, alpha > .003);
      if (alpha <= .003) return;
      const rotation = item.rot + Math.sin(time * .33 + item.index) * 5 + swirl * 180;
      transform(item.el, `translate3d(${screenX.toFixed(2)}px,${screenY.toFixed(2)}px,0) translate(-50%,-50%) scale(${Math.max(0, scale).toFixed(4)}) rotate(${rotation.toFixed(2)}deg)`);
      filter(item.el, `blur(${qBlur(blur)}px) brightness(${(1 - .5 * fog).toFixed(3)})`);
      opacity(item.el, alpha);
      style(item.el, "z-index", String(Math.max(1, 5000 - Math.round(d))));
    });
  }

  // Dust motes: float in the fridge beam, rush past in the void, drift up in candlelight.
  const dustCtx = els.dust.getContext("2d", { alpha: true })!;
  type Mote = { x: number; y: number; z: number; r: number; phase: number; px: number | null; py: number | null };
  const dust: Mote[] = [];
  let dustSize = { w: 0, h: 0, scale: 1 };
  let seed = 9157;
  const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  function spawnMote(m: Mote, anyDepth: boolean) {
    m.x = lerp(-1.2, 1.2, random()); m.y = lerp(-1, 1, random());
    m.z = anyDepth ? lerp(.06, 1, random()) : lerp(.85, 1, random());
    m.r = lerp(.5, 1.6, random()); m.phase = random() * Math.PI * 2; m.px = null; m.py = null;
    return m;
  }
  for (let i = 0; i < C.dustCount; i += 1) dust.push(spawnMote({ x: 0, y: 0, z: 0, r: 0, phase: 0, px: null, py: null }, true));
  const spriteCache: Record<string, HTMLCanvasElement> = {};
  function moteSprite(warmStep: number) {
    if (spriteCache[warmStep]) return spriteCache[warmStep];
    const sprite = document.createElement("canvas");
    sprite.width = sprite.height = 64;
    const g = sprite.getContext("2d")!;
    const r = Math.round(lerp(206, 255, warmStep)), gr = Math.round(lerp(234, 200, warmStep)), b = Math.round(lerp(255, 138, warmStep));
    const gradient = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    gradient.addColorStop(0, "rgba(255,255,255,1)");
    gradient.addColorStop(.25, `rgba(${r},${gr},${b},.75)`);
    gradient.addColorStop(1, `rgba(${r},${gr},${b},0)`);
    g.fillStyle = gradient;
    g.fillRect(0, 0, 64, 64);
    spriteCache[warmStep] = sprite;
    return sprite;
  }
  function resizeCanvas() {
    const w = window.innerWidth, h = window.innerHeight;
    // Soft glowing dots need no retina resolution: cap the canvas instead of redrawing 8 million pixels a frame.
    const scale = Math.min(window.devicePixelRatio || 1, Math.sqrt(C.dustMaxPixels / (w * h)));
    if (w === dustSize.w && h === dustSize.h && scale === dustSize.scale) return;
    dustSize = { w, h, scale };
    els.dust.width = Math.round(w * scale); els.dust.height = Math.round(h * scale);
    dustCtx.setTransform(scale, 0, 0, scale, 0, 0);
  }
  function drawDust(now: number, dt: number, level: number, warm: number, speed: number, beam: number) {
    if (reduced || level < .01) { opacity(els.dust, 0); visible(els.dust, false); return; }
    visible(els.dust, true);
    dustCtx.clearRect(0, 0, dustSize.w, dustSize.h);
    opacity(els.dust, 1);
    const w = dustSize.w, h = dustSize.h;
    const cx = w / 2, cy = h * .46, spread = Math.max(w, h) * .5;
    const beamWidth = Math.min(w, h * .9) * .34;
    const sprite = moteSprite(Math.round(warm * 8) / 8);
    const r = Math.round(lerp(206, 255, warm)), g = Math.round(lerp(234, 200, warm)), b = Math.round(lerp(255, 138, warm));
    dustCtx.globalCompositeOperation = "lighter";
    dustCtx.lineCap = "round";
    dust.forEach((m) => {
      m.z -= (.014 + speed) * dt;
      m.x += Math.sin(now * .0003 + m.phase) * .012 * dt;
      m.y -= (.006 + warm * .02) * dt;
      if (m.z < .05 || m.y < -1.4) { spawnMote(m, false); return; }
      const k = .34 / m.z;
      const sx = cx + m.x * spread * k, sy = cy + m.y * spread * k;
      if (sx < -60 || sx > w + 60 || sy < -60 || sy > h + 60) { m.px = null; return; }
      const size = clamp(m.r * k * 2.4, 1.2, 28);
      let a = level * (.22 + .78 * (1 - m.z)) * (.55 + .45 * Math.sin(now * .0011 + m.phase * 3)) * smoothstep(.05, .16, m.z);
      if (beam > 0) { const bx = (sx - cx) / beamWidth; a *= lerp(1, Math.exp(-bx * bx), beam); }
      if (a < .004) { m.px = sx; m.py = sy; return; }
      if (speed > .12 && m.px !== null && m.py !== null) {
        dustCtx.strokeStyle = `rgba(${r},${g},${b},${Math.min(1, a * .9).toFixed(3)})`;
        dustCtx.lineWidth = Math.max(1, size * .22);
        dustCtx.beginPath(); dustCtx.moveTo(m.px, m.py); dustCtx.lineTo(sx, sy); dustCtx.stroke();
      }
      dustCtx.globalAlpha = Math.min(1, a);
      dustCtx.drawImage(sprite, sx - size / 2, sy - size / 2, size, size);
      dustCtx.globalAlpha = 1;
      m.px = sx; m.py = sy;
    });
  }

  const sound = createSound();
  const cueArmed: Record<string, boolean> = { pop: true, flash: true, land: true, chime: true };
  function updateCues(p: number) {
    Object.entries(C.sounds).forEach(([name, at]) => {
      if (cueArmed[name] && p >= at) { cueArmed[name] = false; sound.cue(name); }
      if (p < at - .01) cueArmed[name] = true;
    });
  }

  function updateChapter(p: number) {
    const text = p < .12 ? "01 — The fridge" : p < .455 ? "02 — The light" : p < .70 ? "03 — Every ingredient" : p < .89 ? "04 — Together" : "05 — MealMatch";
    if (els.chapter.textContent !== text) els.chapter.textContent = text;
  }

  function render(now: number) {
    const dt = clamp((now - lastNow) / 1000, 0.001, 0.05);
    lastNow = now;
    if (frozenValue === null) {
      currentProgress += (targetProgress - currentProgress) * (1 - Math.exp(-dt / C.smoothing));
      if (Math.abs(targetProgress - currentProgress) < .00003) currentProgress = targetProgress;
    }
    const p = frozenValue ?? currentProgress;
    const phone = window.innerWidth < 700;
    const crack = smoothstep(C.doorCrack[0], C.doorCrack[1], p);
    const swing = easeInOut(range(p, C.doorSwing[0], C.doorSwing[1]));
    const angle = 7 * crack + (C.doorMaxDeg - 7) * swing;
    const pushT = range(p, C.pushIn[0], C.pushIn[1]);
    const push = easeIn(pushT);
    const flashUp = easeIn(range(p, C.flashIn[0], C.flashIn[1]));
    const flashRelease = easeOut(range(p, C.flashOut[0], C.flashOut[1]));
    const flash = p < C.flashOut[0] ? flashUp : 1 - flashRelease;
    const cut = p >= C.flashCut;
    const voidAlpha = cut ? 1 - smoothstep(.76, .87, p) : 0;
    const tableAlpha = smoothstep(C.tableIn[0], C.tableIn[1], p);
    const warm = smoothstep(.70, .86, p);
    const focus = smoothstep(C.dishFocus[0], C.dishFocus[1], p);
    const final = smoothstep(C.final[0], C.final[1], p);
    const brand = range(p, C.brand[0], C.brand[1]);
    const truck = range(p, .72, 1);
    currentLight = flickerLevel(now, p);

    // A handheld drift. Translation only: rotating the whole camera re-sampled every layer each frame.
    const driftX = reduced ? 0 : Math.sin(now * .00031) * 1.7 + Math.sin(now * .00079) * .45;
    const driftY = reduced ? 0 : Math.cos(now * .00027) * 1.4;
    transform(els.camera, `translate3d(${driftX.toFixed(2)}px,${driftY.toFixed(2)}px,0)`);

    // The push-in: one camera that scales about the top shelf and brings it to the centre of the screen.
    const s0 = C.fridgeStartScale;
    const scale = Math.exp(lerp(Math.log(s0), Math.log(L.cover * 1.35), easeInOutSine(pushT)));
    const toCover = clamp(Math.log(scale / s0) / Math.log(L.cover / s0), 0, 1);
    const centring = smoothstep(0, 1, toCover);
    const startX = L.origin.x + s0 * (L.target.x - L.origin.x);
    const startY = L.origin.y + s0 * (L.target.y - L.origin.y);
    const focusX = lerp(startX, L.W / 2, centring);
    const focusY = lerp(startY, L.H / 2, centring);
    const plateBlend = smoothstep(Math.log(1.6), Math.log(Math.max(2.5, Math.min(4.5, L.cover * .5))), Math.log(scale));
    // 1 when the close-up just fills the screen; its soft edge fades out while it grows past that.
    const plateFill = scale * 1.03 / L.cover;
    const edgeGone = smoothstep(1, 1.2, plateFill);
    const covered = plateBlend >= 1 && edgeGone >= 1;
    // A little motion blur while the two photos dissolve (strongest halfway), as a fast push-in would
    // have. It hides where the close-up and the fridge photo differ, most visible on narrow screens.
    const dissolveBlur = Math.sin(Math.PI * plateBlend) * (phone ? 7 : 5);

    // Scene 1: kitchen, door and the light.
    const kitchenOn = !cut && !covered;
    visible(els.kitchenScene, kitchenOn);
    if (kitchenOn) {
      const backgroundScale = 1 + (Math.min(scale, 5.6) - 1) * .18;
      const roomBlur = smoothstep(0, .12, p) * 1.6 + push * 8;
      const roomFilter = `brightness(${lerp(.52, .82, currentLight).toFixed(3)}) saturate(${lerp(.85, .72, currentLight).toFixed(3)})`;
      // Focus pull: the room softens as the camera locks onto the fridge (a pre-blurred photo fades in).
      // Only the layers that show are drawn: the sharp room goes once the blurred one covers it.
      const blurred = clamp(roomBlur / 8, 0, 1);
      visible(els.kitchenBg, blurred < 1);
      transform(els.kitchenBg, `scale(${backgroundScale.toFixed(3)})`);
      filter(els.kitchenBg, roomFilter);
      visible(els.kitchenBgBlur, blurred > 0);
      transform(els.kitchenBgBlur, `scale(${(2 * backgroundScale).toFixed(3)})`);
      filter(els.kitchenBgBlur, roomFilter);
      opacity(els.kitchenBgBlur, blurred);

      transform(els.fridgeCamera, `translate3d(${(focusX + scale * (L.bx - L.target.x) - L.bx).toFixed(2)}px,${(focusY + scale * (L.by - L.target.y) - L.by).toFixed(2)}px,0) scale(${scale.toFixed(4)})`);
      transform(els.door, `rotateY(${(-angle).toFixed(3)}deg)`);
      const frontShade = 1 - .55 * Math.sin(Math.min(90, angle) * Math.PI / 180);
      // Graphite: the generated door is silver, so it is toned down here rather than regenerated.
      filter(els.fridgeDoor, `brightness(${(frontShade * .68).toFixed(3)}) contrast(1.14) saturate(.5)`);
      filter(els.fridgeDoorInside, `brightness(${lerp(.45, 1.08, currentLight).toFixed(3)})`);
      // The blur is always in the filter list (often 0px): adding it mid-scroll made the browser rebuild the layer.
      filter(els.fridgeOpen, `brightness(${(.14 + currentLight * .92 + push * .12).toFixed(3)}) saturate(${lerp(.75, 1.03, currentLight).toFixed(3)}) blur(${qBlur(dissolveBlur / scale)}px)`);
      opacity(els.fridgeBloom, currentLight * .8);

      // A slow glint crosses the steel before the first scroll, then the reflection slides with the swing.
      const idle = 118 - ((now / 5200) % 1) * 170;
      const sheenPos = lerp(idle, lerp(96, -40, range(p, .02, .24)), smoothstep(0, .03, p));
      style(els.doorSheen, "background-position", `${sheenPos.toFixed(2)}% 0`);
      opacity(els.doorSheen, lerp(.55, .9, smoothstep(0, .03, p)) * (1 - smoothstep(.16, .26, p)));
      const pulse = .5 + .5 * Math.sin(now * .0023);
      opacity(els.doorSeam, Math.max(lerp(.35, .8, pulse) * (1 - crack), crack * currentLight * (1 - swing) * 1.2));

      const wash = currentLight * smoothstep(.09, .23, p) * (1 - smoothstep(.39, .47, p)) * .66;
      const floor = currentLight * smoothstep(.10, .24, p) * (1 - smoothstep(.38, .47, p));
      const rays = currentLight * smoothstep(.12, .28, p) * (1 - smoothstep(.38, .46, p)) * .9;
      const flare = currentLight * smoothstep(.13, .25, p) * (1 - smoothstep(.37, .45, p)) * .84;
      // Hidden, not just transparent: an invisible blended layer still costs a full-screen pass.
      ([[els.lightWash, wash], [els.floorLight, floor], [els.rays, rays], [els.flare, flare]] as [HTMLElement, number][]).forEach(([el, value]) => {
        visible(el, value > .003);
        opacity(el, value);
      });
      transform(els.floorLight, `translate(-50%,-50%) scale(${lerp(.38, 1.15, smoothstep(.1, .3, p)).toFixed(3)})`);
      transform(els.rays, `scale(2) rotate(${(Math.sin(now * .00017) * 3).toFixed(2)}deg)`);
    }

    // The shelf close-up rides the same camera and resolves out of the fridge photo.
    // The close-up's layer exists (transparent) from the start of the push-in, so it is ready when it shows.
    const plateReady = p >= C.pushIn[0] - .02 && !cut;
    visible(els.zoomPlate, plateReady);
    if (plateReady) {
      const plateScale = scale / L.cover;
      transform(els.zoomPlate, `translate3d(${(focusX + scale * (L.shelf.x - L.target.x)).toFixed(2)}px,${(focusY + scale * (L.shelf.y - L.target.y)).toFixed(2)}px,0) scale(${plateScale.toFixed(5)})`);
      opacity(els.zoomPlate, plateBlend);
      // Soft edges until it is larger than the screen, so no photo rectangle ever shows. The middle of
      // each side sits at 71% of the gradient, so the fade ends there until the photo fills the screen.
      const solid = Math.round(lerp(lerp(16, 60, clamp(plateFill, 0, 1)), 100, edgeGone));
      const clear = Math.round(lerp(71, 160, edgeGone));
      const mask = edgeGone >= 1 ? "none" : `radial-gradient(ellipse farthest-corner at 50% 50%, #000 ${Math.min(solid, clear - 1)}%, transparent ${clear}%)`;
      style(els.zoomPlate, "-webkit-mask-image", mask);
      style(els.zoomPlate, "mask-image", mask);
      filter(els.zoomPlate, `brightness(${lerp(1.0, 1.7, flashUp).toFixed(3)}) saturate(${lerp(.92, .7, flashUp).toFixed(3)}) blur(${qBlur(Math.min(6, dissolveBlur / plateScale) + flashUp * 6)}px)`);
    }
    // Shown (still transparent) a little early, so their layers exist before the light arrives.
    const flashOn = flash > .001 || (p > C.flashIn[0] - .03 && p < C.flashOut[1]);
    visible(els.flashWhite, flashOn); visible(els.flashOrb, flashOn); visible(els.flashStreak, flashOn);
    if (flashOn) {
      // Never exactly 0 while shown: the browser skips painting fully transparent layers and then
      // painted all three at once as the light arrived, dropping a frame.
      opacity(els.flashWhite, Math.max(.004, p < C.flashOut[0] ? flashUp : 1 - smoothstep(C.flashOut[0], C.flashOut[0] + .017, p)));
      opacity(els.flashOrb, Math.max(.004, p < C.flashOut[0] ? flashUp * .9 : .9 * (1 - flashRelease)));
      // The orb element is a quarter size; the scale is multiplied to match.
      transform(els.flashOrb, `scale(${(4 * (p < C.flashOut[0] ? lerp(.6, 1.2, flashUp) : lerp(1.2, .04, flashRelease))).toFixed(4)})`);
      opacity(els.flashStreak, Math.max(.004, smoothstep(.40, .44, p) * (1 - smoothstep(.47, .52, p)) * .9));
      transform(els.flashStreak, `scaleX(${lerp(.3, 1.4, range(p, .40, .50)).toFixed(3)})`);
    }
    const lens = 1 - flash * .95;
    opacity(els.vignette, lens);
    opacity(els.scrim, lens);
    visible(els.grain, lens > .05);

    // Scene 2: the void.
    const fly = easeInOut(range(p, C.flythrough[0], C.flythrough[1]));
    currentCamZ = reduced ? 700 : lerp(C.cameraZ[0], C.cameraZ[1], fly);
    // A jump (Skip, Replay, first frame) is not camera motion, so it must not smear anything.
    const camStep = Math.abs(currentCamZ - previousCamZ);
    camSpeed = lerp(camSpeed, camStep > 400 ? 0 : camStep / dt, 1 - Math.exp(-dt * 8));
    visible(els.voidScene, voidAlpha > 0);
    opacity(els.voidScene, voidAlpha);
    style(els.ingredientField, "display", cut && p < .9 ? "block" : "none");
    if (cut && p < .9) updateIngredients(p, now, 1 - smoothstep(.79, .88, p));

    // Scene 3: the table. The camera trucks slowly sideways, then settles on the centre for the brand.
    visible(els.tableScene, tableAlpha > 0);
    if (tableAlpha > 0) {
      opacity(els.tableScene, tableAlpha);
      const candle = 1 + .025 * Math.sin(now * .009) * Math.sin(now * .0041);
      transform(els.tableBg, `translate3d(${lerp(1.2, -1.2, truck).toFixed(3)}%,0,0) scale(${lerp(1.08, 1.03, tableAlpha).toFixed(3)})`);
      filter(els.tableBg, `brightness(${(lerp(.48, .76, tableAlpha) * candle).toFixed(3)}) saturate(${lerp(.7, 1.04, warm).toFixed(3)})`);
      const dishRise = lerp(26, 0, focus) - final * L.dishRise;
      const dishScale = lerp(.92, 1, focus) * lerp(1, L.dishFinalScale, final);
      const dishShift = lerp(1, -1, truck) * (phone ? 12 : 28) * (1 - final);
      opacity(els.dishWrap, smoothstep(.74, .80, p));
      transform(els.dishWrap, `translate(-50%,-50%) translate3d(${dishShift.toFixed(2)}px,${dishRise.toFixed(2)}px,0) scale(${dishScale.toFixed(3)})`);
      filter(els.dish, `blur(${qBlur((1 - focus) * 16)}px) brightness(${lerp(.55, 1, focus).toFixed(3)})`);
      opacity(els.contactShadow, focus * (1 - final * .42) * .82);
      transform(els.contactShadow, `scale(${lerp(.82, 1, focus).toFixed(3)})`);
      opacity(els.dishGlow, focus * .95);
      style(els.dishSheen, "background-position", `${lerp(110, -10, range(p, .82, 1)).toFixed(2)}% 0`);
      opacity(els.dishSheen, Math.pow(focus, 3) * .85);
      opacity(els.steam, smoothstep(C.steam[0], .885, p) * (1 - smoothstep(.94, 1, p)) * .72);
    }

    const cool = lerp(.18, 0, warm) * lens;
    visible(els.coolGrade, cool > .003); opacity(els.coolGrade, cool);
    visible(els.warmGrade, warm > .003); opacity(els.warmGrade, warm * .28);
    captions.forEach((c) => captionFrame(c, p, now));

    // Brand: kicker, wordmark, tagline and buttons land one after another.
    visible(els.brand, brand > .002);
    brandParts.forEach((part, j) => {
      const t = easeOut(clamp((brand - j * .13) / .61, 0, 1));
      opacity(part, t);
      transform(part, `translate3d(0,${((1 - t) * 22).toFixed(2)}px,0)`);
      filter(part, `blur(${qBlur((1 - t) * 12)}px)`);
    });

    // Frame chrome: the bars retract at the end and the small labels step aside for the brand.
    const barsIn = easeInOut(clamp((now - readyAt) / C.barsInMs, 0, 1));
    const retract = smoothstep(.89, .97, p);
    const barOffset = 100 * (1 - barsIn) + 100 * retract;
    transform(els.topBox, `translateY(${(-barOffset).toFixed(2)}%)`);
    transform(els.bottomBox, `translateY(${barOffset.toFixed(2)}%)`);
    const chrome = 1 - smoothstep(.88, .93, p);
    [els.miniMark, els.topTagline, els.skip, els.bottombar, els.progressRail].forEach((el) => { opacity(el, chrome); visible(el, chrome > .01); });
    style(els.skip, "display", chrome > .01 ? "" : "none"); // lets the sound toggle settle in the corner
    transform(els.progress, `scaleY(${p.toFixed(4)})`);
    opacity(els.scrollHint, 1 - smoothstep(.005, .035, p));
    updateChapter(p);

    // Dust and sound share the camera's speed.
    const camPos = push * 3 + (currentCamZ / C.cameraZ[1]) * 6;
    const camPosStep = Math.abs(camPos - previousCamPos);
    const velocity = camPosStep > .5 ? 0 : camPosStep / dt;
    previousCamPos = camPos;
    dustSpeed = lerp(dustSpeed, clamp(velocity * .2, 0, 1.5), 1 - Math.exp(-dt * 8));
    const fridgeDust = cut ? 0 : currentLight * smoothstep(.09, .2, p) * (1 - flash);
    const voidDust = cut ? (1 - flash) * (1 - warm) * .8 : 0;
    drawDust(now, dt, Math.max(fridgeDust, voidDust, warm * .45), warm, dustSpeed, cut ? 0 : 1);

    updateCues(p);
    sound.update({ light: currentLight, push, cut: cut ? 1 : 0, voidA: voidAlpha, speed: dustSpeed, warm, focus });

    previousCamZ = currentCamZ;
    frames += 1;
    if (now - fpsStamp >= 500) { fps = Math.round(frames * 1000 / (now - fpsStamp)); frames = 0; fpsStamp = now; }
    if (debugEnabled) {
      const scene = p < .12 ? "The fridge" : p < .455 ? "The light" : p < .70 ? "Every ingredient" : p < .89 ? "Together" : "MealMatch";
      els.debug.textContent = `p  ${p.toFixed(4)}\n${scene}\n${fps} fps`;
    }
  }

  function jumpTo(value: number) {
    targetProgress = currentProgress = value;
    // "instant": the app sets scroll-behavior: smooth, which would play the whole film on Skip.
    if (trigger) window.scrollTo({ top: trigger.start + (trigger.end - trigger.start) * value, behavior: "instant" });
  }

  const listeners: [EventTarget, string, EventListener][] = [];
  const listen = (target: EventTarget, type: string, handler: EventListener) => { target.addEventListener(type, handler); listeners.push([target, type, handler]); };
  listen(els.skip, "click", () => jumpTo(1));
  listen(els.replay, "click", () => jumpTo(0));
  listen(els.miniMark, "click", () => jumpTo(0));
  listen(els.enter, "click", () => onEnter());
  listen(els.soundButton, "click", () => {
    const on = sound.toggle();
    els.soundButton.setAttribute("aria-pressed", String(on));
    els.soundButton.setAttribute("aria-label", on ? "Turn sound off" : "Turn sound on");
    els.soundLabel.textContent = on ? "Sound on" : "Sound off";
  });
  listen(document, "visibilitychange", () => sound.suspend(document.hidden));
  listen(window, "resize", () => { resizeCanvas(); measure(); });

  if (frozenValue === null) {
    window.scrollTo({ top: 0, behavior: "instant" });
    trigger = ScrollTrigger.create({
      trigger: els.experience, pin: els.stage, start: "top top",
      end: () => `+=${window.innerHeight * ((window.innerWidth < 700 ? C.scrollScreens.phone : C.scrollScreens.desktop) - 1)}`,
      anticipatePin: 1, invalidateOnRefresh: true,
      onUpdate: (self) => { targetProgress = self.progress; },
      onRefresh: () => measure(),
    });
  }
  measure();
  resizeCanvas();
  readyAt = performance.now() - (frozenValue === null ? 0 : 5000); // pinned frames show the settled state
  lastNow = performance.now();
  root.classList.add("is-ready");
  if (frozenValue !== null) root.classList.add("is-frozen"); // ?introP= pins a frame for review: show it at once
  if (debugEnabled) els.debug.classList.add("is-visible");
  const tick = () => render(performance.now());
  gsap.ticker.add(tick);
  render(performance.now());
  (window as unknown as { __MEALMATCH_INTRO__?: unknown }).__MEALMATCH_INTRO__ = { getProgress: () => frozenValue ?? currentProgress, jumpTo };

  return {
    // Stop scrolling the film and hold the last frame while the app fades in underneath.
    leave() {
      if (leaving) return;
      leaving = true;
      trigger?.kill(true);
      trigger = null;
      targetProgress = currentProgress = 1;
      root.classList.add("is-leaving");
      window.scrollTo({ top: 0, behavior: "instant" });
    },
    destroy() {
      gsap.ticker.remove(tick);
      trigger?.kill(true);
      listeners.forEach(([target, type, handler]) => target.removeEventListener(type, handler));
      sound.close();
      delete (window as unknown as { __MEALMATCH_INTRO__?: unknown }).__MEALMATCH_INTRO__;
    },
  };
}

type SoundState = { light: number; push: number; cut: number; voidA: number; speed: number; warm: number; focus: number };

// Sound: synthesized with Web Audio, no files. Off until the viewer turns it on.
function createSound() {
  let ctx: AudioContext | null = null;
  let master: GainNode, reverb: ConvolverNode, white: AudioBuffer;
  let enabled = false;
  const L: Record<string, GainNode | BiquadFilterNode> = {};
  const g = (name: string) => L[name] as GainNode;
  const f = (name: string) => L[name] as BiquadFilterNode;
  function gain(value: number, dest?: AudioNode) { const node = ctx!.createGain(); node.gain.value = value; if (dest) node.connect(dest); return node; }
  function biquad(type: BiquadFilterType, freq: number, q: number, dest?: AudioNode) { const node = ctx!.createBiquadFilter(); node.type = type; node.frequency.value = freq; node.Q.value = q || .7; if (dest) node.connect(dest); return node; }
  function osc(type: OscillatorType, freq: number, dest: AudioNode, detune = 0) { const node = ctx!.createOscillator(); node.type = type; node.frequency.value = freq; node.detune.value = detune; node.connect(dest); node.start(); return node; }
  function noise(seconds: number, brown: boolean) {
    const length = Math.floor(ctx!.sampleRate * seconds), buffer = ctx!.createBuffer(1, length, ctx!.sampleRate), data = buffer.getChannelData(0);
    let last = 0;
    for (let j = 0; j < length; j += 1) {
      const n = Math.random() * 2 - 1;
      if (brown) { last = (last + .02 * n) / 1.02; data[j] = last * 3.5; } else data[j] = n;
    }
    return buffer;
  }
  function loop(buffer: AudioBuffer, dest: AudioNode) { const source = ctx!.createBufferSource(); source.buffer = buffer; source.loop = true; source.connect(dest); source.start(); return source; }
  function room(seconds: number, decay: number) {
    const length = Math.floor(ctx!.sampleRate * seconds), buffer = ctx!.createBuffer(2, length, ctx!.sampleRate);
    for (let c = 0; c < 2; c += 1) { const data = buffer.getChannelData(c); for (let j = 0; j < length; j += 1) data[j] = (Math.random() * 2 - 1) * Math.pow(1 - j / length, decay); }
    return buffer;
  }
  function build() {
    ctx = new AudioContext();
    const compressor = ctx.createDynamicsCompressor();
    compressor.threshold.value = -20; compressor.ratio.value = 3; compressor.connect(ctx.destination);
    master = gain(0, compressor);
    reverb = ctx.createConvolver(); reverb.buffer = room(3.4, 2.4); reverb.connect(gain(.32, master));
    white = noise(2.5, false);
    const brown = noise(5, true);
    L.room = gain(0, master); loop(brown, biquad("lowpass", 300, .5, L.room));
    L.hum = gain(0, master);
    const humFilter = biquad("lowpass", 380, .7, L.hum);
    osc("sine", 58, gain(.6, humFilter)); osc("sine", 116, gain(.26, humFilter)); osc("triangle", 174, gain(.07, humFilter));
    L.whoosh = gain(0, master); L.whoosh.connect(reverb);
    L.whooshF = biquad("bandpass", 300, .9, L.whoosh); loop(white, L.whooshF);
    L.drone = gain(0, master); L.drone.connect(reverb);
    const droneFilter = biquad("lowpass", 640, .6, L.drone);
    osc("sine", 55, gain(.5, droneFilter)); osc("sine", 82.41, gain(.3, droneFilter), 5); osc("triangle", 110, gain(.08, droneFilter), -7);
    L.wind = gain(0, master); L.windF = biquad("bandpass", 800, .45, L.wind); loop(brown, L.windF);
    L.pad = gain(0, master); L.pad.connect(reverb);
    L.padF = biquad("lowpass", 600, .7, L.pad);
    [[220, .3], [277.18, .2], [329.63, .18], [440, .07]].forEach(([freq, level], j) => { osc("triangle", freq, gain(level, L.padF), j % 2 ? 6 : -6); });
  }
  const set = (param: AudioParam, value: number, tc = .12) => param.setTargetAtTime(value, ctx!.currentTime, tc);
  function envelope(node: GainNode, t0: number, peak: number, attack: number, decay: number) {
    node.gain.setValueAtTime(0.0001, t0);
    node.gain.exponentialRampToValueAtTime(peak, t0 + attack);
    node.gain.exponentialRampToValueAtTime(0.0001, t0 + attack + decay);
  }
  function burst(t0: number, type: BiquadFilterType, freq: number, peak: number, decay: number, dest?: AudioNode) {
    const source = ctx!.createBufferSource(); source.buffer = white;
    const node = gain(0, dest || master); source.connect(biquad(type, freq, .7, node));
    envelope(node, t0, peak, .005, decay); source.start(t0); source.stop(t0 + decay + .05);
  }
  function tone(t0: number, type: OscillatorType, f0: number, f1: number, peak: number, attack: number, decay: number, dest?: AudioNode) {
    const oscillator = ctx!.createOscillator(); oscillator.type = type;
    oscillator.frequency.setValueAtTime(f0, t0);
    if (f1 !== f0) oscillator.frequency.exponentialRampToValueAtTime(f1, t0 + attack + decay * .5);
    const node = gain(0, dest || master); oscillator.connect(node);
    envelope(node, t0, peak, attack, decay); oscillator.start(t0); oscillator.stop(t0 + attack + decay + .05);
  }
  const cues: Record<string, (t: number) => void> = {
    pop(t) { // the seal lets go, the light stutters on
      tone(t, "sine", 120, 44, .45, .006, .3); burst(t, "lowpass", 1300, .16, .22);
      [0, .07, .135, .235, .315].forEach((dt) => burst(t + dt, "highpass", 3800, .05, .012));
      tone(t + .02, "square", 118, 118, .012, .01, .3);
    },
    flash(t) { [1318.5, 1975.5, 2637].forEach((freq, j) => tone(t + j * .04, "sine", freq, freq, .03, .5, 2.8, reverb)); },
    land(t) { tone(t, "sine", 72, 40, .32, .02, 1.4); burst(t, "lowpass", 500, .09, .6, reverb); },
    chime(t) { [[880, .07], [1760, .035], [2649, .02], [3700, .01]].forEach(([freq, level]) => { tone(t, "sine", freq, freq, level, .006, 3.2, reverb); tone(t, "sine", freq, freq, level * .6, .006, 1.4); }); },
  };
  return {
    toggle() {
      if (!ctx) build();
      enabled = !enabled;
      if (ctx!.state === "suspended") void ctx!.resume();
      master.gain.cancelScheduledValues(ctx!.currentTime);
      master.gain.setTargetAtTime(enabled ? .9 : 0, ctx!.currentTime, .25);
      return enabled;
    },
    suspend(hidden: boolean) { if (!ctx) return; if (hidden) void ctx.suspend(); else if (enabled) void ctx.resume(); },
    update(s: SoundState) {
      if (!enabled || !ctx) return;
      set(g("room").gain, .05 * (1 - s.cut));
      set(g("hum").gain, .075 * s.light * (1 - s.cut) + .05 * s.push * (1 - s.cut));
      set(g("whoosh").gain, .2 * Math.pow(s.push, 1.6) * (1 - s.cut) + .12 * clamp(s.speed, 0, 1) * s.voidA);
      set(f("whooshF").frequency, s.cut ? 500 + s.speed * 1800 : lerp(260, 5200, s.push), .08);
      set(g("drone").gain, .085 * s.voidA * (1 - s.warm), .3);
      set(g("wind").gain, .05 * s.voidA * (1 - s.warm), .3);
      set(f("windF").frequency, 700 + s.speed * 1400, .2);
      set(g("pad").gain, .06 * s.warm, .4);
      set(f("padF").frequency, lerp(500, 1600, s.focus), .4);
    },
    cue(name: string) { if (enabled && ctx) cues[name](ctx.currentTime + .01); },
    close() { if (ctx && ctx.state !== "closed") void ctx.close(); ctx = null; enabled = false; },
  };
}
