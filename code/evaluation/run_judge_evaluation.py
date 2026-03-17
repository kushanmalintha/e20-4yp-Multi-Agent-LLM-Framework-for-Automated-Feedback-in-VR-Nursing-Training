from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from statistics import mean
from typing import Any

from openai import AsyncOpenAI


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "Backend_WoundCareSim"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.feedback_narrator_agent import FeedbackNarratorAgent


DATASET_PATH = PROJECT_ROOT / "evaluation" / "golden_dataset.json"
RESULTS_DIR = PROJECT_ROOT / "evaluation" / "results"
AGENT_RESULTS_PATH = RESULTS_DIR / "agent_evaluation_results.json"
JUDGE_DIMENSIONS = [
    "clinical_accuracy",
    "educational_clarity",
    "completeness",
    "tone",
    "contextualization",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LLM-as-judge evaluation for FeedbackNarratorAgent.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--agent-results", type=Path, default=AGENT_RESULTS_PATH)
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--judge-model", type=str, default=os.getenv("OPENAI_JUDGE_MODEL", os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1")))
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_agent_results_by_id(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = load_json(path)
    return {case["id"]: case for case in payload.get("cases", [])}


def build_raw_feedback(case: dict[str, Any], agent_case: dict[str, Any] | None) -> list[dict[str, Any]]:
    predicted_flags = (agent_case or {}).get("majority_flags") or case["expected_flags"]
    communication_verdict = (agent_case or {}).get("majority_communication_verdict") or case["expected_communication_verdict"]

    strengths = []
    gaps = []
    label_map = {
        "identity_asked": "patient identity",
        "allergies_asked": "allergy history",
        "pain_assessed": "pain level",
        "medical_history_asked": "medical history",
        "procedure_explained": "procedure explanation",
        "risk_factor_assessed": "risk factors affecting healing",
    }
    for key, label in label_map.items():
        if predicted_flags.get(key):
            strengths.append(label)
        else:
            gaps.append(label)

    communication_text = f"Communication verdict: {communication_verdict}."
    if communication_verdict == "Appropriate":
        communication_text += " The learner used a professional and respectful tone."
    elif communication_verdict == "Partially Appropriate":
        communication_text += " The learner showed some professionalism but left room for improvement."
    else:
        communication_text += " The learner needs clearer, more patient-centered communication."

    knowledge_text = ""
    if strengths:
        knowledge_text += "Strengths: addressed " + ", ".join(strengths) + ". "
    if gaps:
        knowledge_text += "Areas for improvement: missed " + ", ".join(gaps) + "."

    return [
        {
            "text": communication_text.strip(),
            "speaker": "system",
            "category": "communication",
            "timing": "post_step",
        },
        {
            "text": knowledge_text.strip(),
            "speaker": "system",
            "category": "knowledge",
            "timing": "post_step",
        },
    ]


def calculate_score_hint(case: dict[str, Any], agent_case: dict[str, Any] | None) -> int:
    flags = (agent_case or {}).get("majority_flags") or case["expected_flags"]
    achieved = sum(1 for value in flags.values() if value)
    return round(achieved / len(flags) * 100)


async def judge_feedback(
    client: AsyncOpenAI,
    judge_model: str,
    case: dict[str, Any],
    narrated_feedback: str,
) -> dict[str, int]:
    transcript = "\n".join(case["transcript"])
    clinical_context = json.dumps(case.get("clinical_context", {}))
    system_prompt = (
        "You are grading nursing-education feedback quality.\n"
        "Return only valid JSON with integer scores from 1 to 5 for:\n"
        "- clinical_accuracy\n"
        "- educational_clarity\n"
        "- completeness\n"
        "- tone\n"
        "- contextualization\n"
        "Do not include explanations."
    )
    user_prompt = (
        f"Clinical context: {clinical_context}\n\n"
        f"Transcript:\n{transcript}\n\n"
        f"Feedback to judge:\n{narrated_feedback}\n"
    )

    response = await client.responses.create(
        model=judge_model,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    output_text = ""
    for item in getattr(response, "output", []):
        if getattr(item, "type", None) == "message":
            for part in getattr(item, "content", []):
                if getattr(part, "type", "") in {"text", "output_text"}:
                    output_text += getattr(part, "text", "")

    parsed = json.loads(output_text.replace("```json", "").replace("```", "").strip())
    return {
        key: max(1, min(5, int(parsed[key])))
        for key in JUDGE_DIMENSIONS
    }


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def plot_radar_chart(average_scores: dict[str, float], output_dir: Path) -> None:
    import math
    import matplotlib.pyplot as plt

    labels = JUDGE_DIMENSIONS
    values = [average_scores[label] for label in labels]
    angles = [n / float(len(labels)) * 2 * math.pi for n in range(len(labels))]
    values += values[:1]
    angles += angles[:1]

    fig = plt.figure(figsize=(7, 7))
    ax = plt.subplot(111, polar=True)
    ax.plot(angles, values, linewidth=2, color="#2a9d8f")
    ax.fill(angles, values, color="#2a9d8f", alpha=0.25)
    ax.set_xticks(angles[:-1], labels)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_ylim(1, 5)
    ax.set_title("FeedbackNarratorAgent Judge Scores")
    fig.tight_layout()
    fig.savefig(output_dir / "judge_radar_chart.png")
    plt.close(fig)


async def main() -> None:
    args = parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required to run judge evaluation.")

    dataset = load_json(args.dataset)
    agent_results_by_id = load_agent_results_by_id(args.agent_results)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    narrator = FeedbackNarratorAgent()
    judge_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    case_outputs = []
    for case in dataset:
        agent_case = agent_results_by_id.get(case["id"])
        raw_feedback = build_raw_feedback(case, agent_case)
        narrated = await narrator.narrate(
            raw_feedback=raw_feedback,
            step="history",
            score=calculate_score_hint(case, agent_case),
            clinical_context=case.get("clinical_context", {}),
        )
        judge_scores = await judge_feedback(
            client=judge_client,
            judge_model=args.judge_model,
            case=case,
            narrated_feedback=narrated.message_text,
        )
        case_outputs.append(
            {
                "id": case["id"],
                "category": case.get("category"),
                "narrated_feedback": narrated.model_dump(),
                "judge_scores": judge_scores,
            }
        )

    average_scores = {
        dimension: mean(case["judge_scores"][dimension] for case in case_outputs)
        for dimension in JUDGE_DIMENSIONS
    }
    payload = {
        "judge_model": args.judge_model,
        "dataset_size": len(dataset),
        "average_scores": average_scores,
        "cases": case_outputs,
    }
    save_json(args.output_dir / "judge_evaluation_results.json", payload)

    try:
        plot_radar_chart(average_scores, args.output_dir)
    except ModuleNotFoundError as exc:
        print(f"Plot generation skipped: {exc}. Install matplotlib to produce figures.")

    print("=====================================")
    for dimension in JUDGE_DIMENSIONS:
        print(f"{dimension}: {average_scores[dimension]:.2f}")
    print("=====================================")


if __name__ == "__main__":
    asyncio.run(main())
