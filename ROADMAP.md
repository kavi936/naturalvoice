# Roadmap

naturalvoice is a middleware protocol, not a monolithic agent. Each module ships independently so teams can adopt one layer without rewriting their stack.

## v0.1 — Ambient Layer (current)

- [x] `AmbientMixer` Pipecat processor
- [x] Restaurant and office profiles
- [x] Demo: ambient on vs baseline off
- [x] Research document: four failure layers

## v0.2 — Turn Manager

- [ ] Three-state model: `SPEAKING`, `THINKING`, `SIDE_CONVERSATION`
- [ ] Deepgram word-level timestamp integration
- [ ] Configurable patience window
- [ ] Optional backchannel generation ("mm-hmm", "right")

## v0.3 — Speech Renderer

- [ ] Prompt-layer spoken-register shaping
- [ ] Post-processing markup for ElevenLabs / Cartesia
- [ ] Intensity dial (subtle → conversational)

## v0.4 — Evaluation

- [ ] Before/after demo recordings (ambient, turn-taking, speech)
- [ ] Subjective naturalness rubric for community testing
- [ ] Latency + interruption benchmark script

## Future

- Phone-line compression simulation in Ambient Layer
- Multilingual spoken-register rules
- LiveKit / Vapi integration examples
- Emotional mirroring via sentiment → TTS settings

Open an issue to claim a roadmap item or propose a new one.
