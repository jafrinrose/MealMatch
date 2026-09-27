"""Exact versions of every pretrained model MealMatch uses.

The evaluation results in docs/ were measured with these versions. Ollama tags
such as `qwen2.5vl:3b` can be republished upstream, so setup_models.py checks
each installed model against the digest recorded here. Hugging Face models are
downloaded at a fixed commit into MODEL_CACHE, which Git ignores.
"""

from pathlib import Path

MODEL_CACHE = Path(__file__).resolve().parent / ".model_cache"

# Ollama release the evaluations and timings were run on.
TESTED_OLLAMA_VERSION = "0.30.10"

# Ollama tag -> manifest digest, as shown by `ollama list` (first 12 characters)
# and /api/tags.
OLLAMA_MODELS = {
    "llama3.2:3b": "a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72",
    "qwen2.5vl:3b": "fb90415cde1ef08aa669ae74b082d49b158729b6db1ab183c941417d507e71a1",
}

# faster-whisper size -> commit of its Systran/faster-whisper-<size> repository.
WHISPER_REVISIONS = {
    "small.en": "d1d751a5f8271d482d14ca55d9e2deeebbae577f",
}

# Sentence embedding model for semantic recipe matching (recommender.py).
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
