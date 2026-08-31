"""UltraVoice USF Mini TTS — HTTP streaming adapter for Pipecat."""

from __future__ import annotations

import io
import os
import wave
from collections.abc import AsyncGenerator

import aiohttp
import numpy as np
from loguru import logger

from pipecat.frames.frames import TTSAudioRawFrame, TTSStartedFrame, TTSStoppedFrame
from pipecat.services.tts_service import TTSService

DEFAULT_USF_TTS_URL = os.getenv(
    "ULTRAVOICE_TTS_URL",
    "https://api.us.tech/v1/tts/synthesize",
)


class UltraVoiceTTSService(TTSService):
    """USF Mini TTS via configurable HTTP endpoint (UltraVoice primary stack).

    Configure with ``ULTRAVOICE_ASR_KEY`` / ``ULTRAVOICE_TTS_VOICE_ID`` and
    optionally ``ULTRAVOICE_TTS_URL`` when the hosted endpoint differs.
    """

    def __init__(
        self,
        *,
        api_key: str,
        voice_id: str,
        url: str | None = None,
        model: str = "usf-mini-tts",
        sample_rate: int = 24_000,
        **kwargs,
    ):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self._api_key = api_key
        self._voice_id = voice_id
        self._url = url or DEFAULT_USF_TTS_URL
        self._model = model

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        if not text.strip():
            return

        await self.start_ttfb_metrics()
        await self.start_tts_usage_metrics(text)

        yield TTSStartedFrame()
        try:
            pcm = await self._synthesize(text)
            await self.stop_ttfb_metrics()
            if pcm:
                yield TTSAudioRawFrame(
                    audio=pcm,
                    sample_rate=self.sample_rate,
                    num_channels=1,
                )
        except Exception as exc:
            logger.error(f"{self}: UltraVoice TTS failed: {exc}")
            await self.push_error(error_msg=f"UltraVoice TTS error: {exc}", exception=exc)
        finally:
            yield TTSStoppedFrame()

    async def _synthesize(self, text: str) -> bytes:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/wav",
        }
        payload = {
            "text": text,
            "voice_id": self._voice_id,
            "model": self._model,
            "sample_rate": self.sample_rate,
            "format": "pcm16",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self._url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"USF Mini TTS HTTP {resp.status}: {body[:300]}")
                data = await resp.read()

        if data[:4] == b"RIFF":
            return self._wav_to_pcm(data)
        return data

    def _wav_to_pcm(self, wav_bytes: bytes) -> bytes:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            channels = wf.getnchannels()
            rate = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        samples = np.frombuffer(frames, dtype=np.int16)
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)
        if rate != self.sample_rate and len(samples) > 0:
            duration = len(samples) / rate
            n_out = int(round(duration * self.sample_rate))
            x_old = np.linspace(0.0, 1.0, num=len(samples), endpoint=False)
            x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
            samples = np.interp(x_new, x_old, samples.astype(np.float64)).astype(np.int16)
        return samples.tobytes()
