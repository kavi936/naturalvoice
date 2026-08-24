# Contributing to naturalvoice

Thanks for helping make voice agents sound human. This project is early — issues, PRs, and research contributions are all welcome.

## Ways to contribute

1. **Bug reports** — something broken in a module or demo
2. **Integration notes** — what you learned wiring naturalvoice into Pipecat, LiveKit, Vapi, or Retell
3. **Research** — citations, benchmarks, or field observations (see [`research/`](research/))
4. **Code** — module improvements, new ambient profiles, Turn Manager heuristics, Speech Renderer rules

## Development setup

```bash
git clone https://github.com/kavi936/naturalvoice.git
cd naturalvoice
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in API keys, then:
python modules/ambient/generate_profiles.py
python demo/run_demo.py -t webrtc
```

## Pull request guidelines

- One logical change per PR when possible
- Match existing module style (see `modules/ambient/` as reference)
- Update the relevant module README if behavior or config changes
- Do not commit secrets (`.env`, API keys)

## Research contributions

Add or extend documents under `research/`. Keep citations linked. If you add a new doc, index it in `research/README.md`.

## Code of conduct

Be constructive. This project exists because voice AI is hard and the gap between "accurate" and "human" is under-discussed — help close it.
