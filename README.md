# naturalvoice

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Pipecat](https://img.shields.io/badge/built%20on-Pipecat-orange)](https://github.com/pipecat-ai/pipecat)

**Voice AI agents are accurate. They're just not human. This is the open protocol to fix that.**

Middleware for Pipecat, LiveKit, and any voice pipeline — ambient room tone, smarter turn-taking, and spoken-register speech rendering. No model swap required.

[Research](./research/problem-analysis.md) · [Roadmap](./ROADMAP.md) · [Contributing](./CONTRIBUTING.md)

---

## Demo

> **Before:** studio-clean silence, rigid turn-taking, "I am checking availability for Saturday evening."  
> **After:** restaurant room tone, patience during thinking pauses, "let me just — yeah, one sec, checking Saturday for you."

```bash
pip install -r requirements.txt && cp .env.example .env
python demo/run_demo.py -t webrtc       # full stack — all three modules
python demo/run_baseline.py -t webrtc   # clean baseline — hear the difference
```

Record a side-by-side clip and open a PR — the best demos get linked here.

---

## The Problem

I called Bodega, a restaurant in San Francisco, to reserve a table. I was connected instantly — no hold music, no wait. The agent knew the availability, handled the booking, and got me off the call in under a minute. Technically flawless.

But something was wrong the entire time.

There was no background noise — none of the ambient hum you'd expect from a restaurant floor. The line was studio-clean, which felt immediately off. When I paused to think, or turned to ask someone nearby a question, the agent cut back in. It had no model for "he's thinking" versus "he's done." And when it processed my request, it said things like *"I am checking availability for Saturday evening."* Not *"let me just — yeah, one sec, checking Saturday for you."* Every response was informationally correct and conversationally dead.

This is the uncanny valley of voice AI. And it isn't a model problem. It's a design problem — four separable, fixable layers that almost no one is addressing at the application layer.

---

## Why Agents Feel Fake

Current voice agents fail at four distinct layers, each beneath the one above it:

| Layer | What breaks | naturalvoice module |
|---|---|---|
| **Acoustic environment** | Silence is a tell. Real calls have room tone and ambient bleed. | Ambient Layer |
| **Turn-taking** | Binary VAD can't distinguish thinking pause, sentence end, or side conversation. | Turn Manager |
| **Linguistic register** | LLMs produce written language. Spoken language is structurally different. | Speech Renderer |
| **Temporal rhythm** | Flat TTS pacing is fatiguing. Human speech has micro-pauses and speed variation. | Speech Renderer (Stage 2 markup) |

The academic literature backs all four. Levinson & Torreira (2015) established that humans predict turn completion and prepare responses in advance — voice agents that wait for full silence are structurally incapable of matching human timing. Production voice AI delivers 1,400–1,700ms median response latency against a 200–300ms human baseline.

> See [`research/problem-analysis.md`](research/problem-analysis.md) for the full cited analysis.

---

## What naturalvoice Does (v0.1)

Three composable middleware modules that sit on top of any voice agent pipeline — Pipecat, LiveKit Agents, Vapi, Retell — without requiring a model swap.

### Module 1 — Ambient Layer
Injects context-appropriate background audio into the agent's outgoing TTS stream. Restaurant, office, and custom profiles. Configurable mix levels. Plugs in as a Pipecat `FrameProcessor` after TTS.

```
TTS output → [AmbientMixer] → caller hears: voice + room tone
```

### Module 2 — Turn Manager
Replaces binary VAD with a four-state conversational model: `SPEAKING`, `THINKING`, `SIDE_CONVO`, `DONE`. Uses Deepgram (or USF ASR) word-level confidence plus audio RMS to classify pause intent. Backchannels ("mm-hmm", "right") at clause boundaries during extended speech. Primary tuning knob: `TURN_PATIENCE_MS` (default 600ms).

```
caller audio → STT → [TurnManager] → THINKING  → agent holds
                                   → DONE       → agent responds
                                   → SIDE_CONVO → agent waits
```

### Module 3 — Speech Renderer
Two-stage pipeline for naturalistic spoken output:

- **Stage 1** — `SystemPromptInjector` shapes LLM register at init (contractions, fillers, hedges, no markdown)
- **Stage 2** — `TTSMarkupProcessor` applies engine-specific prosody markup post-LLM, pre-TTS

Supports `ultravoice` (default), `elevenlabs`, and `fish_audio`. Primary tuning knob: `FILLER_INTENSITY` (default 0.7).

```
LLM output:  "I am checking availability for Saturday."
         ↓ [SpeechRenderer]
TTS input:   "Hmm, let me check... looks like Saturday's open at 7:30?"
```

---

## Architecture

Full demo pipeline (`run_demo.py`):

```
Incoming call
     │
     ▼
STT (Deepgram / USF ASR)          ← USE_USF_ASR=true for UltraVoice swap
     │
     ▼
Turn Manager                       ← Module 2
     │
     ▼
user_aggregator → LLM              ← system prompt shaped by Speech Renderer Stage 1
     │
     ▼
TTSMarkupProcessor                 ← Module 3, Stage 2
     │
     ▼
TTS (UltraVoice / ElevenLabs / Fish Audio)
     │
     ▼
BackchannelInjector
     │
     ▼
AmbientMixer                       ← Module 1
     │
     ▼
Outgoing audio
```

`run_baseline.py` skips all naturalvoice modules — default Deepgram + ElevenLabs for clean A/B comparison.

---

## Stack

| Component | Service | Notes |
|---|---|---|
| Agent framework | [Pipecat](https://github.com/pipecat-ai/pipecat) | Open source, pipeline architecture |
| STT (default) | [Deepgram](https://deepgram.com) | Word-level timestamps + confidence for Turn Manager |
| STT (swap) | UltraVoice USF ASR | `USE_USF_ASR=true` — Deepgram-compatible wire format |
| TTS (default) | [UltraVoice](https://ultravoice.us.inc/docs) USF Mini | Primary target for Speech Renderer markup |
| TTS (fallback) | [ElevenLabs](https://elevenlabs.io), [Fish Audio](https://fish.audio) | `TTS_ENGINE` env var |
| LLM | OpenAI (demo default) | Any Pipecat LLM service works |
| Transport | [Daily.co](https://daily.co) | Pipecat native WebRTC |

All free tiers sufficient for development and demos.

---

## Quickstart

```bash
git clone https://github.com/kavi936/naturalvoice
cd naturalvoice
pip install -r requirements.txt
cp .env.example .env
# Fill in API keys (see .env.example for UltraVoice-first demo config)
python modules/ambient/generate_profiles.py
python demo/run_demo.py -t daily
python demo/run_baseline.py -t daily   # A/B comparison
```

Key env vars for the full stack:

```bash
TTS_ENGINE=ultravoice          # ultravoice | elevenlabs | fish_audio
USE_USF_ASR=false              # true → swap Deepgram for USF ASR
FILLER_INTENSITY=0.7            # Speech Renderer tuning (0.0–1.0)
TURN_PATIENCE_MS=600            # Turn Manager patience window
AMBIENT_PROFILE=restaurant      # ambient profile name
```

---

## Modules

- [`modules/ambient/`](modules/ambient/) — Ambient audio layer
- [`modules/turn_manager/`](modules/turn_manager/) — Conversational turn manager + USF ASR adapter
- [`modules/speech_renderer/`](modules/speech_renderer/) — Two-stage spoken-register pipeline

Each module has its own README with configuration, design rationale, and integration guide.

---

## Naturalness Benchmark (next)

Existing benchmarks (SPEARBench, EVA, TurnNat) score **models** or **task completion**. None score **application-layer pipeline interventions** — ambient audio, turn-taking behavior, linguistic register — as independent, measurable dimensions.

naturalvoice's next milestone is a public **NV-Score**: a composite naturalness metric built from the same four failure layers the middleware addresses.

| Sub-score | Layer | What it measures |
|---|---|---|
| **NV-Acoustic** (0–25) | Acoustic environment | Ambient audio presence and context appropriateness |
| **NV-Turn** (0–25) | Turn-taking | Pause classification, backchannel timing, interruption handling |
| **NV-Register** (0–25) | Linguistic register | Filler language, spoken vs written register, hedges |
| **NV-Rhythm** (0–25) | Temporal rhythm | Pacing variation, clause-level micro-pauses, emphasis |

**Composite NV-Score: 0–100.** The headline metric is the **before/after delta** — baseline pipeline vs naturalvoice-enhanced — not a single holistic MOS rating.

Planned deliverables:

- 50–100 standardized call scenarios (restaurant booking, healthcare, support, logistics)
- Automated evaluator (caller simulator → pipeline under test → scored recording)
- Public leaderboard with sub-scores, task completion, and latency

This does not compete with model benchmarks. It answers a different question: *how much does your pipeline's naturalness improve when you apply these interventions?*

Track progress in [`ROADMAP.md`](ROADMAP.md). Want to help design scenarios or scoring rubrics? Open an issue.

---

## Research

| Document | Summary |
|---|---|
| [problem-analysis.md](research/problem-analysis.md) | Four failure layers, Levinson turn-taking paradox, vocal uncanny valley, protocol design |
| [research/README.md](research/README.md) | Index, citation format, how to contribute research |

---

## Competitive landscape

| Project | Approach | Gap |
|---|---|---|
| Sesame CSM | Model-layer, new architecture | Requires model swap; English-only |
| OpenAI Realtime API | Latency + interruption focus | No acoustic, register, or rhythm interventions |
| Pipecat | Framework only | No naturalness middleware |
| **naturalvoice** | Middleware protocol, model-agnostic | Composable on existing stacks today |

---

## Motivation

This started as a personal frustration — a restaurant booking call in San Francisco that technically worked and felt completely wrong. The more I looked into why, the clearer it became that the problem is architectural, not just a matter of better models.

The goal of naturalvoice is to give any developer building on existing voice agent infrastructure a set of composable, low-cost interventions that close the gap between accurate and human — and a benchmark that proves it.

---

## Contributing

Issues and PRs welcome. High-impact contribution paths:

- Confirm USF Mini TTS SSML support → update `_apply_ultravoice()` in Speech Renderer
- New ambient profiles (hospital, call center, outdoor)
- Multilingual spoken-register rules for Speech Renderer
- Benchmark scenario design and scoring rubric review

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup and PR guidelines.

---

## License

MIT
