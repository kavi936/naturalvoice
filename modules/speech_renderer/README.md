# Speech Renderer

Two-stage pipeline that transforms LLM output into **naturalistic spoken audio**.

UltraVoice USF Mini TTS is the **primary** target. ElevenLabs and Fish Audio are supported fallbacks via the same `TTSMarkupProcessor` class (`tts_engine` parameter).

---

## Why two stages?

| Stage | File | When | What it does |
|---|---|---|---|
| **1 — Prompt shaping** | `system_prompt_injector.py` | Pipeline init (once) | Prepends spoken-register rules to the system prompt so the LLM *generates* conversational text |
| **2 — TTS markup** | `tts_markup_processor.py` | Every LLM token/frame | Strips leaked markdown, applies engine-specific pause/elongation markup before TTS |

These are **separate concerns**:

- Stage 1 affects *what* the LLM says (register, fillers, clause length).
- Stage 2 affects *how TTS renders it* (pauses, em-dashes, elongation) without re-prompting the model.

You can use either stage alone via `renderer.injector` or `renderer.markup_processor`.

---

## Before / after example

**Raw LLM output (baseline):**
```
We do not have availability for Saturday evening. Furthermore, the next opening is at 7:30 PM.
```

**After Stage 1 (prompt-shaped LLM output — typical):**
```
Hmm, let me check... Ahh, unfortunately looks like we're fully booked Saturday evening — but I've got 7:30 open if that works?
```

**After Stage 2 (`TTSMarkupProcessor`, ultravoice):**
```
Hmm, let me check... Ahh, unfortunately looks like we're fully booked Saturday evening, but I've got 7:30 open if that works?
```
(`[pause]` tokens → `...`; em-dashes → `, ` for USF Mini until SSML is confirmed)

**What TTS receives:** the Stage 2 string above, synthesized by USF Mini TTS / ElevenLabs / Fish Audio.

---

## Usage

```python
from modules.speech_renderer import SpeechRenderer

renderer = SpeechRenderer(
    tts_engine="ultravoice",
    filler_intensity=0.7,
    emit_pause_tokens=True,
)

system_prompt = renderer.shape_system_prompt("You are a restaurant host...")
# Pass system_prompt to your LLM at init

pipeline = Pipeline([
    ...
    llm,
    renderer.markup_processor,  # Stage 2 — between LLM and TTS
    tts,
    ...
])
```

---

## Primary tuning knob: `filler_intensity`

| Value | Deployment | Behavior |
|---|---|---|
| **0.3** | Professional / formal | Minimal fillers, fewer hedges |
| **0.7** | Casual conversational (default) | Natural "one sec…", "let me check…" at processing moments |
| **1.0** | Maximum naturalness | Generous fillers and floor-holding language |

Set via constructor or `FILLER_INTENSITY=0.7` in `.env`.

---

## Engine markup matrix

| Engine | Pause syntax | Breaks | Elongation | SSML |
|---|---|---|---|---|
| **ultravoice** (USF Mini) | `[pause]` → `...` | em-dash → `, ` | Sooo, Yeahhh, Ahhhh | **TODO** — see below |
| **elevenlabs** | `[pause]` → `...` | em-dash preserved | vowel repeat | punctuation-driven |
| **fish_audio** | `[pause]` → `...` | em-dash → `, ` | vowel repeat | punctuation-driven |

### USF Mini TTS SSML TODO

We have **not yet confirmed** whether USF Mini TTS supports SSML `<break time="300ms"/>` or `<prosody rate="slow">`.

**Contributors:** test with your UltraVoice API key:

```bash
curl -X POST "$ULTRAVOICE_TTS_URL" \
  -H "Authorization: Bearer $ULTRAVOICE_ASR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello<break time=\"300ms\"/>world", "voice_id": "..."}'
```

If SSML works, update `_apply_ultravoice()` in `tts_markup_processor.py`:

- `[pause]` → `<break time="300ms"/>`
- clause boundaries → `<break time="150ms"/>`
- uncertainty hedges → `<prosody rate="slow">...</prosody>`

Until confirmed, **punctuation-driven prosody** is the safe default for UltraVoice.

---

## Environment variables

See `.env.example` for:

- `TTS_ENGINE=ultravoice|elevenlabs|fish_audio`
- `ULTRAVOICE_ASR_KEY` / `ULTRAVOICE_TTS_VOICE_ID`
- `USE_USF_ASR=true` (swap Deepgram for USF ASR — see `modules/turn_manager/usf_asr.py`)
- `FILLER_INTENSITY=0.7`

---

## Full pipeline placement

```
input
  → Deepgram / USF ASR          (USE_USF_ASR)
  → TurnManager
  → user_aggregator
  → LLM                         (system prompt shaped by Stage 1 at init)
  → TTSMarkupProcessor          (Stage 2)
  → USF Mini TTS / ElevenLabs / Fish Audio
  → BackchannelInjector
  → AmbientMixer
  → output
```
