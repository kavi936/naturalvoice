#!/usr/bin/env python3
"""naturalvoice demo — full stack: Turn Manager + Speech Renderer + Ambient.

Compare against `python demo/run_baseline.py` (unmodified Pipecat stack).

Usage:
    python demo/run_demo.py -t daily

Optional .env:
    TTS_ENGINE=ultravoice|elevenlabs|fish_audio
    USE_USF_ASR=true
    FILLER_INTENSITY=0.7
    TURN_PATIENCE_MS=600
    AMBIENT_PROFILE=restaurant
"""

from pipecat.runner.types import RunnerArguments

from _common import bot_entry


async def bot(runner_args: RunnerArguments):
    await bot_entry(
        runner_args,
        use_ambient=True,
        use_turn_manager=True,
        use_speech_renderer=True,
    )


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
