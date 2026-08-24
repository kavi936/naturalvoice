"""Shared Pipecat bot wiring for baseline vs ambient demos.

Kept in one place so the only intentional difference between run_baseline.py
and run_demo.py is whether AmbientMixer is in the pipeline.
"""

from __future__ import annotations

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
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams
from pipecat.workers.runner import WorkerRunner

# Allow `python demo/run_demo.py` to import `modules.*` from the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from modules.ambient.ambient_mixer import AmbientMixer  # noqa: E402

load_dotenv(dotenv_path=_REPO_ROOT / ".env", override=True)

_SYSTEM_INSTRUCTION = (
    "You are a helpful restaurant host taking a phone reservation. "
    "Keep replies short and spoken aloud — no lists, markdown, or emojis."
)

# Transport params are deferred via lambdas so the Pipecat runner can pick
# Daily / WebRTC / etc. at launch time (`--transport daily`).
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


async def run_bot(
    transport: BaseTransport,
    runner_args: RunnerArguments,
    *,
    use_ambient: bool,
) -> None:
    """Build and run the voice pipeline.

    Args:
        transport: Daily / WebRTC transport from the Pipecat runner.
        runner_args: Runner CLI arguments (idle timeout, signal handling).
        use_ambient: If True, insert AmbientMixer after TTS (naturalvoice demo).
                     If False, identical stack without ambient (baseline).
    """
    _require_env(
        "DEEPGRAM_API_KEY",
        "OPENAI_API_KEY",
        "ELEVENLABS_API_KEY",
    )

    label = "demo (ambient ON)" if use_ambient else "baseline (ambient OFF)"
    logger.info(f"Starting naturalvoice {label}")

    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])

    llm = OpenAILLMService(
        api_key=os.environ["OPENAI_API_KEY"],
        settings=OpenAILLMService.Settings(system_instruction=_SYSTEM_INSTRUCTION),
    )

    tts = ElevenLabsTTSService(
        api_key=os.environ["ELEVENLABS_API_KEY"],
        voice_id=os.getenv("ELEVENLABS_VOICE_ID") or None,
    )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    # Pipeline stages. AmbientMixer sits after TTS so room tone rides on
    # outbound audio only — never mixed into the caller's mic path.
    stages = [
        transport.input(),
        stt,
        user_aggregator,
        llm,
        tts,
    ]
    if use_ambient:
        stages.append(
            AmbientMixer(
                profile=os.getenv("AMBIENT_PROFILE", "restaurant"),
                mix_level=float(os.getenv("AMBIENT_MIX_LEVEL", "0.15")),
            )
        )
    stages.extend(
        [
            transport.output(),
            assistant_aggregator,
        ]
    )

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


async def bot_entry(runner_args: RunnerArguments, *, use_ambient: bool) -> None:
    """Pipecat Cloud / runner-compatible entrypoint."""
    # Daily is preferred for the README quickstart; WebRTC works for local tests.
    transport = await create_transport(runner_args, TRANSPORT_PARAMS)
    await run_bot(transport, runner_args, use_ambient=use_ambient)
