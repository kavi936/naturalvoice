# naturalvoice

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Pipecat](https://img.shields.io/badge/built%20on-Pipecat-orange)](https://github.com/pipecat-ai/pipecat)

**Voice AI agents are accurate. They're just not human. This is the open protocol to fix that.**

Middleware for Pipecat, LiveKit, and any voice pipeline — ambient room tone, smarter turn-taking, and spoken-register speech rendering. No model swap required.

[Research paper](./research/problem-analysis.md) · [Roadmap](./ROADMAP.md) · [Contributing](./CONTRIBUTING.md)

---

## Demo

> **Before:** studio-clean silence, rigid turn-taking, "I am checking availability for Saturday evening."  
> **After:** restaurant room tone, patience during thinking pauses, "let me just — yeah, one sec, checking Saturday for you."

```bash
pip install -r requirements.txt && cp .env.example .env
python demo/run_demo.py -t webrtc      # with ambient
python demo/run_baseline.py -t webrtc  # without — hear the difference
```

Record a side-by-side clip and open a PR — the best demos get linked here.

---

## The Problem

I called Bodega, a restaurant in San Francisco, to reserve a table. I was connected instantly — no hold music, no wait. The agent knew the availability, handled the booking, and got me off the call in under a minute. Technically flawless.

But something was wrong the entire time.

There was no background noise — none of the ambient hum you'd expect from a restaurant floor. The line was studio-clean, which felt immediately off. When I paused to think, or turned to ask someone nearby a question, the agent cut back in. It had no model for "he's thinking" versus "he's done." And when it processed my request, it said things like *"I am checking availability for Saturday evening."* Not *"let me just — yeah, one sec, checking Saturday for you."* Every response was informationally correct and conversationally dead.

This is the uncanny valley of voice AI. And it isn't a model problem. It's a design problem — three separable, fixable layers that almost no one is addressing.

---

## Why Agents Feel Fake

Current voice agents fail at four distinct layers, each beneath the one above it:

- **Acoustic Environment** — Silence is a tell. Real calls have room tone, ambient bleed, line noise. A pristine audio stream signals "robot" before a word is spoken.
- **Turn-Taking** — Binary voice detection can't distinguish a thinking pause from a sentence end from a side conversation. Agents cut in too early or go silent too long.
- **Linguistic Register** — LLMs produce grammatically complete sentences. Humans don't speak that way. Filler language isn't noise — it holds the floor, signals processing, and maintains social connection.
- **Temporal Rhythm** — Even within a single response, consistent TTS pacing becomes fatiguing and signals artificiality. Human speech has micro-pauses, speed variation, and emphasis shifts.

The academic literature backs all four. Levinson & Torreira (2015) established that humans predict turn completion and prepare responses in advance — voice agents that wait for full silence are structurally incapable of matching human timing. CHI 2025 research confirms that rigid turn-taking without backchannels limits natural communication. Production voice AI delivers 1,400–1,700ms median response latency against a 200–300ms human baseline.

> See [`research/problem-analysis.md`](research/problem-analysis.md) for the full cited analysis.

---

## What naturalvoice Does

This repo provides three composable middleware modules that sit on top of any voice agent pipeline — Pipecat, LiveKit Agents, Vapi, Retell — without requiring a model swap.

### Module 1 — Ambient Layer
Injects context-appropriate background audio into the agent's outgoing audio stream. Restaurant profiles, office environments, call center tone. Configurable mix levels. Negligible compute cost.

```
agent TTS output → [AmbientMixer] → caller hears: voice + room tone
```

### Module 2 — Turn Manager
Replaces binary VAD with a three-state conversational model: `SPEAKING`, `THINKING`, and `SIDE_CONVERSATION`. Uses Deepgram word-level timestamps and confidence scoring to classify pause intent. Gives the agent a configurable patience window before responding.

```
caller audio → [TurnManager] → state: THINKING → agent holds
                             → state: DONE    → agent responds
                             → state: SIDE    → agent waits silently
```

### Module 3 — Speech Renderer
A prompt-layer + post-processing pipeline that injects naturalistic speech patterns into LLM output before TTS: filler language, elongation markers, hedges, false starts. ElevenLabs and Cartesia render these correctly when fed the right markup.

```
LLM output: "I am checking availability for Saturday."
         ↓ [SpeechRenderer]
TTS input:  "Let me just — yeah, one sec, checking Saturday for you..."
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Incoming Call                         │
└──────────────────────────┬──────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │      Turn Manager       │  ← Module 2
              │  (conversational state) │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │     STT (Deepgram)      │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │        LLM              │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │    Speech Renderer      │  ← Module 3
              │  (naturalistic markup)  │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │     TTS (ElevenLabs)    │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │     Ambient Mixer       │  ← Module 1
              │  (background audio)     │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │       Outgoing Audio    │
              └─────────────────────────┘
```

---

## Stack

| Component | Service | Why |
|---|---|---|
| Agent framework | [Pipecat](https://github.com/pipecat-ai/pipecat) | Open source, pipeline architecture, native hooks for all three modules |
| STT | [Deepgram](https://deepgram.com) | Word-level timestamps + confidence scores needed for Turn Manager |
| TTS | [ElevenLabs](https://elevenlabs.io), [UltraVoice](https://us.inc/products/ultravoice), [Fish Audio](https://fish.audio) | Interchangeable TTS backends; demos default to ElevenLabs. UltraVoice and Fish Audio are first-class targets for Speech Renderer markup. |
| LLM | OpenAI (demo default) | Any Pipecat LLM service works |
| Transport | [Daily.co](https://daily.co) | Pipecat's native WebRTC transport, generous free tier |

All free tiers sufficient for development and demos.

---

## Quickstart

```bash
git clone https://github.com/naturalvoice/naturalvoice
cd naturalvoice
pip install -r requirements.txt
cp .env.example .env
# Add Deepgram + OpenAI + ElevenLabs (+ Daily for -t daily)
# Optional: regenerate placeholder ambient WAVs
python modules/ambient/generate_profiles.py
python demo/run_demo.py -t daily
# Compare without ambient:
python demo/run_baseline.py -t daily
```

> v0.1 demos compare **Ambient Layer on vs off**. Turn Manager and Speech Renderer land in later modules.

---

## Modules

- [`modules/ambient/`](modules/ambient/) — Ambient audio layer
- [`modules/turn-manager/`](modules/turn-manager/) — Conversational turn manager
- [`modules/speech-renderer/`](modules/speech-renderer/) — Naturalistic speech renderer

Each module has its own README with configuration options, design rationale, and integration guide.

---

## Research

The full problem analysis — with citations, academic grounding, and a landscape review of prior art (Sesame CSM, OpenAI Realtime API, Pipecat) — lives in [`research/`](research/):

| Document | Summary |
|---|---|
| [problem-analysis.md](research/problem-analysis.md) | Four failure layers, Levinson turn-taking paradox, vocal uncanny valley, protocol design |
| [research/README.md](research/README.md) | Index, citation format, how to contribute research |

---

## Motivation

This started as a personal frustration — a restaurant booking call in San Francisco that technically worked and felt completely wrong. The more I looked into why, the clearer it became that the problem is architectural, not just a matter of better models.

The goal of naturalvoice is to give any developer building on existing voice agent infrastructure a set of composable, low-cost interventions that close the gap between accurate and human.

---

## Contributing

Issues and PRs welcome. If you've built on top of Pipecat, LiveKit, or any other voice pipeline and have observations on what breaks conversational naturalness — open an issue. The research document is meant to evolve.

---

## License

MIT