"""Stage 1 — spoken-register system prompt shaping."""

from __future__ import annotations

DEFAULT_OPENERS = (
    "Okay so...",
    "Right, let me just...",
    "Sure, one sec...",
    "Hmm, let me check...",
    "Yeah, absolutely...",
)


class SystemPromptInjector:
    """Prepends spoken-register instructions to an existing system prompt.

    Called once at pipeline init — not a frame processor. Pair with
    ``TTSMarkupProcessor`` (Stage 2) for full Speech Renderer coverage.
    """

    SPOKEN_REGISTER_BLOCK = """
You are speaking aloud on a phone call — not writing text. Follow these rules on every reply:

- Use contractions naturally: I'm, let me, we've, you'd, that's, won't.
- Open every response with a varied spoken phrase. Rotate openers — never use the same opener twice in a row. Choose from: {openers}.
- Before any lookup or processing moment, use a filler phrase scaled to your conversational style: "Let me just check that for you...", "One sec...", "Give me just a moment...".
- Break long answers into short clauses — use dashes or ellipses between thoughts. Never deliver one long grammatical sentence.
- Hedge before uncertain answers: "I think...", "Should be...", "Looks like...", "Pretty sure...".
- Soften bad news: "Ahh, unfortunately..." or "Hmm, looks like we're all booked up..." — never "We do not have availability".
- Never use formal written connectors: Furthermore, Additionally, In conclusion, Therefore.
- Never output markdown — no bold, no bullets, no headers, no backticks, no numbered lists.
{pause_tokens_line}
Filler intensity for this deployment: {intensity_label} ({filler_intensity:.1f}). At lower intensity, use fewer fillers; at higher intensity, use them generously at processing moments.
""".strip()

    def __init__(
        self,
        filler_intensity: float = 0.7,
        opener_variety: int = 5,
        emit_pause_tokens: bool = True,
        openers: tuple[str, ...] = DEFAULT_OPENERS,
    ):
        if not 0.0 <= filler_intensity <= 1.0:
            raise ValueError("filler_intensity must be between 0.0 and 1.0")
        self.filler_intensity = filler_intensity
        self.opener_variety = min(opener_variety, len(openers))
        self.emit_pause_tokens = emit_pause_tokens
        self._openers = openers[: self.opener_variety]
        self._last_opener: str | None = None

    @property
    def last_opener(self) -> str | None:
        return self._last_opener

    def next_opener(self) -> str:
        """Return the next opener in rotation (never repeats consecutively)."""
        import random

        choices = [o for o in self._openers if o != self._last_opener] or list(self._openers)
        opener = random.choice(choices)
        self._last_opener = opener
        return opener

    def record_opener(self, text: str) -> None:
        """Record which opener was used if text starts with a known opener."""
        stripped = text.lstrip()
        for opener in self._openers:
            if stripped.lower().startswith(opener.lower().rstrip(".")):
                self._last_opener = opener
                return

    def build_block(self) -> str:
        """Return the spoken-register instruction block only."""
        if self.filler_intensity <= 0.35:
            intensity_label = "professional / minimal fillers"
        elif self.filler_intensity <= 0.75:
            intensity_label = "casual conversational"
        else:
            intensity_label = "maximum naturalness"

        pause_tokens_line = (
            '- You may emit [pause] at natural processing moments; downstream TTS converts these to pauses.'
            if self.emit_pause_tokens
            else ""
        )

        openers_str = ", ".join(f'"{o}"' for o in self._openers)
        return self.SPOKEN_REGISTER_BLOCK.format(
            openers=openers_str,
            pause_tokens_line=pause_tokens_line,
            intensity_label=intensity_label,
            filler_intensity=self.filler_intensity,
        )

    def prepend(self, existing_system_prompt: str) -> str:
        """Prepend spoken-register block to ``existing_system_prompt``."""
        block = self.build_block()
        existing = existing_system_prompt.strip()
        if not existing:
            return block
        return f"{block}\n\n---\n\n{existing}"
