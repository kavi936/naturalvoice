"""Unified Speech Renderer — Stage 1 (prompt) + Stage 2 (TTS markup)."""

from __future__ import annotations

from typing import Literal

from .system_prompt_injector import SystemPromptInjector
from .tts_markup_processor import TTSEngine, TTSMarkupProcessor

TTSEngineName = Literal["ultravoice", "elevenlabs", "fish_audio"]


class SpeechRenderer:
    """Two-stage spoken-register pipeline for voice agents.

    Stage 1 — ``SystemPromptInjector``: shapes LLM register via system prompt.
    Stage 2 — ``TTSMarkupProcessor``: engine-specific markup before TTS.

    Both stages are independently usable via ``renderer.injector`` and
    ``renderer.markup_processor``.
    """

    def __init__(
        self,
        tts_engine: TTSEngineName = "ultravoice",
        filler_intensity: float = 0.7,
        opener_variety: int = 5,
        emit_pause_tokens: bool = True,
    ):
        self.injector = SystemPromptInjector(
            filler_intensity=filler_intensity,
            opener_variety=opener_variety,
            emit_pause_tokens=emit_pause_tokens,
        )
        self.markup_processor = TTSMarkupProcessor(
            tts_engine=tts_engine,  # type: ignore[arg-type]
            injector=self.injector,
        )
        self.tts_engine = tts_engine

    def shape_system_prompt(self, existing: str) -> str:
        """Apply Stage 1 to a system prompt string."""
        return self.injector.prepend(existing)
