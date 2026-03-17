from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "Backend_WoundCareSim"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DATASET_DIR = PROJECT_ROOT / "evaluation" / "audio" / "dataset"
STT_SAMPLES_DIR = DATASET_DIR / "stt_samples"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "audio" / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
GENERATED_AUDIO_DIR = RESULTS_DIR / "generated_audio"
NOISY_AUDIO_DIR = RESULTS_DIR / "noisy_audio"
TRANSCRIPTS_PATH = DATASET_DIR / "transcripts.json"
STT_RESULTS_PATH = RESULTS_DIR / "stt_results.json"
TTS_RESULTS_PATH = RESULTS_DIR / "tts_results.json"
CONSISTENCY_RESULTS_PATH = RESULTS_DIR / "tts_consistency.json"
AUDIO_SUMMARY_PATH = RESULTS_DIR / "summary.json"

DEFAULT_STT_SAMPLE_RATE = 16000
NOISE_CONDITIONS = {
    "clean": None,
    "moderate_noise": -18,
    "heavy_noise": -8,
}
CONSISTENCY_RUNS = 5


def ensure_directories() -> None:
    STT_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    NOISY_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def require_audio_env() -> None:
    missing = [name for name in ("GROQ_API_KEY",) if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
