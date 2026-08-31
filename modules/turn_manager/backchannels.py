"""Pre-generated backchannel audio clips for active listening."""

from __future__ import annotations

import io
import os
import random
import wave
from typing import Literal

import aiohttp
import numpy as np
from loguru import logger

from pipecat.frames.frames import Frame, OutputAudioRawFrame, StartFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

BackchannelVoice = Literal["elevenlabs", "ultravelabs"]

DEFAULT_PHRASES = ("mm-hmm", "right", "yeah", "I see")


class BackchannelClipStore:
    """Generate and cache short backchannel PCM clips at init.

    Clips use the same voice provider / voice ID as the main agent TTS so
    timbre stays consistent mid-call (an UltraVoice agent gets UltraVoice
    backchannels, not ElevenLabs).
    """

    def __init__(
        self,
        *,
        voice: BackchannelVoice = "elevenlabs",
        sample_rate: int = 24_000,
        phrases: tuple[str, ...] = DEFAULT_PHRASES,
        elevenlabs_api_key: str | None = None,
        elevenlabs_voice_id: str | None = None,
        ultravoice_api_key: str | None = None,
        ultravoice_voice_id: str | None = None,
        ultravoice_api_url: str | None = None,
    ):
        self._voice = voice
        self._sample_rate = sample_rate
        self._phrases = phrases
        self._clips: dict[str, bytes] = {}

        self._elevenlabs_api_key = elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY")
        self._elevenlabs_voice_id = elevenlabs_voice_id or os.getenv("ELEVENLABS_VOICE_ID")
        self._ultraveloice_api_key = ultravoice_api_key or os.getenv("ULTRAVOICE_ASR_KEY") or os.getenv("ULTRAVOICE_API_KEY")
        self._ultraveloice_voice_id = (
            ultravoice_voice_id
            or os.getenv("ULTRAVOICE_TTS_VOICE_ID")
            or os.getenv("ULTRAVOICE_VOICE_ID")
        )
        self._ultraveloice_api_url = (
            ultravoice_api_url
            or os.getenv("ULTRAVOICE_API_URL", "https://api.ultravelabs.ai/v1/tts")
        )

    @property
    def ready(self) -> bool:
        return bool(self._clips)

    def random_phrase(self) -> str:
        return random.choice(self._phrases)

    def get_clip(self, phrase: str) -> bytes | None:
        return self._clips.get(phrase)

    async def generate(self) -> None:
        """Synthesize all phrases. Falls back to a tone stub if APIs are unavailable."""
        for phrase in self._phrases:
            try:
                pcm = await self._synthesize(phrase)
                self._clips[phrase] = pcm
                logger.debug(f"BackchannelClipStore: generated '{phrase}' ({len(pcm)} bytes PCM)")
            except Exception as exc:
                logger.warning(
                    f"BackchannelClipStore: failed to synthesize '{phrase}' via {self._voice}: {exc}. "
                    "Using synthetic stub."
                )
                self._clips[phrase] = self._synthetic_stub(phrase)

    async def _synthesize(self, text: str) -> bytes:
        if self._voice == "ultravelabs":
            return await self._synthesize_ultravelabs(text)
        return await self._synthesize_elevenlabs(text)

    async def _synthesize_elevenlabs(self, text: str) -> bytes:
        if not self._elevenlabs_api_key or not self._elevenlabs_voice_id:
            raise RuntimeError("ElevenLabs API key or voice ID missing")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self._elevenlabs_voice_id}"
        headers = {
            "xi-api-key": self._elevenlabs_api_key,
            "Accept": "audio/wav",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"ElevenLabs TTS HTTP {resp.status}: {body[:200]}")
                wav_bytes = await resp.read()
        return self._wav_to_pcm(wav_bytes, self._sample_rate)

    async def _synthesize_ultravelabs(self, text: str) -> bytes:
        """UltraVoice / UltraLabs TTS — configure via env when the public API is available."""
        if not self._ultraveloice_api_key or not self._ultraveloice_voice_id:
            raise RuntimeError("UltraVoice API key or voice ID missing")

        headers = {
            "Authorization": f"Bearer {self._ultraveloice_api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/wav",
        }
        payload = {
            "text": text,
            "voice_id": self._ultraveloice_voice_id,
            "sample_rate": self._sample_rate,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self._ultraveloice_api_url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"UltraVoice TTS HTTP {resp.status}: {body[:200]}")
                audio_bytes = await resp.read()

        if audio_bytes[:4] == b"RIFF":
            return self._wav_to_pcm(audio_bytes, self._sample_rate)
        # Assume raw PCM int16 mono
        return audio_bytes

    @staticmethod
    def _wav_to_pcm(wav_bytes: bytes, target_rate: int) -> bytes:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())

        samples = np.frombuffer(frames, dtype=np.int16)
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)

        if sample_rate != target_rate and len(samples) > 0:
            duration = len(samples) / sample_rate
            n_out = int(round(duration * target_rate))
            x_old = np.linspace(0.0, 1.0, num=len(samples), endpoint=False)
            x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
            samples = np.interp(x_new, x_old, samples.astype(np.float64)).astype(np.int16)

        return samples.tobytes()

    def _synthetic_stub(self, phrase: str) -> bytes:
        """Quiet placeholder tone when TTS APIs are unavailable (dev / CI)."""
        duration = 0.25 + 0.05 * len(phrase.split())
        n = int(self._sample_rate * duration)
        t = np.arange(n, dtype=np.float64) / self._sample_rate
        freq = 180.0 + (hash(phrase) % 80)
        tone = (np.sin(2 * np.pi * freq * t) * 8000).astype(np.int16)
        return tone.tobytes()


class BackchannelInjector(FrameProcessor):
    """Plays queued backchannel PCM after TTS — required because LLM drops raw audio frames.

    Pair with ``TurnManager`` by passing the same ``asyncio.Queue`` instance.
    Place immediately after TTS in the pipeline::

        ... → TTS → BackchannelInjector → transport.output()
    """

    def __init__(self, queue: asyncio.Queue, **kwargs):
        super().__init__(**kwargs)
        self._queue = queue
        self._sample_rate = 24_000
        self._channels = 1
        self._drain_task: asyncio.Task | None = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, StartFrame):
            self._sample_rate = frame.audio_out_sample_rate
            if self._drain_task is None:
                self._drain_task = self.create_task(
                    self._drain_queue(),
                    name=f"{self}::backchannel_drain",
                )

        await self.push_frame(frame, direction)

    async def _drain_queue(self):
        while True:
            audio, sample_rate, channels = await self._queue.get()
            await self.push_frame(
                OutputAudioRawFrame(
                    audio=audio,
                    sample_rate=sample_rate,
                    num_channels=channels,
                ),
                FrameDirection.DOWNSTREAM,
            )
            self._queue.task_done()
