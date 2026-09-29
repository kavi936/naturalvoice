# Voice Agents & TTS: A Beginner's Deep Dive

**naturalvoice research companion · last validated September 2026**

This document is written for someone who has **no prior knowledge** of voice AI. It explains the field from first principles, defines every abbreviation, walks through how the major systems work, and situates [naturalvoice](../README.md) in that landscape.

It is meant to be read once for orientation, then revisited as a glossary and map. Companion docs:


| Document                                     | What it covers                                             |
| -------------------------------------------- | ---------------------------------------------------------- |
| [problem-analysis.md](./problem-analysis.md) | Why voice agents feel robotic (four failure layers)        |
| [benchmark section](../README.md#naturalness-benchmark-next)        | How naturalness is (and isn't) measured                    |
| This file                                    | Domain literacy: history, software, terminology, stack map |


---



## 0. The one-sentence picture

A **voice agent** is software that can **hear you, think, and talk back** over a phone call or browser microphone — usually by chaining three AI systems:`

```
Your speech  →  STT (hears)  →  LLM (thinks)  →  TTS (speaks)  →  Audio you hear
```

That chain is called a **cascaded pipeline**. Almost every production voice agent in 2026 still uses it. naturalvoice sits *on top of* that pipeline and makes the conversation feel more human — without swapping the models.

---



## 1. Start here: what problem does this field even solve?



### Before voice agents

For decades, "talking to a computer" meant:

1. **IVR** (Interactive Voice Response) — "Press 1 for sales, press 2 for support." Tree menus. No understanding of natural speech.
2. **Dictation / ASR products** — Dragon NaturallySpeaking, early Siri/Alexa. They transcribed or answered simple commands, but could not run a full multi-turn business conversation with tool use (book a table, look up an order, update a CRM).
3. **Call centers with humans** — expensive, slow to scale, inconsistent.



### What changed (roughly 2022–2026)

Three technologies matured at once:


| Piece          | What matured                                                                     | Why it mattered                                                            |
| -------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **STT / ASR**  | Streaming speech recognition that is accurate *and* fast enough for conversation | The agent can understand you while you are still talking                   |
| **LLMs**       | Models that can reason, follow instructions, and call tools (APIs, databases)    | The agent can do real work, not just recite scripts                        |
| **Neural TTS** | Voices that no longer sound like 1990s GPS robots                                | Callers will stay on the line long enough for the agent to finish the task |


Glue them with **real-time audio transport** (WebRTC for browsers, SIP/PSTN for phone lines) and you get a **voice agent**: an AI that can take a phone call end-to-end.

### Accuracy is largely solved. Feeling human is not.

That is naturalvoice's thesis. Agents today often:

- Book the table correctly
- Answer the FAQ correctly
- Complete the task faster than a human

…and still feel *wrong* — studio silence, interrupting your thinking pauses, saying "I am checking availability" instead of "yeah one sec, checking Saturday." See [problem-analysis.md](./problem-analysis.md).

---



## 2. Glossary: abbreviations and terms (read this like a dictionary)

You will see these everywhere. Learn them once.

### Core pipeline


| Term                            | Full form                    | Plain English                                                       |
| ------------------------------- | ---------------------------- | ------------------------------------------------------------------- |
| **STT**                         | Speech-to-Text               | Turns your audio into written words                                 |
| **ASR**                         | Automatic Speech Recognition | Same idea as STT (older / academic term)                            |
| **TTS**                         | Text-to-Speech               | Turns written words into spoken audio                               |
| **LLM**                         | Large Language Model         | The "brain" (GPT, Claude, Gemini, etc.) that decides what to say    |
| **S2S**                         | Speech-to-Speech             | One model takes audio in and audio out (skips explicit text stages) |
| **Cascade / cascaded pipeline** | —                            | STT → LLM → TTS chained together (industry default)                 |




### Conversation mechanics


| Term                     | Plain English                                                                |
| ------------------------ | ---------------------------------------------------------------------------- |
| **Turn-taking**          | Who speaks when. Humans do this with ~200–300ms gaps.                        |
| **VAD**                  | Voice Activity Detection — "is someone speaking right now?" (usually yes/no) |
| **Endpointing**          | Deciding the user has *finished* their turn (not just paused)                |
| **Barge-in**             | User interrupts the agent mid-sentence; agent must stop talking              |
| **Backchannel**          | Listener signals: "mm-hmm", "right", "yeah" — not a full turn                |
| **Duplex / full-duplex** | Both sides can speak/listen overlapping (like a real phone call)             |
| **Half-duplex**          | Only one side "has the floor" at a time (walkie-talkie feel)                 |




### Audio & telephony


| Term                    | Plain English                                                                                                 |
| ----------------------- | ------------------------------------------------------------------------------------------------------------- |
| **PCM**                 | Pulse-Code Modulation — raw digital audio samples                                                             |
| **Sample rate**         | How many audio samples per second (e.g. 16 kHz = 16,000/sec). Phone audio often 8 kHz; voice AI often 16 kHz. |
| **Opus**                | Efficient audio codec used heavily in WebRTC                                                                  |
| **WebRTC**              | Browser/standard protocol for real-time audio/video with low latency                                          |
| **WebSocket**           | Persistent internet connection; often used to stream audio chunks to STT/TTS APIs                             |
| **SIP**                 | Session Initiation Protocol — how phone systems set up calls                                                  |
| **PSTN**                | Public Switched Telephone Network — the actual phone network                                                  |
| **Twilio / Telnyx**     | Cloud telephony providers that connect your software to real phone numbers                                    |
| **Daily.co**            | WebRTC infrastructure company; also creators of Pipecat                                                       |
| **Room tone / ambient** | Background acoustic texture of a place (restaurant hum, office HVAC)                                          |




### Speech science (TTS internals)


| Term                | Plain English                                                                                          |
| ------------------- | ------------------------------------------------------------------------------------------------------ |
| **Phoneme**         | A basic unit of sound in a language (the /k/ in "cat")                                                 |
| **Prosody**         | Rhythm, pitch, emphasis, timing — how something is said, not what                                      |
| **Mel-spectrogram** | A picture of sound energy across frequencies over time (intermediate TTS representation)               |
| **Vocoder**         | Model that turns a spectrogram into an actual playable waveform                                        |
| **SSML**            | Speech Synthesis Markup Language — XML-ish tags to control pauses, emphasis, rate                      |
| **Voice cloning**   | Creating a synthetic voice that sounds like a specific person from a short sample                      |
| **MOS**             | Mean Opinion Score — 1–5 human rating of speech quality (flawed for conversation; see the [benchmark section](../README.md#naturalness-benchmark-next)) |




### Latency jargon (the numbers people argue about)


| Term            | Plain English                                                                         |
| --------------- | ------------------------------------------------------------------------------------- |
| **Latency**     | Delay. In voice, usually "how long until the agent starts talking after you stop."    |
| **TTFB / TTFA** | Time To First Byte / First Audio — how fast TTS starts producing sound                |
| **P50 / P95**   | Median / 95th-percentile latency (P50 = typical; P95 = bad cases)                     |
| **Streaming**   | Sending partial results as soon as they exist, instead of waiting for the whole thing |




### Frameworks & products you will see in this repo


| Name                      | What it is                                                                         |
| ------------------------- | ---------------------------------------------------------------------------------- |
| **Pipecat**               | Open-source Python framework for building voice agent pipelines (frame processors) |
| **LiveKit Agents**        | Voice agent framework built on LiveKit's WebRTC media server                       |
| **Deepgram**              | Leading streaming STT provider (Nova models; also Flux for turn detection)         |
| **ElevenLabs**            | Leading consumer/B2B TTS and voice cloning company                                 |
| **UltraVoice / USF**      | UltraSafe's voice stack used as naturalvoice's primary demo TTS/ASR                |
| **Fish Audio**            | TTS/cloning provider; often competitive on quality and price                       |
| **OpenAI Realtime API**   | Speech-in / speech-out API (S2S-style product surface)                             |
| **Sesame CSM**            | Conversational Speech Model — open speech generator with conversation context      |
| **Vapi / Retell / Bland** | Hosted voice-agent platforms (orchestration + telephony, mix-and-match models)     |


---



## 3. A short history of talking machines

Understanding *why* today's software looks the way it does helps you read marketing claims critically.

### Era 1 — Concatenative & parametric TTS (pre-~2016)

- **Concatenative**: stitch together recorded speech fragments. Clear but choppy; hard to change emotion.
- **Parametric** (e.g. older HMM systems): generate speech from statistical models. Flexible, often robotic.

This is the "GPS voice" era most people remember.

### Era 2 — Neural TTS arrives (2016–2020)

Landmark ideas:

- **WaveNet** (DeepMind, 2016) — generates raw audio sample-by-sample; stunning quality, originally too slow for realtime.
- **Tacotron / Tacotron 2** — text → mel-spectrogram with neural nets.
- **FastSpeech** — parallel (non-autoregressive) acoustic models for speed.
- **HiFi-GAN and peers** — fast neural vocoders that made realtime neural TTS practical.

**Why this matters:** quality jumped from "obviously a robot" to "could pass in a short clip." Realtime agents became thinkable.

### Era 3 — Cloud voice APIs & assistants (2011–2022)

Siri, Alexa, Google Assistant proved voice UX at consumer scale — but mostly **command** interfaces, not open-ended agentic phone calls with tools.

### Era 4 — LLM voice agents (2023–2025)

ChatGPT-class models + streaming STT + streaming TTS created the modern **cascaded voice agent**. Startups (Vapi, Retell, Bland, etc.) productized "AI that answers the phone." Frameworks (Pipecat, LiveKit Agents) productized the plumbing for developers who want control.

### Era 5 — Native speech models + naturalness wars (2025–2026)

Two parallel tracks:

1. **Better cascades** — faster STT (Deepgram Nova-3, ElevenLabs Scribe), faster TTS (Cartesia Sonic, ElevenLabs Turbo/Flash, Aura-2), smarter turn detection (Deepgram Flux, Pipecat Smart Turn, LiveKit turn detector).
2. **Speech-native models** — OpenAI Realtime, Gemini Live, research models like Moshi; plus **context-aware speech generators** like Sesame CSM that aim for "voice presence," not just clean reading.

**Where naturalvoice sits:** it argues that even with great models, **application-layer** behavior (ambient sound, turn patience, spoken register) still breaks the illusion — and that this is fixable as middleware.

---



## 4. How a cascaded voice agent actually works

Imagine you call a restaurant and an AI answers.

### Step-by-step (one turn)

```
1. Transport     Your phone → Twilio/SIP → server, OR browser mic → WebRTC (Daily/LiveKit)
2. VAD           "Caller is speaking" vs silence
3. Streaming STT Audio chunks → partial transcript → final transcript
4. Endpointing   "Caller is done" (not just thinking)
5. LLM           Transcript + history + tools → streaming text reply
6. Sentence buffer  Hold tokens until a speakable sentence exists
7. Streaming TTS Sentence → audio chunks
8. Playback      Chunks → your ear (WebRTC / phone)
9. Barge-in loop If you interrupt, cancel TTS + flush buffers
```



### Why streaming matters

If each stage waited for the previous stage to *finish completely*, latency would stack:


| Stage                    | Typical contribution                             |
| ------------------------ | ------------------------------------------------ |
| STT finalization         | ~200–500 ms                                      |
| LLM time-to-first-token  | ~200–400 ms                                      |
| TTS time-to-first-audio  | ~50–300 ms (Cartesia often lower; others higher) |
| Network / jitter buffers | ~50–200+ ms                                      |
| Phone (PSTN/SIP) path    | often +200–400 ms vs pure WebRTC                 |


**Human gap expectation:** ~200–300 ms (Levinson & Torreira, 2015).  
**Many production agents historically:** ~1,400–1,700 ms median — feels "slow" or socially awkward even when accurate.

Streaming + overlap (LLM starts before STT is "done," TTS starts before LLM finishes) is how teams push perceived latency toward the sub-second range.

### The sentence buffer (underrated)

LLMs emit tokens like `I` `can` `help` `with` `that`. If you feed TTS one token at a time, speech sounds broken.

So frameworks buffer until a sentence boundary (`.?!`) — Pipecat's `SentenceAggregator` is one example — then flush a full clause to TTS. This is one of the most important "boring" primitives in the field.

### Cascaded vs speech-to-speech (S2S)


|                                       | Cascaded (STT→LLM→TTS)       | Native S2S (Realtime-style)                 |
| ------------------------------------- | ---------------------------- | ------------------------------------------- |
| **Control**                           | Swap any vendor/model        | Vendor chooses the whole stack              |
| **Debugging**                         | Read text between stages     | Harder — audio in, audio out                |
| **Tool calling**                      | Mature (text LLM tools)      | Improving, historically weaker/inconsistent |
| **Prosody / emotion from your voice** | Often lost (text bottleneck) | Can preserve more of it                     |
| **Production default in 2026**        | Still the majority           | Growing for demos & some products           |


Industry consensus mid-2026: cascades still dominate production because of **modularity, cost control, and debuggability** — not because S2S is "fake."

---



## 5. How TTS works under the hood (beginner technical)

You do not need to train models to use TTS — but understanding the pipeline makes SSML, "prosody," and "why rhythm feels flat" make sense.

### Classic three-stage neural TTS

```
Text
  → 1. Front-end: normalize text, expand "Dr." / "$5", convert to phonemes
  → 2. Acoustic model: phonemes → mel-spectrogram (a visual map of sound)
  → 3. Vocoder: spectrogram → waveform (the actual .wav / PCM you hear)
```

**Analogy:**

1. Figure out *which sounds* to make (phonemes).
2. Draw a *sheet music of energy* over time (spectrogram).
3. Hire a musician (vocoder) to *perform* it as real audio.

Modern systems often fuse stages or use **audio tokens / codecs** (discrete codes representing speech) instead of classic spectrograms — Sesame CSM generating Mimi/RVQ codes is in that family — but the jobs (what to say → how it should sound → samples) remain.

### What "sounding human" requires beyond clear words


| Layer         | Example failure                                 |
| ------------- | ----------------------------------------------- |
| Pronunciation | Wrong stress on a brand name                    |
| Prosody       | Every sentence same pitch contour               |
| Timing        | No micro-pauses at clause boundaries            |
| Register      | Written English spoken aloud ("I am checking…") |
| Interaction   | Perfect voice, terrible turn-taking             |


naturalvoice's Speech Renderer attacks **register + markup**. Full rhythmic naturalness still depends heavily on the TTS engine.

---



## 6. How STT / ASR works (enough to be dangerous)

Streaming STT typically:

1. Receives audio in tiny chunks (often ~20 ms).
2. Emits **partial** transcripts (`is_final: false`) that may change.
3. Emits **final** transcripts when confident (`is_final: true`).
4. May also emit **word-level timestamps and confidence** — naturalvoice's Turn Manager uses these.

**Word Error Rate (WER)** is the classic accuracy metric. In 2026, top providers are often within 1–2 points of each other on clean benchmarks. Competition has shifted to:

- Streaming latency
- Noise robustness
- End-of-turn detection
- Multilingual / code-switching
- Cost at scale

**Providers you will hear about:** Deepgram (Nova-3; Flux for conversational turns), AssemblyAI, OpenAI transcription models, ElevenLabs Scribe, Google, Microsoft, Cartesia Ink-Whisper, open Whisper variants.

---



## 7. Turn-taking, VAD, and why agents interrupt you



### Binary VAD is too dumb for conversation

Classic VAD says: speech vs not-speech.

Human conversation needs richer states, for example:


| State      | What is happening       | What the agent should do  |
| ---------- | ----------------------- | ------------------------- |
| SPEAKING   | Caller mid-utterance    | Listen; maybe backchannel |
| THINKING   | Pause, but not finished | Hold — do not jump in     |
| SIDE_CONVO | Talking to someone else | Wait                      |
| DONE       | Floor yielded           | Respond                   |


naturalvoice's Turn Manager implements this richer model. Industry peers include semantic turn detectors (LiveKit, Pipecat Smart Turn) and conversational STT (Deepgram Flux) that predict end-of-turn from meaning + acoustics, not silence alone.

### Backchannels

If you talk for 20 seconds and the listener is dead silent, it feels like they hung up. Humans say "mm-hmm." Agents that never do this feel absent. Agents that overdo it feel mocking. Timing matters.

### Barge-in is a systems problem

Stopping the agent is not just "run VAD." Audio is buffered on:

- The server generation queue
- The network
- The client playback buffer

Cancel server-side but forget client flush → the agent keeps talking for hundreds of ms after you interrupt. That reads as rude.

---



## 8. The software map (who builds what)

Think in **layers**. Companies compete inside a layer; frameworks connect layers.

```
┌─────────────────────────────────────────────────────────┐
│  Experience layer                                        │
│  naturalvoice (ambient, turns, spoken register)          │
│  Product UX, prompts, tools, business logic              │
├─────────────────────────────────────────────────────────┤
│  Orchestration / agent frameworks                        │
│  Pipecat · LiveKit Agents · Vapi · Retell · Bland        │
├─────────────────────────────────────────────────────────┤
│  Models                                                  │
│  STT: Deepgram, AssemblyAI, Scribe, USF ASR, Whisper…    │
│  LLM: OpenAI, Anthropic, Google, open weights…           │
│  TTS: ElevenLabs, Cartesia, Fish Audio, UltraVoice, Aura │
│  S2S: OpenAI Realtime, Gemini Live, research models      │
├─────────────────────────────────────────────────────────┤
│  Transport                                               │
│  WebRTC (Daily, LiveKit) · SIP/PSTN (Twilio, Telnyx)     │
└─────────────────────────────────────────────────────────┘
```



### Frameworks (orchestration)


| Software                  | Mental model                                                  | Strength                                                |
| ------------------------- | ------------------------------------------------------------- | ------------------------------------------------------- |
| **Pipecat**               | Pipeline of `FrameProcessor`s; audio/text frames flow through | Huge integration surface; naturalvoice's primary target |
| **LiveKit Agents**        | Agent joins a WebRTC *room* as a participant                  | Multi-party, scalable media; strong telephony stories   |
| **Vapi / Retell / Bland** | Hosted "build an agent" platforms                             | Fastest path to a phone number; less low-level control  |




### STT vendors


| Software               | Notes (2026 snapshot)                                                                                        |
| ---------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Deepgram**           | Default STT for many agent platforms; streaming + enterprise footprint; Flux adds conversational end-of-turn |
| **AssemblyAI**         | Strong competitor on accuracy/features                                                                       |
| **ElevenLabs Scribe**  | STT from a TTS-first company; realtime variants emphasize low latency                                        |
| **UltraVoice USF ASR** | Deepgram-compatible wire format in this repo — swap base URL/auth, keep Turn Manager logic                   |




### TTS vendors


| Software                               | Notes (2026 snapshot)                                                                      |
| -------------------------------------- | ------------------------------------------------------------------------------------------ |
| **ElevenLabs**                         | Category leader for many teams; rich voices; climbing into full conversational AI products |
| **Cartesia (Sonic)**                   | Latency specialist (often cited ~sub-100 ms TTFA); popular for phone agents                |
| **Fish Audio**                         | Strong quality/price; cloning from short samples; used as a naturalvoice fallback          |
| **Deepgram Aura**                      | TTS from an STT company — convenient same-vendor stacks                                    |
| **UltraVoice USF Mini**                | naturalvoice default demo TTS; streaming synthesis + telephony path                        |
| **PlayHT, Resemble, Hume, OpenAI TTS** | Other notable options depending on emotion, volume pricing, or ecosystem                   |




### Model-layer "feel human" efforts


| Project                   | Approach                                                        | Relation to naturalvoice                                                       |
| ------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| **Sesame CSM**            | Context-aware speech generation ("voice presence"); open CSM-1B | Model swap / new generator; complementary, not middleware                      |
| **OpenAI Realtime**       | Speech-in/speech-out sessions, interruptions, low latency       | Improves cascade pain points; does not solve ambient/register layers by itself |
| **Moshi (Kyutai) et al.** | Research full-duplex speech models                              | Important scientifically; different product shape                              |




### Evaluation & ops (adjacent world)


| Name                               | Role                                                                             |
| ---------------------------------- | -------------------------------------------------------------------------------- |
| **MOS / ITU-T P.800**              | Classic human listening score for TTS clips                                      |
| **SPEARBench, TurnNat, EVA-Bench** | Academic / industry benchmarks (models or task completion — see the [benchmark section](../README.md#naturalness-benchmark-next)) |
| **Hamming, Future AGI, Coval**     | Commercial voice-agent eval / testing platforms                                  |


naturalvoice's planned **NV-Score** targets a gap: score *pipeline interventions* (ambient, turns, register, rhythm), not just model quality or task success.

---



## 9. How this repository maps onto the field

naturalvoice does **not** replace Deepgram, ElevenLabs, or Pipecat. It assumes they exist and adds three modules:


| Module              | Field problem it addresses          | Where it sits in the pipeline                |
| ------------------- | ----------------------------------- | -------------------------------------------- |
| **Ambient Layer**   | Studio-clean silence feels fake     | After TTS, mix room tone into outgoing audio |
| **Turn Manager**    | Binary VAD cuts off thinking pauses | After STT, before LLM fires                  |
| **Speech Renderer** | LLMs write; humans speak            | Shape LLM prompt + markup before TTS         |


Full demo path (`demo/run_demo.py`):

```
STT → Turn Manager → LLM (spoken-register prompt)
    → TTS markup → TTS → backchannels → Ambient Mixer → out
```

Baseline (`demo/run_baseline.py`) skips the modules so you can A/B the *feel*.

**Why middleware is a valid bet:** if Sesame or Realtime improve the voice model, ambient injection and turn patience still apply. If you swap ElevenLabs for Fish Audio, Speech Renderer still has a job. Model progress and application-layer naturalness are not mutually exclusive.

---



## 10. What "good" looks like in 2026 (practical targets)

These are orientation numbers, not laws of physics — always measure your own stack.


| Dimension        | Rough human / product expectation                                 |
| ---------------- | ----------------------------------------------------------------- |
| Turn gap         | Humans ~200–300 ms; agents often still much higher                |
| Noticeable delay | Many users start noticing gaps above ~500–700 ms                  |
| Phone tax        | SIP/PSTN often adds hundreds of ms vs browser WebRTC              |
| TTS quality      | Clean short demos are easy; multi-minute calls expose flat rhythm |
| Naturalness      | Callers often notice *feel* before they notice wording accuracy   |


**Wrong optimization:** chase a celebrity MOS on a 5-second clip while your endpointing interrupts every thinking pause.

**Right optimization for this repo's thesis:** measure before/after deltas on acoustic presence, turn behavior, register, and rhythm — the NV-Score direction.

---



## 11. Common confusions (and the correction)


| Confusion                                   | Correction                                                                           |
| ------------------------------------------- | ------------------------------------------------------------------------------------ |
| "Better TTS will fix uncanny valley"        | Better voice can *worsen* uncanny valley if turn-taking/register stay robotic        |
| "STT accuracy is the bottleneck"            | For many English deployments, latency + turns + tools matter more day-to-day         |
| "S2S makes cascades obsolete"               | Cascades still win on control/debug/tools in most production systems                 |
| "VAD = understanding when I'm done"         | VAD is speech detection; endpointing / semantic turn detection is the harder problem |
| "Fillers are just fluff"                    | Fillers hold the floor and signal processing — conversational work, not decoration   |
| "Silence on the agent side is professional" | On a phone call, dead air often reads as "call dropped" or "robot"                   |
| "MOS tells you if the agent feels human"    | MOS is a clip-quality score; it masks conversational failures                        |


---



## 12. How to keep yourself up to date

The field moves monthly. A sustainable habit:

1. **Follow the pipeline, not the hype.** When you see a launch, ask: STT, LLM, TTS, transport, or orchestration?
2. **Re-read latency claims carefully.** Vendor TTFA ≠ end-to-end phone latency.
3. **Watch turn-taking features.** Flux-style conversational STT, Smart Turn, Realtime barge-in — this is where UX leaps happen.
4. **Track open speech models.** Sesame CSM, Moshi, open Fish Speech weights — signal research direction even if you stay on APIs.
5. **Use this repo as a checklist.** Ambient? Turns? Register? Rhythm? If a product ignores all four, it is optimizing a different problem than naturalvoice.
6. **Revisit the companion research.** [problem-analysis.md](./problem-analysis.md) for theory; [benchmark section](../README.md#naturalness-benchmark-next) for measurement.



### Suggested reading trail (beginner → deeper)

1. This document (orientation)
2. [problem-analysis.md](./problem-analysis.md) (why agents feel fake)
3. Pipecat docs + this repo's module READMEs (how frames flow)
4. Levinson & Torreira 2015 (turn-taking science)
5. A modern pipeline essay (e.g. cascaded STT→LLM→TTS explainers from Deepgram/practitioner blogs)
6. Sesame "Crossing the Uncanny Valley of Conversational Voice" (model-layer philosophy)
7. SPEARBench / TurnNat papers (how researchers try to measure naturalness)

---



## 13. One-page cheat sheet

```
VOICE AGENT ≈ microphone/phone + STT + LLM + TTS + transport + turn-taking logic

STT  = ears     (Deepgram, AssemblyAI, Scribe, USF ASR…)
LLM  = brain    (GPT, Claude, Gemini…)
TTS  = mouth    (ElevenLabs, Cartesia, Fish, UltraVoice, Aura…)
Pipecat/LiveKit/Vapi = nervous system (wiring)
naturalvoice = social manners (room tone, patience, how you phrase speech)

Humans expect ~200–300ms gaps.
Robots often deliver multi-second gaps + perfect silence + written English aloud.

The uncanny valley in voice is not "needs a prettier voice."
It is "needs the whole conversation to behave like a person."
```

---



## 14. Sources & validation notes

This document synthesizes:

- In-repo research: [problem-analysis.md](./problem-analysis.md), [benchmark section](../README.md#naturalness-benchmark-next), module READMEs, project README
- Foundational citation: Levinson & Torreira (2015), *Frontiers in Psychology* — turn-taking timing
- Practitioner / industry landscape cross-checks (2025–2026): cascaded pipeline explainers; Deepgram voice-agent architecture guidance; public comparisons of ElevenLabs, Cartesia, Fish Audio, Vapi, OpenAI Realtime; Sesame CSM public README/blog; OpenAI Realtime docs
- Academic eval landscape summarized in the README's [benchmark section](../README.md#naturalness-benchmark-next) (SPEARBench, TurnNat, EVA-Bench, MOS limitations)

**Caveats for you as a beginner:** vendor latency numbers are marketing-adjacent; always treat them as *directional*. Model names and "best of" rankings rotate quickly — the **layer map** and **terminology** stay useful longer than any single leaderboard.

---

*Maintained as a living orientation doc for naturalvoice contributors. If a major layer of the stack shifts (e.g. cascades cease to dominate production), update §4, §8, and §12 first.*