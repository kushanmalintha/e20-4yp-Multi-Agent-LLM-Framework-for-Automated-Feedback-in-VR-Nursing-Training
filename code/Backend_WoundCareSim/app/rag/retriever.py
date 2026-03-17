import json
import logging
from typing import Any, Dict, List

from openai import AsyncOpenAI

from app.agents.agent_base import BaseAgent
from app.core.config import OPENAI_API_KEY, OPENAI_CHAT_MODEL, VECTOR_STORE_ID

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not configured")

if not VECTOR_STORE_ID:
    raise RuntimeError("VECTOR_STORE_ID not configured")

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY)


def _extract_materials(scenario_metadata: Dict[str, Any]) -> List[str]:
    materials = scenario_metadata.get("materials") or scenario_metadata.get("required_materials") or []
    if isinstance(materials, list):
        return [str(item).strip() for item in materials if str(item).strip()]
    if isinstance(materials, dict):
        extracted = []
        for key, value in materials.items():
            if isinstance(value, list):
                extracted.extend([f"{key}: {item}" for item in value if str(item).strip()])
            elif value:
                extracted.append(f"{key}: {value}")
        return extracted
    return [str(materials).strip()] if materials else []


def _extract_learning_objectives(scenario_metadata: Dict[str, Any], step: str) -> List[str]:
    objectives = scenario_metadata.get("learning_objectives") or scenario_metadata.get("conversation_points") or []
    if isinstance(objectives, list):
        return [str(item).strip() for item in objectives if str(item).strip()]
    if objectives:
        return [str(objectives).strip()]

    if step == "history":
        return [
            "Confirm identity",
            "Check allergies",
            "Assess pain",
            "Obtain relevant medical history",
            "Explain the wound-care procedure",
        ]

    if step == "cleaning_and_dressing":
        return [
            "Perform wound cleaning and dressing preparation safely",
            "Follow aseptic technique",
            "Complete prerequisite actions in the correct sequence",
        ]

    return []


def _extract_wound_type(scenario_metadata: Dict[str, Any]) -> str:
    wound_details = scenario_metadata.get("wound_details") or {}
    return (
        wound_details.get("wound_type")
        or wound_details.get("type")
        or scenario_metadata.get("wound_type")
        or ""
    )


def _extract_infection_considerations(clinical_context: Dict[str, Any]) -> List[str]:
    considerations: List[str] = []
    infection_risk = clinical_context.get("infection_risk")
    healing_risk = clinical_context.get("healing_risk")
    if infection_risk:
        considerations.append(f"infection risk: {infection_risk}")
    if healing_risk:
        considerations.append(f"healing risk: {healing_risk}")
    if "diabetes" in clinical_context.get("risk_factors", []):
        considerations.append("diabetes increases infection risk and delays wound healing")
    return considerations


def build_rag_context(
    *,
    scenario_metadata: Dict[str, Any],
    clinical_context: Dict[str, Any],
    step: str,
    transcript: str = "",
    action_events: List[Dict[str, Any]] | None = None,
    extra_focus: str = "",
) -> Dict[str, Any]:
    wound_details = scenario_metadata.get("wound_details") or {}
    patient_history = scenario_metadata.get("patient_history")
    if not isinstance(patient_history, dict):
        patient_history = {}
    action_events = action_events or []

    return {
        "scenario_title": scenario_metadata.get("title")
        or scenario_metadata.get("scenario_title")
        or scenario_metadata.get("scenario_id", ""),
        "learning_objectives": _extract_learning_objectives(scenario_metadata, step),
        "procedure_step": step,
        "materials_used": _extract_materials(scenario_metadata),
        "patient_risk_factors": clinical_context.get("risk_factors", []),
        "wound_type": _extract_wound_type(scenario_metadata),
        "wound_location": wound_details.get("location", ""),
        "wound_appearance": wound_details.get("appearance", ""),
        "infection_considerations": _extract_infection_considerations(clinical_context),
        "medical_history": patient_history.get("medical_history", []),
        "allergies": patient_history.get("allergies", []),
        "recent_transcript": transcript[-1200:] if transcript else "",
        "performed_actions": [event.get("action_type", "") for event in action_events if event.get("action_type")],
        "extra_focus": extra_focus,
    }


def get_fallback_rag_query(context: Dict[str, Any]) -> str:
    step = context.get("procedure_step", "")
    risk_factors = [str(item).lower() for item in context.get("patient_risk_factors", [])]
    title = context.get("scenario_title") or "wound care"
    wound_type = context.get("wound_type") or "wound"

    if step == "history":
        query = (
            f"nursing history taking guidelines for {title} {wound_type} "
            "identity allergies pain medical history procedure explanation"
        )
    elif step == "cleaning_and_dressing":
        query = (
            f"clinical guidelines for {title} {wound_type} wound cleaning dressing preparation "
            "hand hygiene aseptic technique sequence prerequisites"
        )
    else:
        query = f"nursing clinical guidelines for {title} {wound_type}"

    if "diabetes" in risk_factors:
        query += " diabetic patient infection risk delayed healing"

    return " ".join(query.split())


