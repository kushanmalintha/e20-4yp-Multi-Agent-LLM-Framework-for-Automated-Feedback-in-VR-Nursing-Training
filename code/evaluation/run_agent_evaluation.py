from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "Backend_WoundCareSim"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.communication_agent import CommunicationAgent
from app.agents.knowledge_agent import KnowledgeAgent

from evaluation.metrics import (
    binary_classification_metrics,
    confusion_matrix,
    consistency_rate,
    majority_vote,
    verdict_accuracy,
)


DATASET_PATH = PROJECT_ROOT / "evaluation" / "golden_dataset.json"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
VERDICTS = ["Appropriate", "Partially Appropriate", "Inappropriate"]
RUBRIC_FLAGS = [
    "identity_asked",
    "allergies_asked",
    "pain_assessed",
    "medical_history_asked",
    "procedure_explained",
    "risk_factor_assessed",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run golden-set evaluation for KnowledgeAgent and CommunicationAgent.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    return parser.parse_args()


def load_dataset(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def format_transcript(turns: list[str]) -> str:
    formatted = []
    for line in turns:
        clean = line.strip()
        lower = clean.lower()
        if lower.startswith(("student:", "patient:", "nurse:", "system:")):
            formatted.append(clean)
        else:
            formatted.append(f"student: {clean}")
    return "\n".join(formatted)


def build_scenario_metadata(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": "Golden Evaluation Scenario",
        "patient_history": "Synthetic history-taking evaluation case.",
        "assessment_questions": [],
        "clinical_context": case.get("clinical_context", {}),
        "conversation_points": [],
    }


def signature_from_outputs(flags: dict[str, bool], verdict: str) -> str:
    flag_bits = "|".join(f"{key}:{int(bool(flags.get(key, False)))}" for key in RUBRIC_FLAGS)
    return f"{flag_bits}|verdict:{verdict}"


async def evaluate_case(
    case: dict[str, Any],
    knowledge_agent: KnowledgeAgent,
    communication_agent: CommunicationAgent,
    runs: int,
) -> dict[str, Any]:
    transcript = format_transcript(case["transcript"])
    scenario_metadata = build_scenario_metadata(case)
    rag_response = case.get("rag_response", "History-taking and communication guidance for wound-care nursing.")
    clinical_context = case.get("clinical_context", {})

    run_outputs = []
    for _ in range(runs):
        knowledge_output = await knowledge_agent.evaluate(
            current_step="history",
            student_input=transcript,
            scenario_metadata=scenario_metadata,
            rag_response=rag_response,
            clinical_context=clinical_context,
        )
        communication_output = await communication_agent.evaluate(
            current_step="history",
            student_input=transcript,
            scenario_metadata=scenario_metadata,
            rag_response=rag_response,
            clinical_context=clinical_context,
        )
        flags = dict(knowledge_output.metadata or {})
        run_outputs.append(
            {
                "flags": {key: bool(flags.get(key, False)) for key in RUBRIC_FLAGS},
                "knowledge_confidence": knowledge_output.confidence,
                "knowledge_verdict": knowledge_output.verdict,
                "communication_verdict": communication_output.verdict,
                "communication_confidence": communication_output.confidence,
            }
        )

    per_flag_majority = {
        key: mean(int(output["flags"].get(key, False)) for output in run_outputs) >= 0.5
        for key in RUBRIC_FLAGS
    }
    signatures = [
        signature_from_outputs(output["flags"], output["communication_verdict"])
        for output in run_outputs
    ]

    return {
        "id": case["id"],
        "category": case.get("category"),
        "expected_flags": case["expected_flags"],
        "expected_communication_verdict": case["expected_communication_verdict"],
        "clinical_context": clinical_context,
        "transcript": transcript,
        "runs": run_outputs,
        "majority_flags": per_flag_majority,
        "majority_communication_verdict": majority_vote(
            [output["communication_verdict"] for output in run_outputs]
        ),
        "case_consistency_rate": consistency_rate(signatures),
    }


def summarise_results(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    expected_flags_flat = []
    predicted_flags_flat = []
    expected_verdicts = []
    predicted_verdicts = []
    inconsistent_cases = []
    total_agreeing_runs = 0
    total_runs = 0

    for result in case_results:
        for flag in RUBRIC_FLAGS:
            expected_flags_flat.append(bool(result["expected_flags"].get(flag, False)))
            predicted_flags_flat.append(bool(result["majority_flags"].get(flag, False)))

        expected_verdicts.append(result["expected_communication_verdict"])
        predicted_verdicts.append(result["majority_communication_verdict"])

        signatures = [
            signature_from_outputs(run["flags"], run["communication_verdict"])
            for run in result["runs"]
        ]
        majority_signature = majority_vote(signatures)
        agreeing_runs = sum(1 for signature in signatures if signature == majority_signature)
        total_agreeing_runs += agreeing_runs
        total_runs += len(signatures)

        if result["case_consistency_rate"] < 1.0:
            inconsistent_cases.append(
                {
                    "id": result["id"],
                    "category": result.get("category"),
                    "consistency_rate": round(result["case_consistency_rate"], 3),
                    "majority_communication_verdict": result["majority_communication_verdict"],
                }
            )

    knowledge_metrics = binary_classification_metrics(expected_flags_flat, predicted_flags_flat)
    communication_accuracy = verdict_accuracy(expected_verdicts, predicted_verdicts)

    return {
        "knowledge_metrics": knowledge_metrics,
        "communication_accuracy": communication_accuracy,
        "communication_confusion_matrix": {
            "labels": VERDICTS,
            "matrix": confusion_matrix(expected_verdicts, predicted_verdicts, VERDICTS),
        },
        "overall_consistency_rate": total_agreeing_runs / total_runs if total_runs else 0.0,
        "inconsistent_cases": inconsistent_cases,
    }


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def plot_knowledge_metrics(metrics_payload: dict[str, float], output_dir: Path) -> None:
    import matplotlib.pyplot as plt

    labels = ["Precision", "Recall", "F1"]
    values = [
        metrics_payload["precision"],
        metrics_payload["recall"],
        metrics_payload["f1"],
    ]

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(labels, values, color=["#2a9d8f", "#e9c46a", "#f4a261"])
    ax.set_ylim(0, 1)
    ax.set_ylabel("Score")
    ax.set_title("KnowledgeAgent Golden-Set Metrics")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.2f}", ha="center")
    fig.tight_layout()
    fig.savefig(output_dir / "knowledge_metrics_bar.png")
    plt.close(fig)


def plot_confusion_matrix(matrix_payload: dict[str, Any], output_dir: Path) -> None:
    import matplotlib.pyplot as plt

    labels = matrix_payload["labels"]
    matrix = matrix_payload["matrix"]

    fig, ax = plt.subplots(figsize=(7, 5))
    image = ax.imshow(matrix, cmap="Blues")
    ax.set_xticks(range(len(labels)), labels=labels, rotation=20, ha="right")
    ax.set_yticks(range(len(labels)), labels=labels)
    ax.set_xlabel("Predicted Verdict")
    ax.set_ylabel("Expected Verdict")
    ax.set_title("CommunicationAgent Confusion Matrix")
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            ax.text(j, i, str(value), ha="center", va="center", color="#111111")
    fig.colorbar(image, ax=ax)
    fig.tight_layout()
    fig.savefig(output_dir / "communication_confusion_matrix.png")
    plt.close(fig)


async def main() -> None:
    args = parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required to run agent evaluation.")

    dataset = load_dataset(args.dataset)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    knowledge_agent = KnowledgeAgent()
    communication_agent = CommunicationAgent()

    case_results = []
    for case in dataset:
        case_results.append(await evaluate_case(case, knowledge_agent, communication_agent, args.runs))

    summary = summarise_results(case_results)
    payload = {
        "dataset_size": len(dataset),
        "runs_per_case": args.runs,
        "summary": summary,
        "cases": case_results,
    }
    save_json(args.output_dir / "agent_evaluation_results.json", payload)

    try:
        plot_knowledge_metrics(summary["knowledge_metrics"], args.output_dir)
        plot_confusion_matrix(summary["communication_confusion_matrix"], args.output_dir)
    except ModuleNotFoundError as exc:
        print(f"Plot generation skipped: {exc}. Install matplotlib to produce figures.")

    knowledge = summary["knowledge_metrics"]
    print("=====================================")
    print(f"KnowledgeAgent Precision: {knowledge['precision']:.2f}")
    print(f"KnowledgeAgent Recall: {knowledge['recall']:.2f}")
    print(f"KnowledgeAgent F1: {knowledge['f1']:.2f}")
    print(f"CommunicationAgent Accuracy: {summary['communication_accuracy']:.2f}")
    print(f"Consistency Rate: {summary['overall_consistency_rate'] * 100:.0f}%")
    if summary["inconsistent_cases"]:
        ids = ", ".join(case["id"] for case in summary["inconsistent_cases"])
        print(f"Inconsistent Cases: {ids}")
    print("=====================================")


if __name__ == "__main__":
    asyncio.run(main())
