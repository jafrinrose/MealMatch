"""Prepare and review MealMatch's household-photo evaluation ground truth.

The local browser UI keeps Qwen draft predictions separate from verified human
labels. It binds to localhost and never uploads photographs to a remote service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import shutil
import sys
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from model_services import identify_foods_with_qwen  # noqa: E402


SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_MODELS = ["qwen2.5vl:3b", "qwen2.5vl:7b"]
MANIFEST_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("The manifest root must be a JSON object.")
    for split in ("development", "test"):
        if not isinstance(payload.get(split, []), list):
            raise ValueError(f"Manifest '{split}' must be a list.")
        payload.setdefault(split, [])
    return payload


def write_manifest(path: Path, payload: dict) -> None:
    """Atomically save the manifest and retain its immediately previous state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    backup = path.with_suffix(path.suffix + ".backup")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if path.exists():
        shutil.copy2(path, backup)
    os.replace(temporary, path)


def stable_record_id(relative_path: str) -> str:
    digest = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:12]
    return f"photo-{digest}"


def deterministic_split(relative_path: str, fraction: float, seed: str) -> str:
    digest = hashlib.sha256(f"{seed}:{relative_path}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big") / (2**64 - 1)
    return "development" if value < fraction else "test"


def initialize_manifest(
    images_dir: Path,
    manifest_path: Path,
    development_fraction: float = 0.25,
    seed: str = "20260922",
) -> dict:
    if not 0 < development_fraction < 1:
        raise ValueError("Development fraction must be between 0 and 1.")
    images_dir = images_dir.resolve()
    manifest_path = manifest_path.resolve()
    if not images_dir.is_dir():
        raise ValueError(f"Image directory does not exist: {images_dir}")
    try:
        images_dir.relative_to(manifest_path.parent)
    except ValueError as exc:
        raise ValueError(
            "The image directory must be inside the manifest directory so paths remain portable."
        ) from exc

    payload = (
        load_manifest(manifest_path)
        if manifest_path.exists()
        else {
            "version": 1,
            "description": "MealMatch household-photo ingredient evaluation set",
            "created_at": utc_now(),
            "development": [],
            "test": [],
        }
    )
    existing = {
        str(record.get("image", ""))
        for split in ("development", "test", "excluded")
        for record in payload.get(split, [])
    }
    added = {"development": 0, "test": 0}
    image_paths = sorted(
        path
        for path in images_dir.rglob("*")
        if path.is_file() and path.suffix.casefold() in SUPPORTED_IMAGE_SUFFIXES
    )
    for image_path in image_paths:
        relative = image_path.relative_to(manifest_path.parent).as_posix()
        if relative in existing:
            continue
        split = deterministic_split(relative, development_fraction, seed)
        payload[split].append(
            {
                "id": stable_record_id(relative),
                "image": relative,
                "scene_type": "unknown",
                "packaging": "unknown",
                "difficulty": "unknown",
                "ingredients": [],
                "annotation_status": "unverified",
                "annotation_method": "unlabelled",
                "annotator": "",
                "second_review_status": "not_reviewed",
                "draft_predictions": {},
                "draft_revealed": False,
                "created_at": utc_now(),
                "updated_at": utc_now(),
            }
        )
        existing.add(relative)
        added[split] += 1
    payload["split_seed"] = seed
    payload["development_fraction"] = development_fraction
    payload["last_initialized_at"] = utc_now()
    write_manifest(manifest_path, payload)
    return {
        "images_found": len(image_paths),
        "development_added": added["development"],
        "test_added": added["test"],
        "manifest": str(manifest_path),
    }


def ingredient_text_to_entries(value: str) -> list[dict]:
    """Parse one `canonical | alias, alias` ingredient per line."""
    entries: list[dict] = []
    seen: set[str] = set()
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        name_part, separator, alias_part = line.partition("|")
        name = " ".join(name_part.strip().split()).casefold()
        if not name or name in seen:
            continue
        aliases = []
        if separator:
            aliases = [
                " ".join(alias.strip().split()).casefold()
                for alias in alias_part.split(",")
                if alias.strip()
            ]
        entries.append({"name": name, "aliases": list(dict.fromkeys(aliases))})
        seen.add(name)
    return entries


