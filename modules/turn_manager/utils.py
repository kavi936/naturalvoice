"""Helpers for transcript analysis and audio RMS."""

from __future__ import annotations

import re
from typing import Any

import numpy as np

TERMINAL_PUNCT = re.compile(r"[.!?]\s*$")
SHORT_COMPLETE = re.compile(
    r"^(yes|yeah|yep|no|nope|okay|ok|sure|thanks|thank you|hello|hi|hey)\.?$",
    re.IGNORECASE,
)


def is_syntactically_complete(text: str) -> bool:
    """Heuristic: does this utterance look like a finished turn?"""
    stripped = text.strip()
    if not stripped:
        return False
    if TERMINAL_PUNCT.search(stripped):
        return True
    if SHORT_COMPLETE.match(stripped):
        return True
    # Trailing comma / dash / conjunction → mid-clause
    if re.search(r"(,\s*|-\s*|\b(and|but|so|or|for|because|um|uh|like)\s*)$", stripped, re.I):
        return False
    return len(stripped.split()) >= 4


def ends_mid_clause(text: str) -> bool:
    return bool(text.strip()) and not is_syntactically_complete(text)


def extract_word_confidence_mean(result: Any) -> float | None:
    """Mean word confidence from Deepgram ListenV1Results or USF ASR JSON."""
    if result is None:
        return None
    try:
        # USF ASR / raw JSON (Deepgram-compatible dict)
        if isinstance(result, dict):
            alts = (result.get("channel") or {}).get("alternatives") or []
            if not alts:
                return None
            words = alts[0].get("words") or []
            confidences = [
                float(w["confidence"])
                for w in words
                if isinstance(w, dict) and w.get("confidence") is not None
            ]
            return sum(confidences) / len(confidences) if confidences else None

        channel = getattr(result, "channel", None)
        if not channel or not channel.alternatives:
            return None
        alt = channel.alternatives[0]
        words = getattr(alt, "words", None) or []
        confidences = [
            float(w.confidence)
            for w in words
            if getattr(w, "confidence", None) is not None
        ]
        if not confidences:
            return None
        return sum(confidences) / len(confidences)
    except Exception:
        return None


def extract_inter_word_gaps_ms(result: Any) -> list[float]:
    """Return inter-word gaps in milliseconds from Deepgram or USF ASR payloads."""
    if result is None:
        return []
    try:
        if isinstance(result, dict):
            alts = (result.get("channel") or {}).get("alternatives") or []
            if not alts:
                return []
            words = alts[0].get("words") or []
            gaps: list[float] = []
            for i in range(1, len(words)):
                prev = words[i - 1]
                curr = words[i]
                if isinstance(prev, dict) and isinstance(curr, dict):
                    prev_end = prev.get("end")
                    curr_start = curr.get("start")
                    if prev_end is not None and curr_start is not None:
                        gap_ms = (float(curr_start) - float(prev_end)) * 1000.0
                        if gap_ms > 0:
                            gaps.append(gap_ms)
            return gaps

        channel = getattr(result, "channel", None)
        if not channel or not channel.alternatives:
            return []
        words = getattr(channel.alternatives[0], "words", None) or []
        gaps: list[float] = []
        for i in range(1, len(words)):
            prev_end = getattr(words[i - 1], "end", None)
            curr_start = getattr(words[i], "start", None)
            if prev_end is not None and curr_start is not None:
                gap_ms = (float(curr_start) - float(prev_end)) * 1000.0
                if gap_ms > 0:
                    gaps.append(gap_ms)
        return gaps
    except Exception:
        return []


def has_clause_boundary_gap(result: Any, min_gap_ms: float = 200.0) -> bool:
    gaps = extract_inter_word_gaps_ms(result)
    return any(g >= min_gap_ms for g in gaps)


def contains_trigger_phrase(text: str, phrases: list[str]) -> bool:
    lowered = text.lower()
    return any(p in lowered for p in phrases)


def frame_rms(audio: bytes, num_channels: int) -> float:
    """RMS of an int16 PCM frame."""
    if not audio:
        return 0.0
    samples = np.frombuffer(audio, dtype=np.int16)
    if num_channels > 1:
        samples = samples.reshape(-1, num_channels).mean(axis=1)
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
