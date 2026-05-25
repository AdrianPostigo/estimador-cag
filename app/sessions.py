from collections import deque
from uuid import uuid4

from app.schemas import ProjectMetadata
from app.services.summarizer import summarize_turns

MAX_TURNS = 6


class ConversationHistory:
    def __init__(self) -> None:
        self._messages: deque[dict] = deque(maxlen=MAX_TURNS * 2)
        self._accumulated_summary: str | None = None
        self._turns_summarized: int = 0

    def should_summarize(self) -> bool:
        """Check if we're at capacity and should compress old turns."""
        return self.turn_count >= MAX_TURNS

    def add_turn(self, user_content: str, assistant_content: str) -> None:
        """Add a new turn, summarizing old turns if necessary."""
        if self.should_summarize():
            # Extract the first 2 turns (4 messages) to summarize
            turns_to_summarize = []
            for _ in range(min(4, len(self._messages))):
                if self._messages:
                    turns_to_summarize.insert(0, self._messages.popleft())

            if turns_to_summarize:
                # Reverse to restore original order
                turns_to_summarize.reverse()
                summary = summarize_turns(turns_to_summarize)

                # Accumulate summaries
                if self._accumulated_summary:
                    self._accumulated_summary += f"\n{summary}"
                else:
                    self._accumulated_summary = summary

                self._turns_summarized += 2

        self._messages.append({"role": "user", "content": user_content})
        self._messages.append({"role": "assistant", "content": assistant_content})

    def to_messages_list(self, system_prompt: str) -> list[dict]:
        """Return messages list with accumulated summary injected if available."""
        messages = [{"role": "system", "content": system_prompt}]

        # Inject accumulated summary as additional system context
        if self._accumulated_summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"Contexto de turnos previos (resumido):\n{self._accumulated_summary}",
                }
            )

        messages.extend(list(self._messages))
        return messages

    @property
    def turn_count(self) -> int:
        return len(self._messages) // 2


class Session:
    def __init__(self) -> None:
        self.session_id: str = str(uuid4())
        self.history: ConversationHistory = ConversationHistory()
        self.metadata: ProjectMetadata = ProjectMetadata()
        # Observables
        self.last_resolved_tier: int | None = None
        self.last_tier_rule: str | None = None

    @property
    def anchors_count(self) -> int:
        """Count how many metadata anchors are resolved (non-empty)."""
        count = 0
        if self.metadata.project_name:
            count += 1
        if self.metadata.assumed_team_size:
            count += 1
        if self.metadata.mentioned_technologies:
            count += 1
        if self.metadata.agreed_scope:
            count += 1
        return count


_sessions: dict[str, Session] = {}


def create_session() -> Session:
    session = Session()
    _sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)
