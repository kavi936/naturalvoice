#!/usr/bin/env python3
"""Baseline voice agent — same stack as run_demo.py, without AmbientMixer.

Compare this against `python demo/run_demo.py` to hear the acoustic-environment
difference in isolation.

Usage:
    python demo/run_baseline.py -t daily
    # or local browser WebRTC:
    python demo/run_baseline.py -t webrtc
"""

from pipecat.runner.types import RunnerArguments

from _common import bot_entry


async def bot(runner_args: RunnerArguments):
    await bot_entry(runner_args, use_ambient=False)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