def entries_to_ingredient_text(entries: object) -> str:
    lines: list[str] = []
    if not isinstance(entries, list):
        return ""
    for entry in entries:
        if isinstance(entry, str):
            lines.append(entry)
            continue
        if not isinstance(entry, dict) or not str(entry.get("name", "")).strip():
            continue
        name = str(entry["name"]).strip()
        aliases = [str(value).strip() for value in entry.get("aliases", []) if str(value).strip()]
        lines.append(f"{name} | {', '.join(aliases)}" if aliases else name)
    return "\n".join(lines)


def flattened_records(payload: dict) -> list[dict]:
    records = []
    for split in ("development", "test"):
        for record in payload.get(split, []):
            copy = dict(record)
            copy["split"] = split
            copy["ingredient_text"] = entries_to_ingredient_text(copy.get("ingredients", []))
            records.append(copy)
    return sorted(records, key=lambda record: (record["split"], record.get("image", "")))


def find_record(payload: dict, record_id: str) -> tuple[str, dict]:
    for split in ("development", "test"):
        for record in payload.get(split, []):
            if record.get("id") == record_id:
                return split, record
    raise KeyError(f"Unknown record id: {record_id}")


def update_record(payload: dict, submitted: dict) -> dict:
    record_id = str(submitted.get("id", ""))
    current_split, record = find_record(payload, record_id)
    requested_split = str(submitted.get("split", current_split))
    if requested_split not in {"development", "test"}:
        raise ValueError("Split must be development or test.")

    for field, allowed in {
        "scene_type": {"fridge", "fridge_shelf", "fridge_drawer", "pantry", "grocery_table", "other", "unknown"},
        "packaging": {"packaged", "unpackaged", "mixed", "unknown"},
        "difficulty": {"easy", "moderate", "high", "unknown"},
        "second_review_status": {"not_reviewed", "agreed", "resolved"},
    }.items():
        value = str(submitted.get(field, record.get(field, "unknown")))
        if value not in allowed:
            raise ValueError(f"Invalid {field}: {value}")
        record[field] = value

    record["annotator"] = str(submitted.get("annotator", "")).strip()[:100]
    record["ingredients"] = ingredient_text_to_entries(str(submitted.get("ingredient_text", "")))
    verified = bool(submitted.get("verified"))
    record["annotation_status"] = "verified" if verified else "unverified"
    if verified:
        if record.get("annotation_method") == "independent_human":
            pass
        elif record.get("draft_revealed"):
            record["annotation_method"] = "model_assisted_human"
        else:
            record["annotation_method"] = "independent_human"
        record["verified_at"] = utc_now()
    else:
        record["annotation_method"] = "unlabelled"
        record.pop("verified_at", None)
    record["updated_at"] = utc_now()

    if requested_split != current_split:
        payload[current_split].remove(record)
        payload[requested_split].append(record)
    return record


def prelabel_record(record: dict, manifest_path: Path, models: list[str]) -> dict:
    relative_path = Path(str(record.get("image", "")))
    image_path = relative_path if relative_path.is_absolute() else manifest_path.parent / relative_path
    if not image_path.exists():
        raise ValueError(f"Image does not exist: {image_path}")
    predictions = dict(record.get("draft_predictions", {}))
    for model_name in models:
        started = time.perf_counter()
        error = ""
        suggestions: list[dict] = []
        try:
            suggestions = identify_foods_with_qwen(str(image_path), model_name)
        except Exception as exc:
            error = str(exc)
        predictions[model_name] = {
            "generated_at": utc_now(),
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "items": suggestions,
            "error": error,
        }
    record["draft_predictions"] = predictions
    record["updated_at"] = utc_now()
    return predictions