def _extract_response_text(response: Any) -> str:
    output_text = ""
    if hasattr(response, "output"):
        for item in response.output:
            if getattr(item, "type", None) == "message":
                for content_part in getattr(item, "content", []):
                    if getattr(content_part, "type", "") in ["text", "output_text"]:
                        text_val = getattr(content_part, "text", "")
                        if text_val:
                            output_text += text_val
    return output_text.strip()


def _extract_retrieved_document_titles(response: Any) -> List[str]:
    titles: List[str] = []

    if not hasattr(response, "output"):
        return titles

    for item in response.output:
        annotations = []
        if getattr(item, "type", None) == "message":
            for content_part in getattr(item, "content", []):
                annotations.extend(getattr(content_part, "annotations", []) or [])

        if getattr(item, "type", None) == "file_search_call":
            annotations.extend(getattr(item, "results", []) or [])

        for annotation in annotations:
            candidate = (
                getattr(annotation, "filename", None)
                or getattr(annotation, "title", None)
                or getattr(annotation, "file_name", None)
                or getattr(annotation, "document_title", None)
            )
            if candidate and candidate not in titles:
                titles.append(candidate)

    return titles


def _count_retrieved_chunks(response: Any, document_titles: List[str]) -> int:
    if hasattr(response, "output"):
        for item in response.output:
            if getattr(item, "type", None) == "file_search_call":
                results = getattr(item, "results", []) or []
                if results:
                    return len(results)
    return len(document_titles)


async def generate_rag_query(context: Dict[str, Any]) -> str:
    """
    Generate a retrieval query from scenario context using a HyDE-style paragraph.
    Falls back to a deterministic query if the LLM call fails.
    """
    fallback_query = get_fallback_rag_query(context)
    prompt = (
        "You generate retrieval text for a nursing-guideline vector store.\n"
        "Use the scenario context to write ONE compact hypothetical clinical guideline paragraph "
        "that will retrieve the most relevant documents.\n"
        "Emphasize the current procedure step, wound type, materials, risk factors, and infection concerns.\n"
        "Do not mention that this is hypothetical. Do not use markdown. Return only the paragraph.\n\n"
        f"Scenario context:\n{json.dumps(context, ensure_ascii=True, indent=2)}"
    )

    try:
        response = await client.responses.create(
            model=OPENAI_CHAT_MODEL,
            input=[
                {
                    "role": "system",
                    "content": "You optimize search inputs for nursing guideline retrieval.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )
        generated_query = _extract_response_text(response)
        if not generated_query or generated_query == "{}":
            raise ValueError("LLM returned empty query text")
        return generated_query
    except Exception as exc:
        logger.warning("Falling back to static RAG query: %s", exc)
        return fallback_query


async def retrieve_with_rag(
    query: str,
    scenario_id: str,
    system_instruction: str = "You are a nursing guideline retrieval assistant."
):
    """
    Perform RAG using OpenAI Responses API + managed Vector Store.

    - Stateless
    - File-first
    - No manual chunking
    - No top_k
    """

    try:
        logger.info("RAG query generated: %s", query)
        response = await client.responses.create(
            model=OPENAI_CHAT_MODEL,
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [VECTOR_STORE_ID]
                }
            ],
            input=[
                {
                    "role": "system",
                    "content": (
                        f"{system_instruction}\n"
                        f"CONSTRAINT: Use only information relevant to scenario_id={scenario_id}.\n"
                        f"Do NOT invent facts. If information is missing, say so."
                    )
                },
                {
                    "role": "user",
                    "content": query
                }
            ]
        )

        # -----------------------------
        # SAFE OUTPUT EXTRACTION
        # -----------------------------
        rag_text = _extract_response_text(response)
        document_titles = _extract_retrieved_document_titles(response)
        document_count = _count_retrieved_chunks(response, document_titles)
        logger.info("Retrieved chunks: %s", document_count)
        logger.info("Retrieved document titles: %s", document_titles)
        if not rag_text:
            logger.warning("RAG returned empty context")

        return {
            "text": rag_text,
            "raw_response": response,
            "query": query,
            "document_titles": document_titles,
            "document_count": document_count,
        }

    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        return {
            "text": "",
            "raw_response": None
        }


async def extract_prerequisite_map(
    rag_text: str,
    base_agent: BaseAgent
) -> dict[str, list[str]]:
    try:
        response = await base_agent.run(
            system_prompt=(
                "You are a clinical guideline parser.\n"
                "Extract the prerequisite map from the provided nursing guideline text.\n"
                "Return ONLY a valid JSON object. No markdown, no explanation,\n"
                "no code fences. Nothing else.\n"
                "Format:\n"
                "{\n"
                '  "action_key": ["prerequisite_action_key", ...],\n'
                "  ...\n"
                "}\n"
                "Rules:\n"
                "- Use exact action key names as they appear in the document\n"
                "  (e.g. action_initial_hand_hygiene)\n"
                "- If an action has no prerequisites, map it to an empty list []\n"
                "- Include ALL actions found in the document\n"
                "- Do NOT invent action keys not present in the document"
            ),
            user_prompt=rag_text,
            temperature=0.0,
        )
        parsed = json.loads(response)
        if isinstance(parsed, dict):
            return parsed
        logger.warning("extract_prerequisite_map() returned non-dict JSON. Falling back to empty map.")
        return {}
    except Exception as e:
        logger.warning(f"Failed to extract prerequisite map from RAG text: {e}")
        return {}
