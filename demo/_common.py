"""Shared Pipecat bot wiring for baseline vs naturalvoice demos."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams
from pipecat.turns.user_stop.external_user_turn_stop_strategy import (
    ExternalUserTurnStopStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from modules.ambient.ambient_mixer import AmbientMixer  # noqa: E402
from modules.speech_renderer import SpeechRenderer, create_tts_service  # noqa: E402
from modules.turn_manager import BackchannelInjector, TurnManager, create_stt_service  # noqa: E402

load_dotenv(dotenv_path=_REPO_ROOT / ".env", override=True)

_BASE_SYSTEM_INSTRUCTION = (
    "You are a helpful restaurant host taking a phone reservation. "
    "Keep replies short and spoken aloud — no lists, markdown, or emojis."
)

TRANSPORT_PARAMS = {
    "daily": lambda: DailyParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
    ),
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
    ),
}


def _require_env(*keys: str) -> None:
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill them in."
        )


def _validate_env(*, use_speech_renderer: bool, use_turn_manager: bool) -> None:
    _require_env("OPENAI_API_KEY")
    use_usf = os.getenv("USE_USF_ASR", "false").lower() in ("1", "true", "yes")
    if use_usf:
        _require_env("ULTRAVOICE_ASR_KEY")
    else:
        _require_env("DEEPGRAM_API_KEY")

    tts_engine = os.getenv("TTS_ENGINE", "elevenlabs" if not use_speech_renderer else "ultravoice")
    if use_speech_renderer or tts_engine == "ultravoice":
        if not (os.getenv("ULTRAVOICE_ASR_KEY") or os.getenv("ULTRAVOICE_API_KEY")):
            if tts_engine == "ultravoice":
                raise RuntimeError("TTS_ENGINE=ultravoice requires ULTRAVOICE_ASR_KEY")
        if tts_engine == "ultravoice" and not (
            os.getenv("ULTRAVOICE_TTS_VOICE_ID") or os.getenv("ULTRAVOICE_VOICE_ID")
        ):
            raise RuntimeError("TTS_ENGINE=ultravoice requires ULTRAVOICE_TTS_VOICE_ID")
    if tts_engine == "elevenlabs" or not use_speech_renderer:
        _require_env("ELEVENLABS_API_KEY")
    if tts_engine == "fish_audio":
        _require_env("FISH_AUDIO_API_KEY")


def _resolve_voice_ids(tts_engine: str) -> tuple[str | None, str | None]:
    eleven = os.getenv("ELEVENLABS_VOICE_ID")
    ultra = os.getenv("ULTRAVOICE_TTS_VOICE_ID") or os.getenv("ULTRAVOICE_VOICE_ID")
    return eleven, ultra


async def run_bot(
    transport: BaseTransport,
    runner_args: RunnerArguments,
    *,
    use_ambient: bool,
    use_turn_manager: bool,
    use_speech_renderer: bool,
) -> None:
    """Build and run the voice pipeline."""
    _validate_env(
        use_speech_renderer=use_speech_renderer,
        use_turn_manager=use_turn_manager,
    )

    parts = []
    if use_speech_renderer:
        parts.append("speech-renderer ON")
    if use_turn_manager:
        parts.append("turn-manager ON")
    if use_ambient:
        parts.append("ambient ON")
    label = "demo (" + ", ".join(parts) + ")" if parts else "baseline"
    logger.info(f"Starting naturalvoice {label}")

    stt = create_stt_service()

    tts_engine = os.getenv(
        "TTS_ENGINE",
        "ultravoice" if use_speech_renderer else "elevenlabs",
    )
    eleven_voice, ultra_voice = _resolve_voice_ids(tts_engine)

    speech_renderer: SpeechRenderer | None = None
    system_instruction = _BASE_SYSTEM_INSTRUCTION
    if use_speech_renderer:
        speech_renderer = SpeechRenderer(
            tts_engine=tts_engine,  # type: ignore[arg-type]
            filler_intensity=float(os.getenv("FILLER_INTENSITY", "0.7")),
            emit_pause_tokens=True,
        )
        system_instruction = speech_renderer.shape_system_prompt(_BASE_SYSTEM_INSTRUCTION)
        logger.info(f"Speech Renderer active (engine={tts_engine}, Stage 1+2)")

    llm = OpenAILLMService(
        api_key=os.environ["OPENAI_API_KEY"],
        settings=OpenAILLMService.Settings(system_instruction=system_instruction),
    )

    tts = (
        create_tts_service(tts_engine)
        if use_speech_renderer
        else create_tts_service("elevenlabs")
    )

    user_turn_strategies = None
    if use_turn_manager:
        user_turn_strategies = UserTurnStrategies(
            stop=[ExternalUserTurnStopStrategy(timeout=0.5)],
        )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
            user_turn_strategies=user_turn_strategies,
        ),
    )

    backchannel_queue: asyncio.Queue | None = None
    turn_manager: TurnManager | None = None
    backchannel_injector: BackchannelInjector | None = None

    if use_turn_manager:
        backchannel_queue = asyncio.Queue()
        bc_voice = "ultravelabs" if tts_engine == "ultravoice" else "elevenlabs"
        turn_manager = TurnManager(
            patience_window_ms=int(os.getenv("TURN_PATIENCE_MS", "600")),
            backchannel_voice=bc_voice,  # type: ignore[arg-type]
            elevenlabs_voice_id=eleven_voice,
            ultravoice_voice_id=ultra_voice,
            debug_mode=os.getenv("TURN_DEBUG", "").lower() in ("1", "true", "yes"),
            backchannel_queue=backchannel_queue,
        )
        backchannel_injector = BackchannelInjector(queue=backchannel_queue)

    stages = [transport.input(), stt]
    if turn_manager:
        stages.append(turn_manager)
    stages.append(user_aggregator)
    stages.append(llm)
    if speech_renderer:
        stages.append(speech_renderer.markup_processor)
    stages.append(tts)
    if backchannel_injector:
        stages.append(backchannel_injector)
    if use_ambient:
        stages.append(
            AmbientMixer(
                profile=os.getenv("AMBIENT_PROFILE", "restaurant"),
                mix_level=float(os.getenv("AMBIENT_MIX_LEVEL", "0.15")),
            )
        )
    stages.extend([transport.output(), assistant_aggregator])

    pipeline = Pipeline(stages)
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected — starting greeting")
        context.add_message(
            {
                "role": "developer",
                "content": "Greet the caller briefly and ask how you can help with their reservation.",
            }
        )
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await runner.cancel()

    await runner.run()


async def bot_entry(
    runner_args: RunnerArguments,
    *,
    use_ambient: bool,
    use_turn_manager: bool = False,
    use_speech_renderer: bool = False,
) -> None:
    transport = await create_transport(runner_args, TRANSPORT_PARAMS)
    await run_bot(
        transport,
        runner_args,
        use_ambient=use_ambient,
        use_turn_manager=use_turn_manager,
        use_speech_renderer=use_speech_renderer,
    )