ANNOTATION_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MealMatch household photo labeller</title>
<style>
:root{font-family:Inter,ui-sans-serif,system-ui;color:#2c1923;background:#fffafc}*{box-sizing:border-box}body{margin:0}button,input,select,textarea{font:inherit}button{cursor:pointer}.top{position:sticky;top:0;z-index:2;background:#fff;border-bottom:1px solid #eedfe6;padding:14px 24px;display:flex;align-items:center;gap:16px}.top h1{font-size:18px;margin:0}.top span{color:#816b76}.progress{margin-left:auto}.layout{display:grid;grid-template-columns:minmax(360px,1.1fr) minmax(360px,.9fr);min-height:calc(100vh - 61px)}.photo{background:#24171d;display:grid;place-items:center;padding:24px;min-height:680px}.photo img{max-width:100%;max-height:calc(100vh - 110px);object-fit:contain;border-radius:16px}.form{padding:24px 30px 80px;overflow:auto}.notice{padding:12px 14px;background:#fff1f7;border:1px solid #f5cce0;border-radius:12px;font-size:14px;line-height:1.45}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}label{display:grid;gap:6px;margin:14px 0;font-weight:650}label span{font-size:13px;color:#6f5964}input,select,textarea{width:100%;border:1px solid #dbcbd3;background:white;border-radius:10px;padding:10px 12px;color:#2c1923}textarea{min-height:180px;resize:vertical;line-height:1.5}.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}button{border:0;border-radius:10px;padding:10px 14px;background:#f0e7eb;color:#2c1923;font-weight:700}.primary{background:#e93d91;color:white}.drafts{margin-top:18px;border-top:1px solid #eedfe6;padding-top:16px}.draft-card{background:white;border:1px solid #e4d5dc;border-radius:12px;padding:12px;margin:10px 0}.draft-card h3{margin:0 0 8px;font-size:14px}.draft-card p{margin:5px 0;color:#67515d}.hidden{display:none}.status{min-height:22px;color:#9f2864;font-weight:650;margin-top:12px}@media(max-width:850px){.layout{grid-template-columns:1fr}.photo{min-height:360px}.photo img{max-height:55vh}.grid{grid-template-columns:1fr}}
</style></head><body>
<header class="top"><h1>MealMatch household photo labeller</h1><span id="position"></span><span class="progress" id="progress"></span></header>
<main class="layout"><section class="photo"><img id="photo" alt="Household evaluation photograph"></section><section class="form">
<div class="notice"><strong>Final-test rule:</strong> inspect the photograph and enter visible food before revealing drafts. Qwen drafts are suggestions only and never become ground truth without human verification.</div>
<div class="grid"><label><span>Dataset split</span><select id="split"><option value="development">Development</option><option value="test">Frozen test</option></select></label><label><span>Annotator</span><input id="annotator" placeholder="Initials or study ID"></label></div>
<div class="grid"><label><span>Scene</span><select id="scene"><option value="unknown">Choose…</option><option value="fridge">Full fridge</option><option value="fridge_shelf">Fridge shelf</option><option value="fridge_drawer">Fridge drawer</option><option value="pantry">Pantry</option><option value="grocery_table">Grocery table</option><option value="other">Other</option></select></label><label><span>Packaging</span><select id="packaging"><option value="unknown">Choose…</option><option value="packaged">Mostly packaged</option><option value="unpackaged">Mostly unpackaged</option><option value="mixed">Mixed</option></select></label></div>
<label><span>Difficulty</span><select id="difficulty"><option value="unknown">Choose…</option><option value="easy">Easy</option><option value="moderate">Moderate</option><option value="high">High</option></select></label>
<label><span>Visible ingredients — one per line; aliases are optional: eggs | egg</span><textarea id="ingredients" placeholder="milk\neggs | egg\nbroccoli"></textarea></label>
<label><span><input id="verified" type="checkbox" style="width:auto"> I carefully checked the complete image and verified this ground truth</span></label>
<div class="actions"><button id="prev">← Previous</button><button class="primary" id="save">Save</button><button class="primary" id="saveNext">Save and next →</button></div><div class="status" id="status"></div>
<section class="drafts"><h2>Optional hidden model drafts</h2><p>Generate drafts locally. For frozen-test images, save an independent label first and reveal drafts only afterwards.</p><div class="actions"><button id="generate">Generate hidden 3B + 7B drafts</button><button id="reveal">Reveal drafts</button></div><div id="draftOutput" class="hidden"></div></section>
</section></main>
<script>
let records=[],index=0;const $=id=>document.getElementById(id);const fields={split:$('split'),annotator:$('annotator'),scene:$('scene'),packaging:$('packaging'),difficulty:$('difficulty'),ingredients:$('ingredients'),verified:$('verified')};
async function api(path,options){const response=await fetch(path,options);const body=await response.json();if(!response.ok)throw new Error(body.error||'Request failed');return body}
function current(){return records[index]}
function renderDrafts(record){const area=$('draftOutput');area.innerHTML='';if(!record.draft_revealed){area.classList.add('hidden');return}area.classList.remove('hidden');const drafts=record.draft_predictions||{};for(const [model,result] of Object.entries(drafts)){const card=document.createElement('div');card.className='draft-card';const h=document.createElement('h3');h.textContent=model;card.appendChild(h);const p=document.createElement('p');const names=(result.items||[]).map(item=>item.ingredient);p.textContent=result.error?`Error: ${result.error}`:(names.join(', ')||'No suggestions');card.appendChild(p);area.appendChild(card)}}
function render(){const record=current();if(!record)return;$('position').textContent=`${index+1} / ${records.length} · ${record.image}`;$('photo').src=`/image?id=${encodeURIComponent(record.id)}`;fields.split.value=record.split;fields.annotator.value=record.annotator||'';fields.scene.value=record.scene_type||'unknown';fields.packaging.value=record.packaging||'unknown';fields.difficulty.value=record.difficulty||'unknown';fields.ingredients.value=record.ingredient_text||'';fields.verified.checked=record.annotation_status==='verified';renderDrafts(record);const verified=records.filter(item=>item.annotation_status==='verified').length;$('progress').textContent=`${verified} verified / ${records.length}`;$('status').textContent=''}
async function save(moveNext=false){const record=current();const body={id:record.id,split:fields.split.value,annotator:fields.annotator.value,scene_type:fields.scene.value,packaging:fields.packaging.value,difficulty:fields.difficulty.value,ingredient_text:fields.ingredients.value,verified:fields.verified.checked,second_review_status:record.second_review_status||'not_reviewed'};try{$('status').textContent='Saving…';const saved=await api('/api/record',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});Object.assign(record,saved);record.split=body.split;record.ingredient_text=body.ingredient_text;$('status').textContent='Saved';if(moveNext&&index<records.length-1){index++;render()}else render()}catch(error){$('status').textContent=error.message}}
$('prev').onclick=()=>{if(index>0){index--;render()}};$('save').onclick=()=>save(false);$('saveNext').onclick=()=>save(true);
$('generate').onclick=async()=>{const record=current();try{$('status').textContent='Running both local models. This can take several minutes…';const result=await api('/api/prelabel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:record.id})});record.draft_predictions=result.draft_predictions;$('status').textContent='Drafts generated and kept hidden'}catch(error){$('status').textContent=error.message}};
$('reveal').onclick=async()=>{const record=current();if(record.split==='test'&&record.annotation_status!=='verified'){alert('Save and verify your independent test label before revealing model drafts.');return}try{const result=await api('/api/reveal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:record.id})});record.draft_revealed=result.draft_revealed;renderDrafts(record)}catch(error){$('status').textContent=error.message}};
api('/api/manifest').then(data=>{records=data.records;render()}).catch(error=>$('status').textContent=error.message);
</script></body></html>"""


def handler_for(manifest_path: Path, models: list[str]):
    class AnnotationHandler(BaseHTTPRequestHandler):
        def send_json(self, payload: object, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def read_json(self) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("Request body must be an object.")
            return payload

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                body = ANNOTATION_HTML.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/api/manifest":
                with MANIFEST_LOCK:
                    payload = load_manifest(manifest_path)
                self.send_json({"records": flattened_records(payload), "models": models})
                return
            if parsed.path == "/image":
                record_id = parse_qs(parsed.query).get("id", [""])[0]
                try:
                    with MANIFEST_LOCK:
                        _, record = find_record(load_manifest(manifest_path), record_id)
                    relative = Path(str(record["image"]))
                    image_path = relative if relative.is_absolute() else manifest_path.parent / relative
                    image_path = image_path.resolve()
                    image_path.relative_to(manifest_path.parent.resolve())
                    body = image_path.read_bytes()
                except (KeyError, OSError, ValueError):
                    self.send_json({"error": "Image not found."}, 404)
                    return
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mimetypes.guess_type(image_path.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_json({"error": "Not found."}, 404)

        def do_POST(self) -> None:  # noqa: N802
            try:
                submitted = self.read_json()
                if self.path == "/api/record":
                    with MANIFEST_LOCK:
                        payload = load_manifest(manifest_path)
                        record = update_record(payload, submitted)
                        write_manifest(manifest_path, payload)
                    response = dict(record)
                    response["ingredient_text"] = entries_to_ingredient_text(record.get("ingredients", []))
                    self.send_json(response)
                    return
                if self.path == "/api/prelabel":
                    with MANIFEST_LOCK:
                        payload = load_manifest(manifest_path)
                        _, record = find_record(payload, str(submitted.get("id", "")))
                    drafts = prelabel_record(record, manifest_path, models)
                    with MANIFEST_LOCK:
                        fresh_payload = load_manifest(manifest_path)
                        _, fresh_record = find_record(fresh_payload, str(submitted.get("id", "")))
                        fresh_record["draft_predictions"] = drafts
                        fresh_record["updated_at"] = utc_now()
                        write_manifest(manifest_path, fresh_payload)
                    self.send_json({"draft_predictions": drafts})
                    return
                if self.path == "/api/reveal":
                    with MANIFEST_LOCK:
                        payload = load_manifest(manifest_path)
                        split, record = find_record(payload, str(submitted.get("id", "")))
                        if split == "test" and record.get("annotation_status") != "verified":
                            raise ValueError("Verify the independent test label before revealing drafts.")
                        record["draft_revealed"] = True
                        record["updated_at"] = utc_now()
                        write_manifest(manifest_path, payload)
                    self.send_json({"draft_revealed": True})
                    return
                self.send_json({"error": "Not found."}, 404)
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                self.send_json({"error": str(exc)}, 400)
            except Exception as exc:  # keep the local labeller responsive
                self.send_json({"error": str(exc)}, 500)

        def log_message(self, format: str, *args: object) -> None:
            sys.stderr.write(f"[labeller] {format % args}\n")

    return AnnotationHandler


def prelabel_split(manifest_path: Path, split: str, models: list[str]) -> None:
    payload = load_manifest(manifest_path)
    selected_splits = ("development", "test") if split == "all" else (split,)
    total = sum(len(payload[name]) for name in selected_splits)
    completed = 0
    for split_name in selected_splits:
        for record in payload[split_name]:
            completed += 1
            print(f"[{completed}/{total}] {record['image']}")
            prelabel_record(record, manifest_path, models)
            write_manifest(manifest_path, payload)
    print("Draft predictions saved but not revealed or copied into ground truth.")


def exclude_records(manifest_path: Path, record_ids: list[str], reason: str) -> list[dict]:
    """Move records out of evaluation splits without deleting their evidence."""
    payload = load_manifest(manifest_path)
    payload.setdefault("excluded", [])
    excluded: list[dict] = []
    requested = set(record_ids)
    for split in ("development", "test"):
        retained = []
        for record in payload[split]:
            if record.get("id") not in requested:
                retained.append(record)
                continue
            copy = dict(record)
            copy["original_split"] = split
            copy["exclusion_reason"] = reason
            copy["excluded_at"] = utc_now()
            payload["excluded"].append(copy)
            excluded.append(copy)
            requested.remove(str(record.get("id")))
        payload[split] = retained
    if requested:
        raise ValueError("Unknown active record ids: " + ", ".join(sorted(requested)))
    write_manifest(manifest_path, payload)
    return excluded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    initialize = subparsers.add_parser("init", help="Scan an image folder and create/update a manifest")
    initialize.add_argument("--images-dir", type=Path, required=True)
    initialize.add_argument("--manifest", type=Path, required=True)
    initialize.add_argument("--development-fraction", type=float, default=0.25)
    initialize.add_argument("--seed", default="20260922")

    serve = subparsers.add_parser("serve", help="Start the local browser annotation interface")
    serve.add_argument("--manifest", type=Path, required=True)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--models", nargs="+", default=DEFAULT_MODELS)

    prelabel = subparsers.add_parser("prelabel", help="Generate hidden local Qwen drafts in batch")
    prelabel.add_argument("--manifest", type=Path, required=True)
    prelabel.add_argument("--split", choices=["development", "test", "all"], default="development")
    prelabel.add_argument("--models", nargs="+", default=DEFAULT_MODELS)

    exclude = subparsers.add_parser("exclude", help="Move records out of evaluation without deleting evidence")
    exclude.add_argument("--manifest", type=Path, required=True)
    exclude.add_argument("--ids", nargs="+", required=True)
    exclude.add_argument("--reason", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "init":
        result = initialize_manifest(
            args.images_dir,
            args.manifest,
            development_fraction=args.development_fraction,
            seed=args.seed,
        )
        print(json.dumps(result, indent=2))
        return
    manifest_path = args.manifest.resolve()
    if not manifest_path.exists():
        raise SystemExit(f"Manifest does not exist: {manifest_path}. Run the init command first.")
    if args.command == "prelabel":
        prelabel_split(manifest_path, args.split, args.models)
        return
    if args.command == "exclude":
        excluded = exclude_records(manifest_path, args.ids, args.reason)
        print(json.dumps({"excluded": [record["id"] for record in excluded]}, indent=2))
        return
    server = ThreadingHTTPServer((args.host, args.port), handler_for(manifest_path, args.models))
    print(f"MealMatch labeller: http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop. Photographs remain local.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
