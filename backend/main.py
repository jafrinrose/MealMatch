"""MealMatch API: start-up, model warm-up and the health check.

The routes for each part of the app are in routers/.
"""

import os
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from ai_services import OLLAMA_MODEL, OLLAMA_URL
from database import SessionLocal, get_db
from model_services import (
    OLLAMA_CHAT_URL,
    VISION_LANGUAGE_MODEL_NAME,
    WHISPER_MODEL_NAME,
    get_speech_model,
    speech_model_available,
)
from model_versions import EMBEDDING_MODEL
from models import User, upgrade_database
from ocr_services import find_tesseract
from ollama_server import ensure_running, full_tag, installed_models
from recipe_store import browsable_recipes
from recommender import build_faiss_index, get_embedding_model
from routers import cooking, pantry, preferences, recipes, scanning, shopping

upgrade_database()


def warm_models() -> None:
    """Get every model ready in the background, so the first request does not wait.

    Starts a local Ollama server if it is not running, loads the recipe-matching
    model and its recipe index, and loads Whisper. A failure here never stops
    the server: the feature then reports it when used, and /health says why.
    """
    ensure_running(OLLAMA_URL)
    db = SessionLocal()
    try:
        build_faiss_index(browsable_recipes(db))
    except Exception as error:
        print(f"Recipe-matching warm-up skipped: {error}")
    finally:
        db.close()
    try:
        get_speech_model()
    except Exception as error:
        print(f"Whisper warm-up skipped: {error}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.getenv("MEALMATCH_WARM_MODELS", "1") == "1":
        threading.Thread(target=warm_models, name="model-warm-up", daemon=True).start()
    yield


app = FastAPI(title="MealMatch API", lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


for area in (recipes, pantry, preferences, cooking, shopping, scanning):
    app.include_router(area.router)


@app.get("/")
def root():
    return {"message": "MealMatch API is running"}


@app.get("/health")
def health():
    """Which AI features can run now, and what to do about any that cannot.

    A local Ollama server that is down is started first, so a reload of the
    app is enough to recover once Ollama has been installed.
    """
    try:
        find_tesseract()
        tesseract_ready = True
    except RuntimeError:
        tesseract_ready = False

    def ollama_check(model: str, endpoint: str) -> tuple[bool, str]:
        if not ensure_running(endpoint):
            return False, "Ollama is not running. Install it from ollama.com or start it with 'ollama serve'."
        if full_tag(model) not in installed_models(endpoint):
            return False, f"Run 'ollama pull {model}'."
        return True, ""

    text_ready, text_fix = ollama_check(OLLAMA_MODEL, OLLAMA_URL)
    vision_ready, vision_fix = ollama_check(VISION_LANGUAGE_MODEL_NAME, OLLAMA_CHAT_URL)
    setup_fix = "Run 'python backend/setup_models.py' to download it."
    features = [
        {"feature": "Recipe ideas, the assistant and receipt names", "model": OLLAMA_MODEL, "ready": text_ready, "fix": text_fix},
        {"feature": "Pantry photos", "model": VISION_LANGUAGE_MODEL_NAME, "ready": vision_ready, "fix": vision_fix},
        {"feature": "Voice commands", "model": f"Whisper {WHISPER_MODEL_NAME}", "ready": speech_model_available(), "fix": setup_fix},
        {"feature": "Recipe matching", "model": EMBEDDING_MODEL.split("/")[-1], "ready": get_embedding_model() is not None, "fix": setup_fix},
        {"feature": "Receipt scanning", "model": "Tesseract OCR", "ready": tesseract_ready, "fix": "Install Tesseract (for example 'brew install tesseract')."},
    ]
    for feature in features:
        if feature["ready"]:
            feature["fix"] = ""
    return {"ready": all(feature["ready"] for feature in features), "features": features}


@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    return db.query(User).all()
