from typing import Dict, List
from datetime import datetime


class ConversationManager:
    """
    Manages multi-turn conversation history per session and step.

    """

    def __init__(self):
        # session_id -> step -> list of turns
        self.conversations: Dict[str, Dict[str, List[Dict]]] = {}

    def add_turn(
        self,
        session_id: str,
        step: str,
        speaker: str,
        text: str
    ):
        if session_id not in self.conversations:
            self.conversations[session_id] = {}

        if step not in self.conversations[session_id]:
            self.conversations[session_id][step] = []

        self.conversations[session_id][step].append({
            "speaker": speaker,
            "text": text,
            "timestamp": datetime.now().isoformat()
        })

    def get_aggregated_transcript(
        self,
        session_id: str,
        step: str
    ) -> str:
        turns = self.conversations.get(session_id, {}).get(step, [])

        lines = []
        for t in turns:
            lines.append(f"{t['speaker']}: {t['text']}")

        return "\n".join(lines)

    def clear_step(self, session_id: str, step: str):
        if session_id in self.conversations:
            self.conversations[session_id].pop(step, None)
