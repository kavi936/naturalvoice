"""Custom frames emitted by the Turn Manager."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pipecat.frames.frames import SystemFrame


class TurnState(Enum):
    """Conversational state of the caller's turn."""

    SPEAKING = "speaking"
    THINKING = "thinking"
    SIDE_CONVO = "side_convo"
    DONE = "done"


@dataclass
class TurnStateChangedFrame(SystemFrame):
    """Emitted on every Turn Manager state transition (logging / debugging)."""

    state: TurnState
    previous_state: TurnState
    reason: str = ""
    signals: dict | None = None
