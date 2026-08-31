# Turn Manager

Replaces binary VAD with a **four-state conversational model** that decides when the agent may respond, when to hold (thinking pause), and when the caller is talking to someone else.

## States

```
                    ┌──────────────────────────────────────┐
                    │                                      │
         speech     │         ┌──────────┐   patience +   │
    ┌──────────────►│ SPEAKING │──────────►│  THINKING  │──┼──► DONE ──► LLM
    │               │         └─────┬────┘   complete     │       ▲
    │               │               │                     │       │
    │               │     pause +   │   new speech        │       │
    │               │   mid-clause  │                     │       │
    │               │               ▼                     │       │
    │               │         (hold timer)                │       │
    │               │               │                     │       │
    │               │    conf↓ + vol↓ (both)              │       │
    │               │               ▼                     │       │
    │               │         ┌───────────┐               │       │
    └───────────────┤         │ SIDE_CONVO│───────────────┘       │
      vol↑ + conf↑  │         └───────────┘  recovery             │
                    └──────────────────────────────────────┘
```

| State | Meaning |
|---|---|
| `SPEAKING` | Caller is mid-utterance |
| `THINKING` | Pause detected — caller may still be thinking |
| `SIDE_CONVO` | Caller likely speaking to someone nearby |
| `DONE` | Floor yielded — agent may respond |

## Primary tuning knob: patience window

`patience_window_ms` (default **600 ms**) is how long the manager waits in `THINKING` before emitting `UserStoppedSpeakingFrame` and triggering the LLM.

- **Too low** → agent cuts in during natural pauses ("um… let me check…")
- **Too high** → agent feels sluggish after the caller is clearly done

Start at 600 ms for restaurant booking; increase for older callers or complex forms.

## Side-conversation detection (two-signal)

`SIDE_CONVO` requires **both**:

1. **Deepgram** — mean word confidence below `side_convo_confidence_threshold` (default 0.6)
2. **Audio** — frame RMS drops more than `side_convo_volume_drop` (default 40%) vs a rolling 3-second average

Optional trigger phrases (`"hold on"`, `"one sec"`, etc.) are logged when present but do not bypass the two-signal rule.

Recovery to `SPEAKING`: volume ratio ≥ 70% of rolling average **and** confidence ≥ 0.75.

## Backchannels

While the caller speaks continuously (> `backchannel_threshold_s`, default 3.5 s), the manager queues a pre-generated clip (`"mm-hmm"`, `"right"`, …) at a **clause boundary** (inter-word gap > 200 ms from Deepgram timestamps).

Clips are synthesized at init using the **same voice provider and voice ID** as the main agent (`elevenlabs` or `ultravelabs` / UltraVoice) so timbre stays consistent.

Because the LLM processor drops raw audio frames, pair with `BackchannelInjector` **after TTS**:

```
STT → TurnManager → user_aggregator → LLM → TTS → BackchannelInjector → output
```

## Pipeline integration

Use `ExternalUserTurnStopStrategy` on the user aggregator so turn-end is driven by Turn Manager, not Silero VAD alone:

```python
from pipecat.turns.user_stop.external_user_turn_stop_strategy import ExternalUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from modules.turn_manager import TurnManager, BackchannelInjector

queue = asyncio.Queue()
turn_manager = TurnManager(backchannel_queue=queue, elevenlabs_voice_id=VOICE_ID)
injector = BackchannelInjector(queue=queue)

user_params = LLMUserAggregatorParams(
    vad_analyzer=SileroVADAnalyzer(),
    user_turn_strategies=UserTurnStrategies(
        stop=[ExternalUserTurnStopStrategy(timeout=0.5)],
    ),
)

Pipeline([
    transport.input(),
    stt,
    turn_manager,
    user_aggregator,
    llm,
    tts,
    injector,
    transport.output(),
    assistant_aggregator,
])
```

## Configuration

```python
TurnManager(
    patience_window_ms=600,
    thinking_pause_min_ms=400,
    thinking_pause_max_ms=800,
    backchannel_threshold_s=3.5,
    side_convo_confidence_threshold=0.6,
    side_convo_volume_drop=0.4,
    trigger_phrases=["hold on", "one sec", ...],
    backchannel_voice="elevenlabs",  # or "ultravelabs" (UltraVoice)
    backchannel_volume=0.4,
    debug_mode=False,
)
```

Set `TURN_DEBUG=1` in `.env` to log every transition with triggering signals.

## Debug frames

Every transition emits a `TurnStateChangedFrame` downstream with `state`, `previous_state`, `reason`, and `signals` — useful for logging and tuning.
