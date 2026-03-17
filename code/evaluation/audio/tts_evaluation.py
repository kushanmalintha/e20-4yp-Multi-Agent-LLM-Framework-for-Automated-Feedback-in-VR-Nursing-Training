from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any

import librosa
from jiwer import wer

from app.services.groq_audio_service import GroqAudioService

from evaluation.audio.config import (
    CONSISTENCY_RESULTS_PATH,
    CONSISTENCY_RUNS,
    GENERATED_AUDIO_DIR,
    PROJECT_ROOT,
    TRANSCRIPTS_PATH,
    TTS_RESULTS_PATH,
    ensure_directories,
)
from evaluation.audio.metrics import average_round_trip_wer, summarize


def load_dataset() -> list[dict[str, Any]]:
    with TRANSCRIPTS_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def audio_duration_seconds(audio_path: Path) -> float:
    samples, sample_rate = librosa.load(audio_path, sr=None, mono=True)
    return float(len(samples) / sample_rate) if sample_rate else 0.0


async def generate_audio(audio_service: GroqAudioService, text: str, target_path: Path) -> tuple[float, Path]:
    start = time.perf_counter()
    payload = await audio_service.text_to_speech(text=text)
    latency = time.perf_counter() - start
    target_path.write_bytes(base64.b64decode(payload["audio_base64"]))
    return latency, target_path


async def round_trip_stt(audio_service: GroqAudioService, audio_path: Path) -> tuple[str, float]:
    start = time.perf_counter()
    prediction = await audio_service.transcribe_audio(
        filename=audio_path.name,
        content=audio_path.read_bytes(),
        content_type="audio/wav",
    )
    latency = time.perf_counter() - start
    return prediction, latency


async def run_tts_evaluation() -> dict[str, Any]:
    ensure_directories()
    dataset = load_dataset()
    audio_service = GroqAudioService()

    results = []
    for sample in dataset:
        output_path = GENERATED_AUDIO_DIR / f"{sample['id']}.wav"
        tts_latency, audio_path = await generate_audio(audio_service, sample["text"], output_path)
        prediction, stt_latency = await round_trip_stt(audio_service, audio_path)
        duration = audio_duration_seconds(audio_path)
        results.append(
            {
                "id": sample["id"],
                "text": sample["text"],
                "text_length": len(sample["text"]),
                "audio_file": str(audio_path.relative_to(PROJECT_ROOT)),
                "tts_latency": tts_latency,
                "round_trip_stt_latency": stt_latency,
                "prediction": prediction,
                "round_trip_wer": wer(sample["text"], prediction),
                "duration_seconds": duration,
            }
        )

    consistency_text = dataset[0]["text"]
    durations = []
    consistency_runs = []
    for run_index in range(CONSISTENCY_RUNS):
        target_path = GENERATED_AUDIO_DIR / f"consistency_run_{run_index + 1}.wav"
        latency, audio_path = await generate_audio(audio_service, consistency_text, target_path)
        duration = audio_duration_seconds(audio_path)
        durations.append(duration)
        consistency_runs.append(
            {
                "run": run_index + 1,
                "text": consistency_text,
                "audio_file": str(audio_path.relative_to(PROJECT_ROOT)),
                "tts_latency": latency,
                "duration_seconds": duration,
            }
        )

    consistency_payload = {
        "text": consistency_text,
        "runs": consistency_runs,
        "duration_variance": (max(durations) - min(durations)) if durations else 0.0,
        "duration_summary": summarize(durations),
    }
    save_json(CONSISTENCY_RESULTS_PATH, consistency_payload)

    payload = {
        "dataset_size": len(dataset),
        "results": results,
        "summary": {
            "tts_latency": summarize(entry["tts_latency"] for entry in results),
            "round_trip_stt_latency": summarize(entry["round_trip_stt_latency"] for entry in results),
            "average_round_trip_wer": average_round_trip_wer(results),
        },
    }
    save_json(TTS_RESULTS_PATH, payload)
    return {"tts": payload, "consistency": consistency_payload}


if __name__ == "__main__":
    asyncio.run(run_tts_evaluation())
