# Ambient Layer

Injects context-appropriate **room tone** into the agent's outgoing TTS stream so calls don't sound studio-clean.

## Why

Silence on the agent side is an acoustic tell. Real calls carry environment bleed (restaurant floor, office HVAC). Mixing a low-level loop into outbound audio restores that social/acoustic cue without changing STT, LLM, or TTS models.

## Usage

```python
from modules.ambient import AmbientMixer

ambient = AmbientMixer(profile="restaurant", mix_level=0.15)

pipeline = Pipeline([
    transport.input(),
    stt,
    user_aggregator,
    llm,
    tts,
    ambient,              # after TTS, before transport output
    transport.output(),
    assistant_aggregator,
])
```

### Constructor

| Arg | Type | Default | Notes |
|---|---|---|---|
| `profile` | `str` | `"restaurant"` | `"restaurant"`, `"office"`, or `"none"` |
| `mix_level` | `float` | `0.15` | 0.0–1.0 gain of ambient relative to TTS |
| `profiles_dir` | `Path \| str` | bundled `profiles/` | Override for custom WAVs |

### Mid-call switch

```python
ambient.set_profile("office")
ambient.mix_level = 0.1
```

## Profiles

Bundled placeholders live in `profiles/`:

- `restaurant.wav` — mid-band chatter-like bed
- `office.wav` — quieter HVAC / open-plan hum

Regenerate synthesized placeholders:

```bash
python modules/ambient/generate_profiles.py
```

Replace with royalty-free recordings for public demos. Mono PCM WAV preferred; the mixer resamples to the transport output rate on `StartFrame`.

## Design notes

- Implements a Pipecat `FrameProcessor` and only mixes `OutputAudioRawFrame` (including TTS audio). Inbound mic audio is never touched.
- Ambient loops seamlessly when the WAV ends.
- **Limitation:** in pipeline mode, ambient only rides frames that already carry TTS/output audio. For continuous room tone during silence, attach the same WAVs via a transport-level `BaseAudioMixer` / `SoundfileMixer`.
- Default `mix_level=0.15` is intentional — high enough to read as “present,” low enough not to mask speech.

## Related TTS backends

naturalvoice treats TTS as swappable. Ambient sits **after** synthesis, so it works the same for ElevenLabs, UltraVoice, Fish Audio, or any other provider that emits PCM frames into the Pipecat pipeline.
