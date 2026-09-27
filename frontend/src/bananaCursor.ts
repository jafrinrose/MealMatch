/**
 * Renders the banana emoji to a PNG cursor. Emoji inside SVG cursors render
 * inconsistently across browsers; a bitmap drawn from the system emoji font is
 * crisp everywhere and gets a 2x version for high-density screens.
 */
function render(size: number, scale: number, angle: number): string {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size * scale;
  const context = canvas.getContext("2d");
  if (!context) return "";
  context.scale(scale, scale);
  context.translate(size / 2, size / 2);
  context.rotate((angle * Math.PI) / 180);
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.font = `${size * 0.78}px "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif`;
  context.shadowColor = "rgba(0, 0, 0, .28)";
  context.shadowBlur = 2;
  context.shadowOffsetY = 1;
  context.fillText("🍌", 0, size * 0.04);
  return canvas.toDataURL("image/png");
}

export function installBananaCursor() {
  if (typeof window === "undefined" || !window.matchMedia("(pointer: fine)").matches) return;
  const size = 32;
  const set = (name: string, angle: number) => {
    const one = render(size, 1, angle);
    const two = render(size, 2, angle);
    if (!one) return;
    // Hotspot at the banana's stem tip.
    const value = `image-set(url("${one}") 1x, url("${two}") 2x) 6 5`;
    document.documentElement.style.setProperty(name, CSS.supports("cursor", `${value}, auto`) ? value : `url("${one}") 6 5`);
  };
  set("--banana-cursor", -28);
  set("--banana-pointer", -8);
}
