from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from evaluation.audio.config import CONSISTENCY_RESULTS_PATH, FIGURES_DIR, STT_RESULTS_PATH, TTS_RESULTS_PATH


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def plot_stt_wer_per_sample(stt_results: dict) -> None:
    df = pd.DataFrame(stt_results["clean_results"])
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=df, x="id", y="wer", ax=ax, color="#2a9d8f")
    ax.set_title("STT WER per Audio Sample")
    ax.set_ylabel("WER")
    ax.set_xlabel("Sample ID")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "stt_wer_per_sample.png")
    plt.close(fig)


def plot_stt_latency_distribution(stt_results: dict) -> None:
    df = pd.DataFrame(stt_results["clean_results"])
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.histplot(df["latency"], bins=min(10, len(df)), kde=True, ax=ax, color="#e9c46a")
    ax.set_title("STT Latency Distribution")
    ax.set_xlabel("Latency (s)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "stt_latency_distribution.png")
    plt.close(fig)


def plot_noise_robustness(stt_results: dict) -> None:
    clean_df = pd.DataFrame(stt_results["clean_results"])[["id", "wer"]].assign(condition="clean")
    noise_df = pd.DataFrame(stt_results["noise_results"])[["id", "wer", "condition"]]
    combined = pd.concat([clean_df, noise_df], ignore_index=True)

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=combined, x="id", y="wer", hue="condition", ax=ax)
    ax.set_title("STT Noise Robustness Comparison")
    ax.set_ylabel("WER")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "stt_noise_robustness.png")
    plt.close(fig)


def plot_tts_latency_vs_text_length(tts_results: dict) -> None:
    df = pd.DataFrame(tts_results["results"])
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.scatterplot(data=df, x="text_length", y="tts_latency", ax=ax, color="#264653", s=80)
    ax.set_title("TTS Latency vs Text Length")
    ax.set_xlabel("Text Length (characters)")
    ax.set_ylabel("TTS Latency (s)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "tts_latency_vs_text_length.png")
    plt.close(fig)


def plot_tts_round_trip_wer(tts_results: dict) -> None:
    df = pd.DataFrame(tts_results["results"])
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=df, x="id", y="round_trip_wer", ax=ax, color="#f4a261")
    ax.set_title("TTS Round-Trip WER")
    ax.set_ylabel("WER")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "tts_round_trip_wer.png")
    plt.close(fig)


def plot_tts_duration_variance(consistency_results: dict) -> None:
    df = pd.DataFrame(consistency_results["runs"])
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=df, x="run", y="duration_seconds", ax=ax, color="#e76f51")
    ax.set_title("TTS Duration Variance Across Repeated Synthesis")
    ax.set_ylabel("Duration (s)")
    ax.set_xlabel("Run")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "tts_duration_variance.png")
    plt.close(fig)


def main() -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    stt_results = load_json(STT_RESULTS_PATH)
    tts_results = load_json(TTS_RESULTS_PATH)
    consistency_results = load_json(CONSISTENCY_RESULTS_PATH)

    plot_stt_wer_per_sample(stt_results)
    plot_stt_latency_distribution(stt_results)
    plot_noise_robustness(stt_results)
    plot_tts_latency_vs_text_length(tts_results)
    plot_tts_round_trip_wer(tts_results)
    plot_tts_duration_variance(consistency_results)

    print("Charts saved to:")
    print(FIGURES_DIR)


if __name__ == "__main__":
    main()
