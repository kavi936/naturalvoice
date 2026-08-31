"""Turn Manager — four-state conversational turn control for voice agents."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Literal

from loguru import logger

from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    InterimTranscriptionFrame,
    StartFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from .backchannels import BackchannelClipStore, BackchannelVoice
from .frames import TurnState, TurnStateChangedFrame
from .utils import (
    contains_trigger_phrase,
    ends_mid_clause,
    extract_word_confidence_mean,
    frame_rms,
    has_clause_boundary_gap,
    is_syntactically_complete,
)

BackchannelVoiceOption = Literal["elevenlabs", "ultravelabs"]

DEFAULT_TRIGGER_PHRASES = [
    "hold on",
    "one sec",
    "sorry",
    "just a second",
    "hang on",
]


class TurnManager(FrameProcessor):
    """Pipecat processor that classifies caller state and gates LLM turn-end.

    Sits between STT and the user/LLM aggregators. Pair with
    ``ExternalUserTurnStopStrategy`` on the user aggregator so the LLM only
    runs when this processor emits ``UserStoppedSpeakingFrame`` on ``DONE``.

    Pipeline::

        transport.input → STT → TurnManager → user_aggregator → LLM → TTS → output
    """

    def __init__(
        self,
        *,
        patience_window_ms: int = 600,
        thinking_pause_min_ms: int = 400,
        thinking_pause_max_ms: int = 800,
        backchannel_threshold_s: float = 3.5,
        side_convo_confidence_threshold: float = 0.6,
        side_convo_volume_drop: float = 0.4,
        side_convo_recovery_volume_ratio: float = 0.7,
        side_convo_recovery_confidence: float = 0.75,
        trigger_phrases: list[str] | None = None,
        backchannel_voice: BackchannelVoiceOption = "elevenlabs",
        backchannel_volume: float = 0.4,
        backchannel_min_interval_s: float = 6.0,
        backchannel_clause_gap_ms: float = 200.0,
        speech_rms_threshold: float = 350.0,
        debug_mode: bool = False,
        elevenlabs_voice_id: str | None = None,
        ultravoice_voice_id: str | None = None,
        backchannel_queue: asyncio.Queue | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self._backchannel_queue = backchannel_queue or asyncio.Queue()
        self._patience_window_ms = patience_window_ms
        self._thinking_pause_min_ms = thinking_pause_min_ms
        self._thinking_pause_max_ms = thinking_pause_max_ms
        self._backchannel_threshold_s = backchannel_threshold_s
        self._side_convo_confidence_threshold = side_convo_confidence_threshold
        self._side_convo_volume_drop = side_convo_volume_drop
        self._side_convo_recovery_volume_ratio = side_convo_recovery_volume_ratio
        self._side_convo_recovery_confidence = side_convo_recovery_confidence
        self._trigger_phrases = trigger_phrases or list(DEFAULT_TRIGGER_PHRASES)
        self._backchannel_volume = backchannel_volume
        self._backchannel_min_interval_s = backchannel_min_interval_s
        self._backchannel_clause_gap_ms = backchannel_clause_gap_ms
        self._speech_rms_threshold = speech_rms_threshold
        self._debug_mode = debug_mode

        self._state = TurnState.DONE
        self._last_transcript: str = ""
        self._last_result: object | None = None
        self._last_confidence: float | None = None

        # Silence / pause tracking
        self._last_speech_time: float = 0.0
        self._silence_started_at: float | None = None
        self._pause_ms_at_thinking: float = 0.0

        # Rolling 3-second RMS buffer: (timestamp, rms)
        self._rms_buffer: deque[tuple[float, float]] = deque()
        self._rms_window_s = 3.0
        self._current_volume_ratio: float = 1.0

        # Backchannel state
        self._speaking_started_at: float | None = None
        self._last_backchannel_at: float = 0.0
        self._backchannel_clips = BackchannelClipStore(
            voice=backchannel_voice,  # type: ignore[arg-type]
            elevenlabs_voice_id=elevenlabs_voice_id,
            ultravoice_voice_id=ultravoice_voice_id,
        )
        self._output_sample_rate: int = 24_000
        self._output_channels: int = 1
        self._clips_ready = False

        self._patience_task: asyncio.Task | None = None

    @property
    def state(self) -> TurnState:
        return self._state

    # ------------------------------------------------------------------
    # FrameProcessor
    # ------------------------------------------------------------------

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, StartFrame):
            self._output_sample_rate = frame.audio_out_sample_rate
            if not self._clips_ready:
                await self._backchannel_clips.generate()
                self._clips_ready = True
            await self.push_frame(frame, direction)
            return

        if direction != FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        # Raw audio — RMS analysis for side-conversation detection
        if isinstance(frame, InputAudioRawFrame):
            await self._handle_input_audio(frame)
            await self.push_frame(frame, direction)
            return

        # Deepgram / STT transcripts
        if isinstance(frame, InterimTranscriptionFrame):
            await self._handle_interim(frame)
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TranscriptionFrame):
            await self._handle_final_transcript(frame)
            await self.push_frame(frame, direction)
            return

        # VAD frames from upstream Silero — use as a secondary speech signal
        if isinstance(frame, VADUserStartedSpeakingFrame):
            await self._on_speech_detected(source="vad_start")
            # Pass through so user aggregator can track start too
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, VADUserStoppedSpeakingFrame):
            await self._on_vad_silence(frame)
            # Swallow VAD stop — Turn Manager owns turn-end signalling
            return

        # Suppress premature turn-end while not DONE
        if isinstance(frame, UserStoppedSpeakingFrame):
            if self._state != TurnState.DONE:
                if self._debug_mode:
                    logger.debug(
                        f"TurnManager: suppressed UserStoppedSpeakingFrame (state={self._state.value})"
                    )
                return
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)

    # ------------------------------------------------------------------
    # Transcript handlers
    # ------------------------------------------------------------------

    async def _handle_interim(self, frame: InterimTranscriptionFrame):
        if not frame.text.strip():
            return
        self._last_transcript = frame.text.strip()
        self._last_result = frame.result
        self._last_confidence = extract_word_confidence_mean(frame.result)
        await self._on_speech_detected(source="interim")
        await self._maybe_side_convo_from_transcript(frame.text, frame.result)
        await self._maybe_backchannel(frame.result)

    async def _handle_final_transcript(self, frame: TranscriptionFrame):
        if frame.text.strip():
            self._last_transcript = frame.text.strip()
            self._last_result = frame.result
            self._last_confidence = extract_word_confidence_mean(frame.result)
            await self._on_speech_detected(source="final")
            await self._maybe_side_convo_from_transcript(frame.text, frame.result)

    async def _on_speech_detected(self, source: str):
        now = time.monotonic()
        self._last_speech_time = now
        self._silence_started_at = None

        if self._state in (TurnState.THINKING, TurnState.SIDE_CONVO):
            await self._cancel_patience_timer()
            if self._state == TurnState.SIDE_CONVO:
                # Recovery from side convo handled by volume/confidence checks
                if (
                    self._current_volume_ratio >= self._side_convo_recovery_volume_ratio
                    and (self._last_confidence or 0.0) >= self._side_convo_recovery_confidence
                ):
                    await self._transition(
                        TurnState.SPEAKING,
                        reason=f"recovered from side convo ({source})",
                        signals={
                            "volume_ratio": self._current_volume_ratio,
                            "confidence": self._last_confidence,
                        },
                    )
            else:
                await self._transition(
                    TurnState.SPEAKING,
                    reason=f"new speech during thinking ({source})",
                )

        elif self._state == TurnState.DONE:
            await self._transition(TurnState.SPEAKING, reason=f"turn started ({source})")
            self._speaking_started_at = now
            await self.push_frame(UserStartedSpeakingFrame(), FrameDirection.DOWNSTREAM)

        elif self._state == TurnState.SPEAKING:
            pass  # continue speaking

        if self._state == TurnState.SPEAKING and self._speaking_started_at is None:
            self._speaking_started_at = now

    async def _on_vad_silence(self, frame: VADUserStoppedSpeakingFrame):
        """Deepgram / Silero reported silence — evaluate THINKING transition."""
        now = time.monotonic()
        if self._silence_started_at is None:
            self._silence_started_at = now

        pause_ms = (now - self._silence_started_at) * 1000.0
        # Also account for VAD stop_secs as part of perceived pause
        pause_ms += frame.stop_secs * 1000.0

        if self._state != TurnState.SPEAKING:
            return

        mid_clause = ends_mid_clause(self._last_transcript)
        in_thinking_band = self._thinking_pause_min_ms <= pause_ms <= self._thinking_pause_max_ms

        if mid_clause or in_thinking_band:
            self._pause_ms_at_thinking = pause_ms
            await self._transition(
                TurnState.THINKING,
                reason="pause after speech",
                signals={
                    "pause_ms": pause_ms,
                    "mid_clause": mid_clause,
                    "transcript": self._last_transcript[:80],
                },
            )
            await self._start_patience_timer()

    # ------------------------------------------------------------------
    # Audio RMS
    # ------------------------------------------------------------------

    async def _handle_input_audio(self, frame: InputAudioRawFrame):
        now = time.monotonic()
        rms = frame_rms(frame.audio, frame.num_channels)

        self._rms_buffer.append((now, rms))
        while self._rms_buffer and (now - self._rms_buffer[0][0]) > self._rms_window_s:
            self._rms_buffer.popleft()

        avg_rms = sum(v for _, v in self._rms_buffer) / max(len(self._rms_buffer), 1)
        self._current_volume_ratio = (rms / avg_rms) if avg_rms > 1.0 else 1.0

        if rms >= self._speech_rms_threshold:
            await self._on_speech_detected(source="rms")

        # Side-conversation volume signal
        volume_drop = self._current_volume_ratio < (1.0 - self._side_convo_volume_drop)
        if volume_drop and self._state in (TurnState.SPEAKING, TurnState.THINKING):
            await self._maybe_enter_side_convo()

        if (
            self._state == TurnState.SIDE_CONVO
            and self._current_volume_ratio >= self._side_convo_recovery_volume_ratio
            and (self._last_confidence or 0.0) >= self._side_convo_recovery_confidence
        ):
            await self._transition(
                TurnState.SPEAKING,
                reason="side convo recovery",
                signals={
                    "volume_ratio": self._current_volume_ratio,
                    "confidence": self._last_confidence,
                },
            )

        # Fallback silence watcher when VAD frames aren't emitted (TurnManager is upstream of user VAD)
        if rms < self._speech_rms_threshold * 0.5:
            if self._silence_started_at is None and self._last_speech_time > 0:
                self._silence_started_at = now
            if self._silence_started_at and self._state == TurnState.SPEAKING:
                pause_ms = (now - self._silence_started_at) * 1000.0
                if pause_ms >= self._thinking_pause_min_ms:
                    mid_clause = ends_mid_clause(self._last_transcript)
                    in_band = pause_ms <= self._thinking_pause_max_ms or mid_clause
                    if in_band:
                        self._pause_ms_at_thinking = pause_ms
                        await self._transition(
                            TurnState.THINKING,
                            reason="audio silence pause",
                            signals={"pause_ms": pause_ms, "mid_clause": mid_clause},
                        )
                        await self._start_patience_timer()
        else:
            self._silence_started_at = None

    # ------------------------------------------------------------------
    # Side conversation
    # ------------------------------------------------------------------

    async def _maybe_side_convo_from_transcript(self, text: str, result: object | None):
        conf = extract_word_confidence_mean(result)
        if conf is not None:
            self._last_confidence = conf
        await self._maybe_enter_side_convo()

    async def _maybe_enter_side_convo(self):
        if self._state not in (TurnState.SPEAKING, TurnState.THINKING):
            return

        conf = self._last_confidence
        conf_low = conf is not None and conf < self._side_convo_confidence_threshold
        volume_drop = self._current_volume_ratio < (1.0 - self._side_convo_volume_drop)
        phrase_hit = contains_trigger_phrase(self._last_transcript, self._trigger_phrases)

        # Core rule: low confidence AND volume drop must both be present.
        if not (conf_low and volume_drop):
            return

        signals = {
            "confidence": conf,
            "volume_ratio": self._current_volume_ratio,
            "phrase": phrase_hit,
        }

        await self._cancel_patience_timer()
        await self._transition(TurnState.SIDE_CONVO, reason="side conversation detected", signals=signals)

    # ------------------------------------------------------------------
    # Patience window → DONE
    # ------------------------------------------------------------------

    async def _start_patience_timer(self):
        await self._cancel_patience_timer()
        self._patience_task = self.create_task(
            self._patience_timer(),
            name=f"{self}::patience_timer",
        )

    async def _cancel_patience_timer(self):
        if self._patience_task:
            await self.cancel_task(self._patience_task)
            self._patience_task = None

    async def _patience_timer(self):
        await asyncio.sleep(self._patience_window_ms / 1000.0)

        if self._state != TurnState.THINKING:
            return

        if is_syntactically_complete(self._last_transcript):
            await self._finalize_turn(
                reason="patience window elapsed + complete transcript",
                signals={"transcript": self._last_transcript[:80]},
            )
        else:
            # Still thinking — extend patience once more
            if self._debug_mode:
                logger.debug(
                    f"TurnManager: patience elapsed but transcript incomplete — "
                    f"extending ({self._last_transcript[:60]!r})"
                )
            await self._start_patience_timer()

    async def _finalize_turn(self, reason: str, signals: dict | None = None):
        await self._transition(TurnState.DONE, reason=reason, signals=signals)
        self._speaking_started_at = None
        self._silence_started_at = None
        self._last_speech_time = 0.0
        await self.push_frame(UserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM)

    # ------------------------------------------------------------------
    # Backchannels
    # ------------------------------------------------------------------

    async def _maybe_backchannel(self, result: object | None):
        if self._state != TurnState.SPEAKING:
            return
        if self._speaking_started_at is None:
            return

        now = time.monotonic()
        if (now - self._speaking_started_at) < self._backchannel_threshold_s:
            return
        if (now - self._last_backchannel_at) < self._backchannel_min_interval_s:
            return
        if not has_clause_boundary_gap(result, self._backchannel_clause_gap_ms):
            return
        if not self._backchannel_clips.ready:
            return

        phrase = self._backchannel_clips.random_phrase()
        pcm = self._backchannel_clips.get_clip(phrase)
        if not pcm:
            return

        scaled = self._scale_pcm(pcm, self._backchannel_volume)
        await self._backchannel_queue.put((scaled, self._output_sample_rate, self._output_channels))
        self._last_backchannel_at = now
        if self._debug_mode:
            logger.debug(f"TurnManager: backchannel '{phrase}' injected")

    @staticmethod
    def _scale_pcm(pcm: bytes, gain: float) -> bytes:
        import numpy as np

        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) * gain
        return np.clip(samples, -32768, 32767).astype(np.int16).tobytes()

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    async def _transition(
        self,
        new_state: TurnState,
        *,
        reason: str = "",
        signals: dict | None = None,
    ):
        if new_state == self._state:
            return
        previous = self._state
        self._state = new_state

        if self._debug_mode:
            logger.info(
                f"TurnManager: {previous.value} → {new_state.value} | {reason} | signals={signals}"
            )

        await self.push_frame(
            TurnStateChangedFrame(
                state=new_state,
                previous_state=previous,
                reason=reason,
                signals=signals,
            ),
            FrameDirection.DOWNSTREAM,
        )

        if new_state == TurnState.SPEAKING and self._speaking_started_at is None:
            self._speaking_started_at = time.monotonic()
