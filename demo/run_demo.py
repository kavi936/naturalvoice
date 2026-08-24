#!/usr/bin/env python3
"""naturalvoice demo — baseline stack + AmbientMixer after TTS.

Compare this against `python demo/run_baseline.py` (identical pipeline, no ambient).

Usage:
    python demo/run_demo.py -t daily
    # or local browser WebRTC:
    python demo/run_demo.py -t webrtc

Optional .env knobs:
    AMBIENT_PROFILE=restaurant|office|none
    AMBIENT_MIX_LEVEL=0.15
"""

from pipecat.runner.types import RunnerArguments

from _common import bot_entry


async def bot(runner_args: RunnerArguments):
    await bot_entry(runner_args, use_ambient=True)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
