"""Adding food by photo, receipt or voice, and recording how the cook confirmed what was found."""

import json
import os
import shutil
import threading
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ai_services import extract_receipt_items
from database import SessionLocal, get_db
from model_services import (
    VISION_LANGUAGE_MODEL_NAME,
    open_photo,
    scan_pantry_photo,
    transcribe_audio,
    vision_model_display_name,
    warm_vision_model,
)
from models import User, VisionScan
from ocr_services import RECEIPT_IMAGE_TYPES, extract_receipt_text
from pantry_store import normalize_ingredient_list, normalize_ingredient_name, save_or_update_pantry_item
from schemas import VerifyIngredientsRequest

router = APIRouter()

UPLOAD_DIR = str(Path(__file__).resolve().parent.parent / "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def save_uploaded_file(file: UploadFile, allowed_extensions: set[str]) -> tuple[str, str]:
    original_name = Path(file.filename or "upload").name
    extension = Path(original_name).suffix.lower()
    if extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Please upload one of: {', '.join(sorted(allowed_extensions))}.",
        )
    stored_name = f"{uuid4().hex}{extension}"
    file_path = os.path.join(UPLOAD_DIR, stored_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return original_name, file_path


def delete_upload(file_path: str) -> None:
    """Uploads are removed once read, so no photo, receipt or recording is kept."""
    with suppress(OSError):
        os.remove(file_path)


@router.post("/upload-image")
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    user_id: int = Form(default=1),
    db: Session = Depends(get_db),
):
    """Stream one JSON line per model pass: the whole photo, then any close-ups.

    Close-ups run here only when MEALMATCH_VISION_CLOSE_UPS=1; otherwise the
    user can ask for them with /upload-image/{scan_id}/close-ups.
    """
    if not db.query(User).filter(User.id == user_id).first():
        raise HTTPException(status_code=404, detail="User not found.")
    original_name, image = await read_uploaded_photo(file)
    scan = VisionScan(
        scan_id=uuid4().hex,
        user_id=user_id,
        source="photo",
        detector_model="",
        semantic_model=vision_model_display_name(VISION_LANGUAGE_MODEL_NAME),
        status="analysing",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(scan)
    db.commit()
    return StreamingResponse(
        stream_photo_scan(request, scan.scan_id, image, original_name),
        media_type="application/x-ndjson",
    )


@router.post("/upload-image/{scan_id}/close-ups")
async def look_closer(
    request: Request,
    scan_id: str,
    file: UploadFile = File(...),
    user_id: int = Form(default=1),
    db: Session = Depends(get_db),
):
    """Check four overlapping close-ups of a scanned photo, when the user asks.

    The browser sends the same photo again, so the server never keeps it.
    Only foods not already suggested are streamed.
    """
    scan = db.query(VisionScan).filter(VisionScan.scan_id == scan_id, VisionScan.user_id == user_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Photo scan record not found.")
    if scan.status not in {"awaiting_confirmation", "no_detections"}:
        raise HTTPException(status_code=409, detail="This scan can no longer be checked more closely.")
    if any(entry.get("pass", "").startswith("close-up") for entry in json.loads(scan.pass_log or "[]")):
        raise HTTPException(status_code=409, detail="This photo has already been checked more closely.")
    original_name, image = await read_uploaded_photo(file)
    return StreamingResponse(
        stream_photo_scan(request, scan_id, image, original_name, look_closer=True),
        media_type="application/x-ndjson",
    )


async def read_uploaded_photo(file: UploadFile):
    """Held in memory for the scan, so the photo is deleted before any model runs."""
    original_name, file_path = save_uploaded_file(file, {".jpg", ".jpeg", ".png", ".webp"})
    try:
        return original_name, await run_in_threadpool(open_photo, file_path)
    except OSError as error:
        raise HTTPException(status_code=400, detail="The image could not be read. Please try another photo.") from error
    finally:
        delete_upload(file_path)


async def stream_photo_scan(request: Request, scan_id: str, image, original_name: str, look_closer: bool = False):
    """Run the passes and record each one on the scan as it arrives.

    With look_closer, the whole photo was scanned by an earlier request: only
    the close-ups run, and their results are added to what that scan recorded.
    """
    def line(payload: dict) -> str:
        return json.dumps(payload) + "\n"

    db = SessionLocal()
    scan = db.query(VisionScan).filter(VisionScan.scan_id == scan_id).first()
    detections: list[dict] = json.loads(scan.initial_detections or "[]") if look_closer else []
    warnings: list[str] = json.loads(scan.warnings or "[]") if look_closer else []
    pass_log: list[dict] = json.loads(scan.pass_log or "[]") if look_closer else []
    earlier_ms = (scan.total_analysis_ms or 0) if look_closer else 0
    passes = scan_pantry_photo(image, earlier=list(detections) if look_closer else None)
    started = perf_counter()
    try:
        while True:
            try:
                result = await run_in_threadpool(next, passes, None)
            except Exception as error:
                # A failed close-up request leaves the whole-photo results usable.
                if not look_closer:
                    scan.status = "failed"
                    scan.failure_reason = str(error)[-2000:]
                    scan.inference_ms = round((perf_counter() - started) * 1000)
                    scan.analysis_completed_at = datetime.now(timezone.utc).isoformat()
                    db.commit()
                yield line({"type": "error", "detail": f"Pantry photo analysis failed: {error}"})
                return
            if result is None:
                break
            # Stop once the user has confirmed or left: later suggestions would
            # never be seen but would count as deletions.
            db.refresh(scan)
            if scan.status == "confirmed" or await request.is_disconnected():
                return
            elapsed_ms = round((perf_counter() - started) * 1000)
            detections += result["detections"]
            if result.get("error"):
                warnings.append(f"The {result['pass']} could not be checked.")
            # done_reason, output tokens and timing per pass, to spot cut-off or looping answers.
            pass_log.append({
                **{key: value for key, value in result.items() if key not in {"detections", "alternatives"}},
                "new": len(result["detections"]),
                "elapsed_ms": elapsed_ms,
                "requested_by_user": look_closer,
            })
            if result["pass_number"] == 1:
                scan.inference_ms = elapsed_ms
                scan.analysis_completed_at = datetime.now(timezone.utc).isoformat()
            scan.status = "awaiting_confirmation" if detections else "no_detections"
            scan.initial_detections = json.dumps(detections)
            scan.initial_count = len(detections)
            scan.pass_log = json.dumps(pass_log)
            scan.total_analysis_ms = earlier_ms + elapsed_ms
            scan.warnings = json.dumps(warnings)
            db.commit()
            yield line({
                "type": "suggestions",
                "scan_id": scan_id,
                "filename": original_name,
                "pass": result["pass"],
                "pass_number": result["pass_number"],
                "passes": result["passes"],
                "detections": result["detections"],
                "alternatives": result["alternatives"],
                "analysis_ms": elapsed_ms,
            })
        yield line({"type": "done", "scan_id": scan_id, "total": len(detections), "warnings": warnings, "analysis_ms": scan.total_analysis_ms})
    finally:
        db.close()


@router.post("/vision/warmup")
def warm_up_vision():
    """Start loading the vision model while the user is still choosing a photo."""
    threading.Thread(target=warm_vision_model, daemon=True).start()
    return {"status": "warming"}


# A plain function, so FastAPI runs it in a worker thread: transcription takes
# seconds and, run on the event loop, it stopped every other request meanwhile.
@router.post("/transcribe-audio")
def transcribe_voice(file: UploadFile = File(...)):
    original_name, file_path = save_uploaded_file(
        file,
        {".webm", ".wav", ".mp3", ".m4a", ".mp4", ".ogg"},
    )
    try:
        result = transcribe_audio(file_path)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Whisper transcription failed: {str(error)}",
        ) from error
    finally:
        delete_upload(file_path)
    return {"filename": original_name, **result}


@router.post("/upload-receipt")
def upload_receipt(file: UploadFile = File(...)):
    original_name, file_path = save_uploaded_file(file, RECEIPT_IMAGE_TYPES)

    try:
        ocr_result = extract_receipt_text(file_path)
        raw_text_lines = ocr_result["raw_text_lines"]

        receipt = extract_receipt_items(raw_text_lines)

    except (ValueError, OSError) as error:
        # Not an image that can be opened (OSError covers unreadable image files).
        raise HTTPException(
            status_code=400,
            detail="The receipt image could not be read. Please try a clear JPG, PNG or WebP photo.",
        ) from error
    except Exception as error:
        # Tesseract missing or failing: the service, not the photo, is the problem.
        raise HTTPException(
            status_code=503,
            detail=f"Receipt processing failed: {str(error)}",
        ) from error
    finally:
        delete_upload(file_path)

    return {
        "filename": original_name,
        "raw_text_lines": raw_text_lines,
        "detections": receipt["detections"],
        "warnings": receipt["warnings"],
        "message": "Receipt scanned and interpreted successfully. Please verify detected ingredients before saving.",
    }


@router.post("/verify-ingredients/{user_id}")
def verify_ingredients(
    user_id: int,
    request: VerifyIngredientsRequest,
    db: Session = Depends(get_db),
):
    scan = None
    if request.scan_id:
        scan = (
            db.query(VisionScan)
            .filter(
                VisionScan.scan_id == request.scan_id,
                VisionScan.user_id == user_id,
            )
            .first()
        )
        if not scan:
            raise HTTPException(status_code=404, detail="Photo scan record not found.")
    verified_items = []
    seen = set()


    if request.items:
        for item in request.items:
            ingredient = normalize_ingredient_name(item.ingredient)
            quantity = item.quantity.strip()

            if ingredient and ingredient not in seen:
                verified_items.append({
                    "ingredient": ingredient,
                    "quantity": quantity,
                    "category": item.category.strip().lower() or "other",
                    "expiry_date": item.expiry_date.strip(),
                    "detection_id": item.detection_id,
                })
                seen.add(ingredient)


    else:
        verified_ingredients = normalize_ingredient_list(request.ingredients)

        for ingredient in verified_ingredients:
            if ingredient not in seen:
                verified_items.append({
                    "ingredient": ingredient,
                    "quantity": "",
                    "category": "other",
                    "expiry_date": "",
                    "detection_id": None,
                })
                seen.add(ingredient)

    saved_items = []

    for item in verified_items:
        saved_item = save_or_update_pantry_item(
            db=db,
            user_id=user_id,
            ingredient=item["ingredient"],
            quantity=item["quantity"],
            category=item["category"],
            expiry_date=item["expiry_date"],
        )

        if saved_item:
            saved_items.append(saved_item)

    study_metrics = None
    if scan:
        try:
            initial_items = json.loads(scan.initial_detections or "[]")
        except json.JSONDecodeError:
            initial_items = []
        initial_by_id = {
            str(item.get("detection_id")): item
            for item in initial_items
            if item.get("detection_id")
        }
        final_by_id = {
            str(item.get("detection_id")): item
            for item in verified_items
            if item.get("detection_id") and str(item.get("detection_id")) in initial_by_id
        }
        additions = sum(
            1
            for item in verified_items
            if not item.get("detection_id") or str(item.get("detection_id")) not in initial_by_id
        )
        deletions = len(set(initial_by_id) - set(final_by_id))
        renames = sum(
            normalize_ingredient_name(initial_by_id[detection_id].get("ingredient", ""))
            != normalize_ingredient_name(item.get("ingredient", ""))
            for detection_id, item in final_by_id.items()
        )
        confirmed_at = datetime.now(timezone.utc)
        try:
            review_started = datetime.fromisoformat(scan.analysis_completed_at)
            confirmation_ms = max(0, round((confirmed_at - review_started).total_seconds() * 1000))
        except (TypeError, ValueError):
            confirmation_ms = 0
        scan.status = "confirmed"
        scan.confirmed_at = confirmed_at.isoformat()
        scan.confirmation_ms = confirmation_ms
        scan.final_items = json.dumps(verified_items)
        scan.final_count = len(verified_items)
        scan.additions = additions
        scan.deletions = deletions
        scan.renames = renames
        scan.user_confidence = request.user_confidence
        db.commit()
        study_metrics = {
            "additions": additions,
            "deletions": deletions,
            "renames": renames,
            "confirmation_ms": confirmation_ms,
            "user_confidence": request.user_confidence,
        }

    return {
        "message": "Ingredients saved to your pantry.",
        "verified_items": verified_items,
        "saved_items": saved_items,
        "study_metrics": study_metrics,
    }


@router.get("/vision-study/{user_id}/summary")
def vision_study_summary(user_id: int, db: Session = Depends(get_db)):
    scans = db.query(VisionScan).filter(VisionScan.user_id == user_id).all()
    confirmed = [scan for scan in scans if scan.status == "confirmed"]
    failures = [
        scan
        for scan in scans
        if scan.status == "failed" or scan.initial_count == 0
    ]

    def average(values: list[int]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    confidence_values = [
        scan.user_confidence for scan in confirmed if scan.user_confidence is not None
    ]
    return {
        "total_scans": len(scans),
        "confirmed_scans": len(confirmed),
        "failure_count": len(failures),
        "failure_rate": round(len(failures) / len(scans), 4) if scans else 0.0,
        "average_confirmation_seconds": round(
            average([scan.confirmation_ms for scan in confirmed]) / 1000, 2
        ),
        "average_user_confidence": average(confidence_values),
        "total_additions": sum(scan.additions for scan in confirmed),
        "total_deletions": sum(scan.deletions for scan in confirmed),
        "total_renames": sum(scan.renames for scan in confirmed),
        "scans": [
            {
                "scan_id": scan.scan_id,
                "status": scan.status,
                "created_at": scan.created_at,
                "inference_ms": scan.inference_ms,
                "total_analysis_ms": scan.total_analysis_ms,
                "confirmation_ms": scan.confirmation_ms,
                "initial_count": scan.initial_count,
                "final_count": scan.final_count,
                "additions": scan.additions,
                "deletions": scan.deletions,
                "renames": scan.renames,
                "user_confidence": scan.user_confidence,
                "failure_reason": scan.failure_reason,
                "warnings": json.loads(scan.warnings or "[]"),
                "passes": json.loads(scan.pass_log or "[]"),
                "looked_closer": any(entry.get("requested_by_user") for entry in json.loads(scan.pass_log or "[]")),
            }
            for scan in sorted(scans, key=lambda item: item.id, reverse=True)
        ],
    }
