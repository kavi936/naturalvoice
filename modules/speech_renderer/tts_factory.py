"""Factory for TTS services used by the demo pipeline."""

from __future__ import annotations

import os

from loguru import logger

from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.tts_service import TTSService

from .ultravoice_tts import UltraVoiceTTSService

try:
    from pipecat.services.fish.tts import FishAudioTTSService
except ImportError:
    FishAudioTTSService = None  # type: ignore[misc, assignment]


def create_tts_service(engine: str | None = None) -> TTSService:
    """Instantiate TTS for ``TTS_ENGINE`` env (ultravoice | elevenlabs | fish_audio)."""
    engine = (engine or os.getenv("TTS_ENGINE", "ultravoice")).lower().strip()

    if engine == "ultravoice":
        api_key = os.getenv("ULTRAVOICE_ASR_KEY") or os.getenv("ULTRAVOICE_API_KEY")
        voice_id = os.getenv("ULTRAVOICE_TTS_VOICE_ID") or os.getenv("ULTRAVOICE_VOICE_ID")
        if not api_key or not voice_id:
            raise RuntimeError(
                "UltraVoice TTS requires ULTRAVOICE_ASR_KEY (or ULTRAVOICE_API_KEY) "
                "and ULTRAVOICE_TTS_VOICE_ID"
            )
        logger.info("TTS engine: UltraVoice USF Mini")
        return UltraVoiceTTSService(api_key=api_key, voice_id=voice_id)

    if engine == "fish_audio":
        if FishAudioTTSService is None:
            raise RuntimeError('Fish Audio requires pipecat-ai[fish]. pip install "pipecat-ai[fish]"')
        api_key = os.environ["FISH_AUDIO_API_KEY"]
        ref = os.getenv("FISH_AUDIO_VOICE_ID")
        logger.info("TTS engine: Fish Audio")
        return FishAudioTTSService(api_key=api_key, reference_id=ref)

    # Default fallback: ElevenLabs
    logger.info("TTS engine: ElevenLabs")
    return ElevenLabsTTSService(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        voice_id=os.getenv("ELEVENLABS_VOICE_ID") or None,
    )
