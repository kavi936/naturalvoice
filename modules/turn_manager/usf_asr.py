"""USF ASR drop-in — Deepgram-compatible WebSocket pointed at UltraVoice ASR."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from urllib.parse import urlencode

from loguru import logger

from pipecat.frames.frames import (
    InterimTranscriptionFrame,
    TranscriptionFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.deepgram.stt import DeepgramSTTService, DeepgramSTTSettings
from pipecat.transcriptions.language import Language
from pipecat.utils.time import time_now_iso8601

try:
    import websockets
except ImportError as e:
    raise ImportError("websockets is required for USF ASR") from e

# USF ASR speaks the Deepgram-compatible wire format on this endpoint.
USF_ASR_BASE_URL = os.getenv(
    "USF_ASR_BASE_URL",
    "wss://api-asr.us.tech/v1/audio/transcriptions/stream",
)
USF_ASR_MODEL = os.getenv("USF_ASR_MODEL", "usf-asr-en")


class USFASRService(DeepgramSTTService):
    """Drop-in STT adapter for UltraVoice USF ASR.

    When ``USE_USF_ASR=true``, swap this in place of ``DeepgramSTTService``.
    Only the WebSocket URL and auth header change — Bearer token instead of
    Deepgram ``Token`` — so Turn Manager's confidence + timestamp logic stays
    identical.
    """

    def __init__(self, *, api_key: str, **kwargs):
        settings = DeepgramSTTSettings(
            model=USF_ASR_MODEL,
            language=Language.EN,
            interim_results=True,
            punctuate=True,
        )
        # Initialize parent without opening a Deepgram client connection.
        super().__init__(
            api_key=api_key,
            settings=settings,
            sample_rate=kwargs.pop("sample_rate", 16_000),
            encoding="linear16",
            channels=1,
            **kwargs,
        )
        self._usf_api_key = api_key
        self._ws: websockets.WebSocketClientProtocol | None = None
        # Prevent Deepgram SDK client from being used
        self._client = None  # type: ignore[assignment]

    async def _connect(self):
        logger.debug(f"{self}: Connecting to USF ASR at {USF_ASR_BASE_URL}")
        self._quick_failure_tracker.reset()
        self._connection_task = self.create_task(self._usf_connection_handler())

    async def _disconnect(self):
        if not self._connection_task:
            return
        self._connection_ready.clear()
        ws = self._ws
        self._ws = None
        if ws and ws.open:
            await ws.close()
        await self.cancel_task(self._connection_task)
        self._connection_task = None

    def _build_ws_url(self) -> str:
        params = {
            "model": USF_ASR_MODEL,
            "encoding": self._encoding,
            "sample_rate": str(self.sample_rate),
            "channels": str(self._channels),
            "interim_results": "true",
            "punctuate": "true",
        }
        separator = "&" if "?" in USF_ASR_BASE_URL else "?"
        return f"{USF_ASR_BASE_URL}{separator}{urlencode(params)}"

    async def _usf_connection_handler(self):
        """Maintain USF ASR WebSocket with automatic reconnect."""
        while True:
            try:
                url = self._build_ws_url()
                headers = {"Authorization": f"Bearer {self._usf_api_key}"}
                async with websockets.connect(url, additional_headers=headers) as ws:
                    self._ws = ws
                    self._connection_ready.set()
                    logger.debug(f"{self}: USF ASR WebSocket connected")
                    async for raw in ws:
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8", errors="ignore")
                        await self._handle_json_message(raw)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"{self}: USF ASR connection error: {exc}")
                await self.push_error(error_msg=f"USF ASR connection error: {exc}", exception=exc)
                self._connection_ready.clear()
                self._ws = None
                await asyncio.sleep(1.0)

    async def run_stt(self, audio: bytes):
        if self._ws and self._ws.open:
            try:
                await self._ws.send(audio)
            except Exception as exc:
                logger.warning(f"{self}: USF ASR send failed: {exc}")
                self._ws = None
        yield None

    async def _handle_json_message(self, raw: str):
        """Parse Deepgram-compatible JSON payloads from USF ASR."""
        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            return

        if data.get("type") == "Results" or "channel" in data:
            await self._emit_transcription(data)
        elif data.get("type") == "Metadata":
            logger.trace(f"{self}: USF ASR metadata: {data}")

    async def _emit_transcription(self, data: dict[str, Any]):
        channel = data.get("channel") or {}
        alts = channel.get("alternatives") or []
        if not alts:
            return
        alt = alts[0]
        transcript = (alt.get("transcript") or "").strip()
        is_final = bool(data.get("is_final") or data.get("speech_final"))
        language = None
        langs = alt.get("languages") or alt.get("language")
        if isinstance(langs, list) and langs:
            language = Language(langs[0])
        elif isinstance(langs, str):
            language = Language(langs)

        if is_final:
            if transcript:
                await self.emit_stt_usage_metrics()
                await self.push_frame(
                    TranscriptionFrame(
                        transcript,
                        self._user_id,
                        time_now_iso8601(),
                        language,
                        result=data,
                    )
                )
                await self._handle_transcription(transcript, True, language)
                await self.stop_processing_metrics()
        elif transcript:
            await self.push_frame(
                InterimTranscriptionFrame(
                    transcript,
                    self._user_id,
                    time_now_iso8601(),
                    language,
                    result=data,
                )
            )

    async def process_frame(self, frame, direction: FrameDirection):
        """Skip Deepgram finalize — USF ASR uses its own endpointing."""
        from pipecat.frames.frames import VADUserStartedSpeakingFrame
        from pipecat.services.stt_service import STTService

        await STTService.process_frame(self, frame, direction)
        if isinstance(frame, VADUserStartedSpeakingFrame):
            await self._start_metrics()


def create_stt_service(*, use_usf: bool | None = None):
    """Return Deepgram STT or USF ASR based on ``USE_USF_ASR`` env."""
    if use_usf is None:
        use_usf = os.getenv("USE_USF_ASR", "false").lower() in ("1", "true", "yes")

    if use_usf:
        api_key = os.getenv("ULTRAVOICE_ASR_KEY") or os.getenv("ULTRAVOICE_API_KEY")
        if not api_key:
            raise RuntimeError("USE_USF_ASR=true requires ULTRAVOICE_ASR_KEY")
        logger.info("STT engine: USF ASR (UltraVoice)")
        return USFASRService(api_key=api_key)

    from pipecat.services.deepgram.stt import DeepgramSTTService as DG

    logger.info("STT engine: Deepgram")
    return DG(api_key=os.environ["DEEPGRAM_API_KEY"])
