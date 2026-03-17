from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any

import librosa
import numpy as np
import soundfile as sf
from jiwer import wer

from app.services.groq_audio_service import GroqAudioService

from evaluation.audio.config import (
    DEFAULT_STT_SAMPLE_RATE,
    NOISE_CONDITIONS,
    NOISY_AUDIO_DIR,
    PROJECT_ROOT,
    RESULTS_DIR,
    STT_RESULTS_PATH,
    STT_SAMPLES_DIR,
    TRANSCRIPTS_PATH,
    ensure_directories,
)
from evaluation.audio.metrics import average_wer, summarize


def load_dataset() -> list[dict[str, Any]]:
    with TRANSCRIPTS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


async def ensure_clean_audio_dataset(dataset: list[dict[str, Any]], audio_service: GroqAudioService) -> None:
    for sample in dataset:
        audio_path = STT_SAMPLES_DIR / Path(sample["audio_file"]).name
        if audio_path.exists():
            continue
        tts_payload = await audio_service.text_to_speech(text=sample["text"])
        audio_bytes = base64.b64decode(tts_payload["audio_base64"])
        audio_path.write_bytes(audio_bytes)


def create_noisy_audio(source_path: Path, condition: str) -> Path:
    target_path = NOISY_AUDIO_DIR / condition / source_path.name
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if condition == "clean":
        target_path.write_bytes(source_path.read_bytes())
        return target_path

    audio, sample_rate = librosa.load(source_path, sr=DEFAULT_STT_SAMPLE_RATE, mono=True)
    rms = np.sqrt(np.mean(np.square(audio))) if len(audio) else 0.0
    scale = 10 ** (NOISE_CONDITIONS[condition] / 20)
    noise = np.random.normal(0.0, max(rms * scale, 1e-4), size=audio.shape)
    noisy = np.clip(audio + noise, -1.0, 1.0)
    sf.write(target_path, noisy, sample_rate)
    return target_path


async def transcribe_file(audio_service: GroqAudioService, audio_path: Path) -> tuple[str, float]:
    start = time.perf_counter()
    prediction = await audio_service.transcribe_audio(
        filename=audio_path.name,
        content=audio_path.read_bytes(),
        content_type="audio/wav",
    )
    latency = time.perf_counter() - start
    return prediction, latency


def compute_duration_seconds(audio_path: Path) -> float:
    samples, sample_rate = librosa.load(audio_path, sr=None, mono=True)
    return float(len(samples) / sample_rate) if sample_rate else 0.0


async def run_stt_evaluation() -> dict[str, Any]:
    ensure_directories()
    dataset = load_dataset()
    audio_service = GroqAudioService()
    await ensure_clean_audio_dataset(dataset, audio_service)

    sample_results = []
    noise_results = []

    for sample in dataset:
        clean_audio_path = STT_SAMPLES_DIR / Path(sample["audio_file"]).name
        ground_truth = sample["text"]

        prediction, latency = await transcribe_file(audio_service, clean_audio_path)
        sample_results.append(
            {
                "id": sample["id"],
                "condition": "clean",
                "audio_file": str(clean_audio_path.relative_to(PROJECT_ROOT)),
                "ground_truth": ground_truth,
                "prediction": prediction,
                "wer": wer(ground_truth, prediction),
                "latency": latency,
                "duration_seconds": compute_duration_seconds(clean_audio_path),
            }
        )

        for condition in ("moderate_noise", "heavy_noise"):
            noisy_path = create_noisy_audio(clean_audio_path, condition)
            noisy_prediction, noisy_latency = await transcribe_file(audio_service, noisy_path)
            noise_results.append(
                {
                    "id": sample["id"],
                    "condition": condition,
                    "audio_file": str(noisy_path.relative_to(PROJECT_ROOT)),
                    "ground_truth": ground_truth,
                    "prediction": noisy_prediction,
                    "wer": wer(ground_truth, noisy_prediction),
                    "latency": noisy_latency,
                    "duration_seconds": compute_duration_seconds(noisy_path),
                }
            )

    summary = {
        "clean_average_wer": average_wer(sample_results),
        "clean_latency": summarize(entry["latency"] for entry in sample_results),
        "noise_conditions": {
            condition: {
                "average_wer": average_wer([entry for entry in noise_results if entry["condition"] == condition]),
                "latency": summarize(entry["latency"] for entry in noise_results if entry["condition"] == condition),
            }
            for condition in ("moderate_noise", "heavy_noise")
        },
    }
    payload = {
        "dataset_size": len(dataset),
        "clean_results": sample_results,
        "noise_results": noise_results,
        "summary": summary,
    }
    save_json(STT_RESULTS_PATH, payload)
    return payload


if __name__ == "__main__":
    asyncio.run(run_stt_evaluation())
