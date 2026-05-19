from collections import deque
from uuid import uuid4

from app.schemas import ProjectMetadata

MAX_TURNS = 6


class ConversationHistory:
    def __init__(self) -> None:
        self._messages: deque[dict] = deque(maxlen=MAX_TURNS * 2)

    def add_turn(self, user_content: str, assistant_content: str) -> None:
        self._messages.append({"role": "user", "content": user_content})
        self._messages.append({"role": "assistant", "content": assistant_content})

    def to_messages_list(self, system_prompt: str) -> list[dict]:
        return [{"role": "system", "content": system_prompt}, *list(self._messages)]

    @property
    def turn_count(self) -> int:
        return len(self._messages) // 2


class Session:
    def __init__(self) -> None:
        self.session_id: str = str(uuid4())
        self.history: ConversationHistory = ConversationHistory()
        self.metadata: ProjectMetadata = ProjectMetadata()


_sessions: dict[str, Session] = {}


def create_session() -> Session:
    session = Session()
    _sessions[session.session_id] = session
    return session


def get_session(session_id: str) -> Session | None:
    return _sessions.get(session_id)
