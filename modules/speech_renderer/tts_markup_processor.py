"""Stage 2 — engine-specific TTS markup applied to LLM text frames."""

from __future__ import annotations

import re
from typing import Literal

from pipecat.frames.frames import Frame, TextFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from .system_prompt_injector import SystemPromptInjector

TTSEngine = Literal["ultravoice", "elevenlabs", "fish_audio"]

# Markdown / code cleanup
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_HEADER = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_BULLET = re.compile(r"^\s*[-*•]\s+", re.MULTILINE)
_NUMBERED = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)
_CODE_FENCE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_PAUSE_TOKEN = re.compile(r"\[pause\]", re.IGNORECASE)

# Filler openers that should trail with ellipsis if missing
_FILLER_OPENERS = (
    "let me check",
    "let me just check",
    "one sec",
    "give me just a moment",
    "hang on",
    "hold on",
)

# Words that can be elongated for naturalness (applied sparingly at clause starts)
_ELONGATION_MAP = {
    "so": "Sooo",
    "yeah": "Yeahhh",
    "ah": "Ahhhh",
    "ahh": "Ahhhh",
    "oh": "Ohhh",
    "hmm": "Hmmm",
    "um": "Umm",
}


class TTSMarkupProcessor(FrameProcessor):
    """Pipecat processor between LLM and TTS — applies markup to ``TextFrame`` text."""

    def __init__(
        self,
        tts_engine: TTSEngine = "ultravoice",
        *,
        injector: SystemPromptInjector | None = None,
        apply_elongation: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._tts_engine = tts_engine
        self._injector = injector
        self._elongation_enabled = apply_elongation

    @property
    def tts_engine(self) -> TTSEngine:
        return self._tts_engine

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if direction == FrameDirection.DOWNSTREAM and isinstance(frame, TextFrame):
            frame.text = self.apply(frame.text)
            if self._injector:
                self._injector.record_opener(frame.text)

        await self.push_frame(frame, direction)

    def apply(self, text: str) -> str:
        """Transform raw LLM text into TTS-ready markup."""
        if not text or not text.strip():
            return text

        result = text
        result = self._strip_markdown(result)
        result = self._normalize_whitespace(result)
        result = self._ensure_filler_ellipsis(result)
        result = self._apply_engine_rules(result)
        if self._elongation_enabled:
            result = self._apply_elongation(result)
        return result

    def _strip_markdown(self, text: str) -> str:
        text = _CODE_FENCE.sub("", text)
        text = _INLINE_CODE.sub(r"\1", text)
        text = _BOLD.sub(r"\1", text)
        text = _ITALIC.sub(r"\1", text)
        text = _HEADER.sub("", text)
        text = _BULLET.sub("", text)
        text = _NUMBERED.sub("", text)
        return text

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return " ".join(lines)

    def _ensure_filler_ellipsis(self, text: str) -> str:
        lowered = text.lower()
        for phrase in _FILLER_OPENERS:
            idx = lowered.find(phrase)
            if idx == -1:
                continue
            end = idx + len(phrase)
            tail = text[end : end + 4]
            if not tail.startswith("...") and not tail.startswith("…"):
                text = text[:end] + "..." + text[end:]
                break
        return text

    def _apply_engine_rules(self, text: str) -> str:
        if self._tts_engine == "ultravoice":
            return self._apply_ultravoice(text)
        if self._tts_engine == "elevenlabs":
            return self._apply_elevenlabs(text)
        return self._apply_fish_audio(text)

    def _apply_ultravoice(self, text: str) -> str:
        # TODO(USF Mini TTS): Confirm whether USF Mini TTS supports SSML <break> and
        # <prosody rate="slow"> tags. Test with:
        #   curl -X POST $ULTRAVOICE_TTS_URL -d '{"text":"<break time=\"300ms\"/>"}'
        # If supported, upgrade [pause] → <break time="300ms"/> and clause breaks
        # to <break time="150ms"/>. Until confirmed, punctuation-driven prosody only.
        text = _PAUSE_TOKEN.sub("...", text)
        text = text.replace("—", ", ")
        text = text.replace("–", ", ")
        return text

    def _apply_elevenlabs(self, text: str) -> str:
        text = _PAUSE_TOKEN.sub("...", text)
        # ElevenLabs renders em-dashes as short breaks natively
        text = self._ensure_comma_clauses(text)
        return text

    def _apply_fish_audio(self, text: str) -> str:
        text = _PAUSE_TOKEN.sub("...", text)
        text = text.replace("—", ", ")
        text = text.replace("–", ", ")
        return text

    @staticmethod
    def _ensure_comma_clauses(text: str) -> str:
        """Light touch: ensure major clause breaks have comma pauses."""
        text = re.sub(r"\s+-\s+", ", ", text)
        return text

    def _apply_elongation(self, text: str) -> str:
        """Elongate select leading words for prosodic naturalness."""
        words = text.split()
        if not words:
            return text
        first = words[0].lower().rstrip(".,!?…")
        if first in _ELONGATION_MAP and len(words[0]) < 8:
            words[0] = _ELONGATION_MAP[first] + words[0][len(words[0].rstrip(".,!?…")) :]
        return " ".join(words)
