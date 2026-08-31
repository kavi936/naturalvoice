#!/usr/bin/env python3
"""Baseline — default Deepgram + ElevenLabs, no naturalvoice modules."""

from pipecat.runner.types import RunnerArguments

from _common import bot_entry


async def bot(runner_args: RunnerArguments):
    await bot_entry(
        runner_args,
        use_ambient=False,
        use_turn_manager=False,
        use_speech_renderer=False,
    )


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
