# Roadmap

naturalvoice is a middleware protocol, not a monolithic agent. Each module ships independently so teams can adopt one layer without rewriting their stack.

**Current focus:** v0.2 — the naturalness benchmark (NV-Score).

---

## v0.1 — Middleware stack ✅ (shipped)

All three modules, demo A/B, and research foundation.

### Ambient Layer
- [x] `AmbientMixer` Pipecat processor
- [x] Restaurant and office profiles + `generate_profiles.py`
- [x] Configurable mix level and mid-call profile switching

### Turn Manager
- [x] Four-state model: `SPEAKING`, `THINKING`, `SIDE_CONVO`, `DONE`
- [x] Deepgram word-level confidence + audio RMS detection
- [x] Configurable patience window (`TURN_PATIENCE_MS`)
- [x] Backchannel generation with matching voice timbre
- [x] USF ASR drop-in adapter (`USE_USF_ASR=true`)

### Speech Renderer
- [x] Stage 1: `SystemPromptInjector` (spoken register at init)
- [x] Stage 2: `TTSMarkupProcessor` (engine-specific markup)
- [x] `TTS_ENGINE` support: `ultravoice`, `elevenlabs`, `fish_audio`
- [x] `FILLER_INTENSITY` tuning dial (0.0–1.0)

### Demo & docs
- [x] `run_demo.py` — full stack (all modules, UltraVoice-first)
- [x] `run_baseline.py` — clean Deepgram + ElevenLabs A/B baseline
- [x] Research: four failure layers ([`research/problem-analysis.md`](research/problem-analysis.md))
- [x] Per-module READMEs

---

## v0.2 — Naturalness Benchmark (next)

The first evaluation framework designed to score **application-layer pipeline interventions**, not model quality. Measures improvement via before/after delta vs baseline.

### NV-Score (composite 0–100)

| Sub-score | Layer | Method |
|---|---|---|
| NV-Acoustic (0–25) | Acoustic environment | Audio waveform analysis |
| NV-Turn (0–25) | Turn-taking | TurnNat-inspired perturbation pairs + LLM evaluator |
| NV-Register (0–25) | Linguistic register | LLM evaluator on transcript |
| NV-Rhythm (0–25) | Temporal rhythm | Audio waveform analysis |

### Deliverables
- [ ] `benchmark/` scaffolding — scenario library, evaluator, CLI
- [ ] 50–100 standardized call scenarios (restaurant, healthcare, support, logistics)
- [ ] Caller simulator (LLM + TTS) → pipeline under test → scored recording
- [ ] Automated NV-Evaluator (no human raters required for leaderboard)
- [ ] Before/after delta metric (baseline vs naturalvoice-enhanced)
- [ ] Public leaderboard (pipeline config + sub-scores + task completion + latency)
- [ ] Community demo recordings for README showcase

### Known v1 limitations (documented honestly)
- English-only
- Fixed caller voice profile (no accent/dialect variation yet)
- NV-Acoustic scores ambient presence, not phone-line compression artifacts
- Periodic human calibration runs needed for academic credibility

---

## v0.3 — Protocol & production polish

- [ ] `docs/protocol-spec.md` — referenceable protocol spec, not just a library
- [ ] Confirm USF Mini TTS SSML support → upgrade `_apply_ultravoice()` if supported
- [ ] Real phone call demo via UltraVoice telephony + Twilio
- [ ] Continuous room tone during silence (`BaseAudioMixer` upgrade for Ambient Layer)
- [ ] LiveKit / Vapi integration examples

---

## v0.4 — Adaptive calibration

Real-time parameter adaptation based on caller behavior. Requires benchmark (to measure improvement) and call volume (to train on).

- [ ] Auto-extending patience window when caller keeps getting cut off
- [ ] Dynamic `FILLER_INTENSITY` based on caller response patterns
- [ ] Backchannel threshold adjustment to match caller speaking rhythm
- [ ] Per-deployment optimal defaults learned from aggregate call data

---

## Future

- Multilingual spoken-register rules and turn-taking conventions
- Emotional mirroring (sentiment → TTS prosody settings)
- Phone-line compression simulation in Ambient Layer
- Cross-accent robustness in benchmark caller simulator
- Telemetry and diagnostics layer (open-core: modules stay OSS, observability optional)

---

## How to contribute

Open an issue to claim a roadmap item or propose a new one. High-impact paths right now:

1. **Benchmark** — scenario design, scoring rubric review, evaluator implementation
2. **USF SSML** — test and document UltraVoice TTS markup capabilities
3. **Ambient profiles** — hospital, call center, outdoor environments
4. **Multilingual register** — spoken-language rules beyond English

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup and PR guidelines.
