"""AmbientMixer — Pipecat FrameProcessor that injects room tone into TTS audio.

Why this exists
---------------
Real phone calls carry ambient bleed (restaurant floor, office HVAC, etc.).
Studio-clean TTS is an immediate "robot" tell. This module mixes a looping
background profile into outbound TTS frames at a low, configurable level.

Placement in the pipeline
-------------------------
    ... → TTS → AmbientMixer → transport.output() → ...

Only ``OutputAudioRawFrame`` (including ``TTSAudioRawFrame``) frames are mixed.
Inbound caller audio is left untouched.

Note: ambient only rides along with TTS/output audio frames. For continuous
room tone during silence gaps, prefer attaching a transport-level mixer
(Pipecat ``SoundfileMixer`` / ``BaseAudioMixer``) using the same profile WAVs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
from loguru import logger

from pipecat.frames.frames import Frame, OutputAudioRawFrame, StartFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

# Bundled profiles shipped under modules/ambient/profiles/
_PROFILES_DIR = Path(__file__).resolve().parent / "profiles"
_SUPPORTED_PROFILES = ("restaurant", "office", "none")


class AmbientMixer(FrameProcessor):
    """Mix a looping ambient WAV into outgoing TTS audio frames.

    Args:
        profile: ``"restaurant"``, ``"office"``, or ``"none"`` (passthrough).
        mix_level: Background gain relative to TTS (0.0–1.0). Default 0.15
            keeps speech intelligible while providing acoustic context.
        profiles_dir: Optional override for the WAV directory (useful in tests).
    """

    def __init__(
        self,
        profile: str = "restaurant",
        mix_level: float = 0.15,
        profiles_dir: Optional[Path | str] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        if profile not in _SUPPORTED_PROFILES:
            raise ValueError(
                f"Unknown ambient profile '{profile}'. "
                f"Expected one of: {', '.join(_SUPPORTED_PROFILES)}"
            )
        if not 0.0 <= mix_level <= 1.0:
            raise ValueError("mix_level must be between 0.0 and 1.0")

        self._profile = profile
        self._mix_level = float(mix_level)
        self._profiles_dir = Path(profiles_dir) if profiles_dir else _PROFILES_DIR

        # Filled on StartFrame once we know the transport output sample rate.
        self._sample_rate: Optional[int] = None
        self._ambient: Optional[np.ndarray] = None  # int16 mono samples
        self._pos: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_profile(self, profile: str) -> None:
        """Switch ambient profile mid-call (e.g. restaurant → office).

        Reloads/resamples the WAV if the output sample rate is already known.
        """
        if profile not in _SUPPORTED_PROFILES:
            raise ValueError(
                f"Unknown ambient profile '{profile}'. "
                f"Expected one of: {', '.join(_SUPPORTED_PROFILES)}"
            )
        self._profile = profile
        self._pos = 0
        if profile == "none":
            self._ambient = None
            logger.info("AmbientMixer profile set to 'none' (passthrough)")
            return
        if self._sample_rate is not None:
            self._load_profile(profile, self._sample_rate)
            logger.info(f"AmbientMixer switched to profile '{profile}'")

    @property
    def profile(self) -> str:
        return self._profile

    @property
    def mix_level(self) -> float:
        return self._mix_level

    @mix_level.setter
    def mix_level(self, value: float) -> None:
        if not 0.0 <= value <= 1.0:
            raise ValueError("mix_level must be between 0.0 and 1.0")
        self._mix_level = float(value)

    # ------------------------------------------------------------------
    # FrameProcessor
    # ------------------------------------------------------------------

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # Learn the transport output rate and load the matching ambient loop.
        if isinstance(frame, StartFrame):
            self._sample_rate = frame.audio_out_sample_rate
            if self._profile != "none":
                self._load_profile(self._profile, self._sample_rate)
            await self.push_frame(frame, direction)
            return

        # Mix only outbound audio (TTS → transport). Never touch inbound mic.
        if (
            direction == FrameDirection.DOWNSTREAM
            and isinstance(frame, OutputAudioRawFrame)
            and self._ambient is not None
            and self._mix_level > 0.0
        ):
            frame.audio = self._mix(frame.audio, frame.num_channels)

        await self.push_frame(frame, direction)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _profile_path(self, profile: str) -> Path:
        return self._profiles_dir / f"{profile}.wav"

    def _load_profile(self, profile: str, target_rate: int) -> None:
        """Load a mono WAV and resample to ``target_rate`` if needed."""
        path = self._profile_path(profile)
        if not path.exists():
            logger.error(
                f"Ambient profile file missing: {path}. "
                "Run: python modules/ambient/generate_profiles.py"
            )
            self._ambient = None
            return

        data, file_rate = sf.read(str(path), dtype="float32", always_2d=True)
        # Collapse to mono (average channels if stereo source).
        mono = data.mean(axis=1)

        if file_rate != target_rate:
            mono = self._resample(mono, file_rate, target_rate)
            logger.debug(
                f"Resampled ambient '{profile}' from {file_rate} Hz → {target_rate} Hz"
            )

        # Store as int16 for cheap mixing with PCM frames.
        self._ambient = np.clip(mono * 32767.0, -32768, 32767).astype(np.int16)
        self._pos = 0
        logger.info(
            f"Loaded ambient profile '{profile}' "
            f"({len(self._ambient)} samples @ {target_rate} Hz, mix_level={self._mix_level})"
        )

    @staticmethod
    def _resample(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
        """Linear-interpolation resample — dependency-light, good enough for noise beds."""
        if src_rate == dst_rate or len(samples) == 0:
            return samples
        duration = len(samples) / src_rate
        n_out = int(round(duration * dst_rate))
        x_old = np.linspace(0.0, 1.0, num=len(samples), endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
        return np.interp(x_new, x_old, samples).astype(np.float32)

    def _mix(self, audio: bytes, num_channels: int) -> bytes:
        """Add a looping ambient chunk to an int16 PCM frame."""
        assert self._ambient is not None

        audio_np = np.frombuffer(audio, dtype=np.int16)
        if audio_np.size == 0:
            return audio

        # Work in mono for the ambient bed, then expand if the frame is stereo.
        if num_channels > 1:
            # Interleaved layout: L R L R ...
            reshaped = audio_np.reshape(-1, num_channels)
            n_mono = reshaped.shape[0]
            ambient_chunk = self._next_ambient_chunk(n_mono)
            mixed = reshaped.astype(np.float32)
            mixed += ambient_chunk[:, None] * self._mix_level
            out = np.clip(mixed, -32768, 32767).astype(np.int16)
            return out.reshape(-1).tobytes()

        ambient_chunk = self._next_ambient_chunk(len(audio_np))
        mixed = audio_np.astype(np.float32) + ambient_chunk.astype(np.float32) * self._mix_level
        return np.clip(mixed, -32768, 32767).astype(np.int16).tobytes()

    def _next_ambient_chunk(self, n_samples: int) -> np.ndarray:
        """Return the next ``n_samples`` of ambient audio, wrapping at EOF."""
        ambient = self._ambient
        assert ambient is not None
        total = len(ambient)
        if total == 0:
            return np.zeros(n_samples, dtype=np.int16)

        out = np.empty(n_samples, dtype=np.int16)
        filled = 0
        while filled < n_samples:
            take = min(n_samples - filled, total - self._pos)
            out[filled : filled + take] = ambient[self._pos : self._pos + take]
            self._pos += take
            filled += take
            if self._pos >= total:
                self._pos = 0  # seamless loop
        return out
