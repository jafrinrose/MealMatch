import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { api, apiBaseUrl, errorMessage } from "../api";
import type { PantryItem, DetectedIngredient } from "../types";
import { quantityUnits, parseQuantity, inferCategory, normalizedCategory } from "../utils";
import { Icon } from "./ui";

type AddMode = "manual" | "receipt" | "photo";

// One line of the /upload-image stream: the whole photo, then close-ups (automatic, or after "Look closer").
type PhotoScanEvent =
  | { type: "suggestions"; scan_id: string; pass_number: number; passes: number; detections: DetectedIngredient[]; alternatives: { detection_id: string; ingredient: string }[] }
  | { type: "done"; warnings: string[] }
  | { type: "error"; detail: string };

export function IngredientSheet({ userId, editingItem, onClose, onSaved }: { userId: number; editingItem: PantryItem | null; onClose: () => void; onSaved: (message: string) => void }) {
  const [mode, setMode] = useState<AddMode>("manual");
  const [ingredient, setIngredient] = useState(editingItem?.ingredient || "");
  const [quantity, setQuantity] = useState(editingItem?.quantity.match(/^\d+(?:\.\d+)?/)?.[0] || "1");
  const [unit, setUnit] = useState(editingItem?.quantity.replace(/^\s*\d+(?:\.\d+)?\s*/, "") || "piece");
  const [expiryDate, setExpiryDate] = useState(editingItem?.expiry_date || "");
  const [detected, setDetected] = useState<DetectedIngredient[]>([]);
  const [scanId, setScanId] = useState<string | null>(null);
  const [scanWarnings, setScanWarnings] = useState<string[]>([]);
  const [hasScanned, setHasScanned] = useState(false);
  const [userConfidence, setUserConfidence] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [analysing, setAnalysing] = useState(false);
  const [analysisSeconds, setAnalysisSeconds] = useState(0);
  const [scanError, setScanError] = useState("");
  const [saveError, setSaveError] = useState("");
  const [closeUps, setCloseUps] = useState<{ checked: number; total: number; found: number } | null>(null);
  const scanAbort = useRef<AbortController | null>(null);
  // Kept in the browser only, so "Look closer" can send it again; the server never stores it.
  const scannedPhoto = useRef<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => () => scanAbort.current?.abort(), []);

  useEffect(() => {
    if (!analysing) return;
    setAnalysisSeconds(0);
    const timer = window.setInterval(() => setAnalysisSeconds((seconds) => seconds + 1), 1000);
    return () => window.clearInterval(timer);
  }, [analysing]);

  async function saveManual() {
    if (!ingredient.trim()) return;
    setBusy(true);
    setSaveError("");
    try {
      const formattedQuantity = `${quantity} ${unit}`.trim();
      const category = inferCategory(ingredient);
      if (editingItem) {
        await api.put(`/pantry/item/${editingItem.id}`, { ingredient, quantity: formattedQuantity, expiry_date: expiryDate, category });
        onSaved("Ingredient updated.");
      } else {
        await api.post(`/pantry/${userId}`, null, { params: { ingredient, quantity: formattedQuantity, expiry_date: expiryDate, category } });
        onSaved("Ingredient added to your pantry.");
      }
    } catch (error) {
      setSaveError(errorMessage(error, "Could not save this ingredient. Please try again."));
    } finally { setBusy(false); }
  }

  function stopCloseUps() {
    scanAbort.current?.abort();
    scanAbort.current = null;
    setCloseUps(null);
  }

  function resetScan(nextMode: AddMode) {
    stopCloseUps();
    scannedPhoto.current = null;
    setMode(nextMode);
    setDetected([]);
    setHasScanned(false);
    setScanId(null);
    setScanWarnings([]);
  }

  function reviewable(item: DetectedIngredient): DetectedIngredient {
    return { ...item, quantity: item.quantity || "1 piece", expiry_date: "", category: normalizedCategory(item.category, item.ingredient) };
  }

  function showSuggestions(detections: DetectedIngredient[], warnings: string[]) {
    setHasScanned(true);
    setUserConfidence(null);
    setScanWarnings(warnings);
    setDetected(detections.map(reviewable));
  }

  // Close-up passes only add foods the list does not have yet, below the rows
  // the user may already be editing, and offer more specific names as buttons.
  function addCloseUp(event: Extract<PhotoScanEvent, { type: "suggestions" }>) {
    const incoming = event.detections.map(reviewable);
    setDetected((current) => {
      const listed = new Set(current.map((item) => item.ingredient.trim().toLowerCase()));
      const withAlternatives = current.map((item) => {
        const names = event.alternatives.filter((alternative) => alternative.detection_id === item.detection_id && alternative.ingredient !== item.ingredient).map((alternative) => alternative.ingredient);
        return names.length ? { ...item, semantic_alternatives: [...new Set([...(item.semantic_alternatives || []), ...names])] } : item;
      });
      return [...withAlternatives, ...incoming.filter((item) => !listed.has(item.ingredient.toLowerCase()))];
    });
    setCloseUps((current) => current && { ...current, checked: event.pass_number - 1, found: current.found + incoming.length });
  }

  async function scanPhoto(path: string, formData: FormData, onFirstResults: () => void) {
    const controller = new AbortController();
    scanAbort.current = controller;
    const response = await fetch(`${apiBaseUrl}${path}`, { method: "POST", body: formData, signal: controller.signal });
    if (!response.ok || !response.body) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || "The image could not be processed. Please try another image.");
    }
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffered = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffered += value;
      const lines = buffered.split("\n");
      buffered = lines.pop() || "";
      for (const line of lines.filter((text) => text.trim())) {
        const event = JSON.parse(line) as PhotoScanEvent;
        if (event.type === "error") throw new Error(event.detail);
        if (event.type === "done") {
          if (event.warnings.length) setScanWarnings(event.warnings);
          setCloseUps((current) => current && { ...current, checked: current.total });
        } else if (event.pass_number === 1) {
          setScanId(event.scan_id);
          showSuggestions(event.detections, []);
          setCloseUps(event.passes > 1 ? { checked: 0, total: event.passes - 1, found: 0 } : null);
          onFirstResults();
        } else {
          addCloseUp(event);
        }
      }
    }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setAnalysing(true);
    setScanError("");
    const formData = new FormData();
    formData.append("file", file);
    let reviewing = false;
    const startReview = () => { reviewing = true; setBusy(false); setAnalysing(false); };
    try {
      if (mode === "photo") {
        formData.append("user_id", String(userId));
        stopCloseUps();
        scannedPhoto.current = file;
        await scanPhoto("/upload-image", formData, startReview);
      } else {
        const response = await api.post("/upload-receipt", formData, { headers: { "Content-Type": "multipart/form-data" } });
        setScanId(null);
        showSuggestions(Array.isArray(response.data.detections) ? response.data.detections : [], Array.isArray(response.data.warnings) ? response.data.warnings : []);
      }
    } catch (error) {
      if ((error as Error).name === "AbortError") return;
      const detail = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail || (error as Error).message;
      if (reviewing) setScanWarnings((current) => [...current, "The close-up check stopped early. Add any missed items below."]);
      else setScanError(detail || "The image could not be processed. Please try another image.");
    } finally {
      if (!reviewing) { setBusy(false); setAnalysing(false); }
      event.target.value = "";
    }
  }

  // Four zoomed-in checks for small or hidden items, only when the user asks:
  // they are four more model runs and add more wrong items than right ones on average.
  async function lookCloser() {
    if (!scanId || !scannedPhoto.current) return;
    const formData = new FormData();
    formData.append("file", scannedPhoto.current);
    formData.append("user_id", String(userId));
    setCloseUps({ checked: 0, total: 4, found: 0 });
    try {
      await scanPhoto(`/upload-image/${scanId}/close-ups`, formData, () => undefined);
    } catch (error) {
      if ((error as Error).name === "AbortError") return;
      setCloseUps(null);
      setScanWarnings((current) => [...current, (error as Error).message || "The close-up check did not finish. Add any missed items below."]);
    }
  }

  function updateDetected(index: number, changes: Partial<DetectedIngredient>) {
    setDetected((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...changes } : item));
  }

  function adjustDetectedQuantity(index: number, change: number) {
    const parsed = parseQuantity(detected[index]?.quantity || "1 piece");
    updateDetected(index, { quantity: `${Math.max(0, parsed.amount + change)} ${parsed.unit}`.trim() });
  }

  async function saveDetected() {
    if (!detected.length) return;
    stopCloseUps();
    setBusy(true);
    setSaveError("");
    try {
      await api.post(`/verify-ingredients/${userId}`, {
        items: detected.map((item) => ({ ...item, category: inferCategory(item.ingredient) })),
        scan_id: scanId,
        user_confidence: userConfidence,
      });
      onSaved(`${detected.length} ingredient${detected.length === 1 ? "" : "s"} added to your pantry.`);
    } catch (error) {
      setSaveError(errorMessage(error, "Could not add these ingredients. Please try again."));
    } finally { setBusy(false); }
  }

  return (
    <div className="sheet-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="ingredient-sheet" role="dialog" aria-modal="true" aria-label={editingItem ? "Edit ingredient" : "Add ingredients"}>
        <div className="sheet-handle" />
        <header><div><p className="eyebrow">Keep your kitchen current</p><h2>{editingItem ? "Edit ingredient" : "Add ingredients"}</h2></div><button onClick={onClose} aria-label="Close"><Icon name="close" /></button></header>
        {!editingItem && <div className="mode-tabs"><button className={mode === "manual" ? "active" : ""} onClick={() => { stopCloseUps(); setMode("manual"); }}><Icon name="edit" />Manual</button><button className={mode === "receipt" ? "active" : ""} onClick={() => resetScan("receipt")}><Icon name="receipt" />Receipt</button><button className={mode === "photo" ? "active" : ""} onClick={() => { resetScan("photo"); void api.post("/vision/warmup").catch(() => undefined); }}><Icon name="camera" />Photo</button></div>}
        {(mode === "manual" || editingItem) ? (
          <div className="ingredient-form">
            <label><span>Ingredient name</span><input autoFocus value={ingredient} onChange={(event) => setIngredient(event.target.value)} placeholder="e.g. Tomatoes, milk, chicken…" /></label>
            <div className="form-row"><label><span>Quantity</span><div className="stepper"><button onClick={() => setQuantity(String(Math.max(0, Number(quantity) - 1)))}>−</button><input inputMode="decimal" value={quantity} onChange={(event) => setQuantity(event.target.value)} /><button onClick={() => setQuantity(String(Number(quantity || 0) + 1))}>+</button></div></label><label><span>Unit</span><select value={unit} onChange={(event) => setUnit(event.target.value)}>{quantityUnits.map((option) => <option key={option}>{option}</option>)}</select></label></div>
            <label><span>Expiry date <small>(optional)</small></span><input type="date" value={expiryDate} onChange={(event) => setExpiryDate(event.target.value)} /><small className="expiry-help">Leave blank and MealMatch will add a clearly marked estimate from food-storage guidance.</small></label>
            {saveError && <p className="scan-error" role="alert"><Icon name="alert" />{saveError}</p>}
            <button className="primary-button sheet-save" disabled={!ingredient.trim() || busy} onClick={() => void saveManual()}><Icon name={editingItem ? "check" : "plus"} />{busy ? "Saving…" : editingItem ? "Save changes" : "Add to pantry"}</button>
          </div>
        ) : (
          <div className="scan-panel">
            {!hasScanned ? <>
              <span className="scan-icon"><Icon name={mode === "receipt" ? "receipt" : "camera"} /></span>
              <h3>{mode === "receipt" ? "Scan a grocery receipt" : "Photograph your ingredients"}</h3>
              <p>Confirm results before saving.</p>
              <button className="primary-button" disabled={busy} onClick={() => fileInput.current?.click()}><Icon name="upload" />{analysing ? <><i className="button-spinner" /> Analysing image…</> : "Choose an image"}</button>
              {analysing && <div className="analysis-wait" role="status"><span><i className="button-spinner" /> {mode === "receipt" ? "Reading your receipt…" : "Looking at your photo…"}</span><strong>{analysisSeconds}s</strong></div>}
            </> : <>
              <h3>Confirm what we found</h3>
              <p>Confirm results before saving.</p>
              {scanWarnings.map((warning) => <p className="scan-warning" key={warning}><Icon name="alert" />{warning}</p>)}
              {detected.length > 0 && <>
                <div className="detected-head"><span>Ingredient</span><span>Quantity & unit</span><span>Expiry date</span><span /></div>
                <div className="detected-list">{detected.map((item, index) => {
                  const parsed = parseQuantity(item.quantity);
                  return <div key={item.detection_id || index}>
                    <label><span>Ingredient</span><input value={item.ingredient} onChange={(event) => updateDetected(index, { ingredient: event.target.value, category: inferCategory(event.target.value) })} />{item.confidence != null && <small>{Math.round(item.confidence * 100)}% sure</small>}{item.visible_text && <small>{item.source === "Receipt" ? "On receipt" : "Label read"}: “{item.visible_text}”</small>}{item.semantic_alternatives?.map((alternative) => <button type="button" className="semantic-alternative" key={alternative} onClick={() => updateDetected(index, { ingredient: alternative, category: inferCategory(alternative) })}>Vision model suggests “{alternative}” — use this</button>)}</label>
                    <label><span>Quantity & unit</span><div className="detected-quantity"><button type="button" aria-label={`Decrease ${item.ingredient} quantity`} onClick={() => adjustDetectedQuantity(index, -1)}>−</button><input inputMode="decimal" value={parsed.amount} onChange={(event) => updateDetected(index, { quantity: `${event.target.value} ${parsed.unit}` })} /><button type="button" aria-label={`Increase ${item.ingredient} quantity`} onClick={() => adjustDetectedQuantity(index, 1)}>+</button><select aria-label={`${item.ingredient} unit`} value={parsed.unit} onChange={(event) => updateDetected(index, { quantity: `${parsed.amount} ${event.target.value}` })}>{quantityUnits.map((option) => <option key={option}>{option}</option>)}</select></div></label>
                    <label><span>Expiry date</span><input type="date" value={item.expiry_date} onChange={(event) => updateDetected(index, { expiry_date: event.target.value })} /></label>
                    <button className="remove-detection" onClick={() => setDetected(detected.filter((_, i) => i !== index))} aria-label={`Remove ${item.ingredient}`}><Icon name="close" /></button>
                  </div>;
                })}</div>
              </>}
              {detected.length === 0 && <p className="empty-detection">Nothing reliable was detected. Add any visible food manually or try a clearer, closer photograph.</p>}
              {closeUps ? (closeUps.checked < closeUps.total
                ? <p className="close-up-status" role="status"><i className="button-spinner" />Looking closer for more items: {closeUps.checked} of {closeUps.total} areas checked{closeUps.found > 0 && `, ${closeUps.found} more found`}. You can keep checking the list.</p>
                : <p className="close-up-status done" role="status"><Icon name="check" />Close-up check done{closeUps.found > 0 ? `: ${closeUps.found} more found and added above.` : ", nothing more found."}</p>)
                : mode === "photo" && scanId && <button type="button" className="look-closer" onClick={() => void lookCloser()}><Icon name="search" /><span><strong>Look closer for missed items</strong><small>Checks four zoomed-in parts of the photo, which takes a while. Extra items are more often wrong, so check them.</small></span></button>}
              <button className="add-missed-detection" onClick={() => setDetected([...detected, { ingredient: "", quantity: "1 piece", category: "other", expiry_date: "", detection_id: `manual-${Date.now()}`, source: "User added" }])}><Icon name="plus" />Add a missed ingredient</button>
              {mode === "photo" && scanId && <fieldset className="scan-confidence"><legend>How confident are you that this final list is correct? <small>(optional)</small></legend><div>{[1, 2, 3, 4, 5].map((rating) => <button type="button" className={userConfidence === rating ? "active" : ""} key={rating} onClick={() => setUserConfidence(rating)} aria-label={`Confidence ${rating} out of 5`}>{rating}</button>)}</div><span><small>Not sure</small><small>Very confident</small></span></fieldset>}
              {saveError && <p className="scan-error" role="alert"><Icon name="alert" />{saveError}</p>}
              <button className="primary-button sheet-save" disabled={busy || detected.some((item) => !item.ingredient.trim()) || detected.length === 0} onClick={() => void saveDetected()}><Icon name="check" />Confirm and add to pantry</button>
            </>}
            {scanError && <p className="scan-error"><Icon name="alert" />{scanError}</p>}
            {/* The formats the backend reads; HEIC is left out, and phones convert camera photos to JPEG. */}
            <input ref={fileInput} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void upload(event)} />
          </div>
        )}
      </section>
    </div>
  );
}
