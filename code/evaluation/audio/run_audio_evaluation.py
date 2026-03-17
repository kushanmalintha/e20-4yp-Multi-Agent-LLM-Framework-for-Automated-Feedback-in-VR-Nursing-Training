from __future__ import annotations

import asyncio
import json

from evaluation.audio.config import AUDIO_SUMMARY_PATH, FIGURES_DIR, require_audio_env
from evaluation.audio.metrics import average_round_trip_wer, average_wer
from evaluation.audio.stt_evaluation import run_stt_evaluation
from evaluation.audio.tts_evaluation import run_tts_evaluation
from evaluation.audio.visualize_results import main as generate_figures


def save_json(path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


async def main() -> None:
    require_audio_env()
    stt_results = await run_stt_evaluation()
    tts_payload = await run_tts_evaluation()
    tts_results = tts_payload["tts"]
    consistency_results = tts_payload["consistency"]

    summary = {
        "stt_average_wer": average_wer(stt_results["clean_results"]),
        "stt_latency_p50": stt_results["summary"]["clean_latency"]["p50"],
        "stt_latency_p95": stt_results["summary"]["clean_latency"]["p95"],
        "tts_latency_p50": tts_results["summary"]["tts_latency"]["p50"],
        "tts_latency_p95": tts_results["summary"]["tts_latency"]["p95"],
        "tts_round_trip_wer": average_round_trip_wer(tts_results["results"]),
        "tts_duration_variance": consistency_results["duration_variance"],
    }
    save_json(AUDIO_SUMMARY_PATH, summary)
    generate_figures()

    print("====================================")
    print("Audio Evaluation Results")
    print("====================================")
    print(f"STT Average WER: {summary['stt_average_wer']:.2f}")
    print(f"STT Latency P50: {summary['stt_latency_p50']:.2f} s")
    print(f"STT Latency P95: {summary['stt_latency_p95']:.2f} s")
    print("")
    print(f"TTS Latency P50: {summary['tts_latency_p50']:.2f} s")
    print(f"TTS Latency P95: {summary['tts_latency_p95']:.2f} s")
    print(f"TTS Round-trip WER: {summary['tts_round_trip_wer']:.2f}")
    print("")
    print("Charts saved to:")
    print(FIGURES_DIR)
    print("====================================")


if __name__ == "__main__":
    asyncio.run(main())
