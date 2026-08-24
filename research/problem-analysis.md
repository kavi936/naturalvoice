# The Voice Agent Naturalness Problem: A Layered Analysis

**naturalvoice research document · v0.1**

---

## Abstract

Voice AI agents have achieved high accuracy in speech recognition and task completion, yet users consistently report that interactions feel robotic, strained, and unnatural — even when agents perform their function correctly. This paper argues that naturalness failure in voice AI is not a model-quality problem but an architectural one: current pipelines optimize for information exchange while ignoring the social, acoustic, and linguistic layers that govern real human conversation. We identify four distinct failure layers — acoustic environment, turn-taking, linguistic register, and temporal rhythm — and propose a middleware protocol (naturalvoice) that intervenes at each layer without requiring model replacement.

---

## 1. Introduction

Phone calls carry a social contract that text-based interfaces do not. When a person picks up the phone, they bring a set of unconscious expectations built over a lifetime of human conversation: ambient sound from the other end of the line, natural rhythms of pause and response, filler language that signals thinking and social connection. These are not aesthetic preferences. They are the substrate of spoken communication — the layer beneath the words.

Current voice AI agents are optimized almost entirely for the informational layer: accuracy of transcription, relevance of response, latency of delivery. The social substrate is treated as noise to be eliminated rather than signal to be replicated.

The result is a consistent experience: technically correct, socially wrong.

Consider a concrete example. A user calls a restaurant to make a reservation. They are connected to an AI agent. The agent correctly identifies availability, processes the booking, and completes the task in under two minutes — faster than any human host. But the interaction feels deeply uncomfortable. There is no background noise from the restaurant floor. When the user pauses to think, the agent cuts back in. When the agent processes the booking request, it says "I am checking availability for Saturday evening" — not "let me just — yeah, one sec, checking Saturday for you." Every response is informationally complete and conversationally sterile.

This is the uncanny valley of voice AI. And it is a solvable problem.

---

## 2. The Uncanny Valley Applied to Voice

The term "uncanny valley" was coined by Japanese roboticist Masahiro Mori in 1970 to describe the discomfort humans feel when artificial entities approximate — but do not reach — human appearance. The effect is non-linear: a robot that looks 60% human provokes no unease, but one that looks 95% human provokes intense discomfort, because the remaining 5% of deviation is perceived against a backdrop of high human-likeness, making each flaw more salient.

The same dynamic applies to voice. Peer-reviewed research (ScienceDirect, 2024) has established that organic-sounding voices increase the level of specialized perceptual processing due to their proximity to natural human voices — which also increases the sensitivity to deviations and their negative evaluation. In practical terms: the better an AI voice gets at sounding human, the more harshly listeners judge its remaining unnatural properties.

This has a direct implication for voice agent design. Improving TTS quality alone — making the voice itself more convincing — may actually intensify the uncanny valley effect if the surrounding conversational behavior remains robotic. A highly realistic voice delivering a stilted turn-taking pattern feels worse, not better, than a clearly synthetic voice doing the same.

The solution is not to make the voice more human. It is to make the entire conversational system more human — across all four layers.

---

## 3. Failure Layer 1 — Acoustic Environment

### What is missing

Real phone calls are never acoustically neutral. Every call carries room tone — the ambient sound of the environment the caller is in. A call from a restaurant has a low hum of conversation, cutlery, and kitchen noise bleeding through. A call from an office has the muffled sound of an open-plan environment. A call from a car has road noise and slight echo. These are not imperfections. They are acoustic signals that tell the listener where the other person is, that they are real, that the call is live.

Voice agent calls have none of this on the agent's side. The TTS output is studio-clean — no room tone, no ambient bleed, no microphone coloration. The result is an acoustic signature that human listeners register as wrong before a single word is processed.

### Why it matters

This is the most underexplored failure mode in voice AI research and the most novel contribution of the naturalvoice protocol. There is currently no published standard or open-source implementation for ambient audio injection as a deliberate conversational design technique. The fix is technically simple — audio mixing at the output layer — but requires identifying it as a problem worth solving.

### The naturalvoice intervention

The Ambient Layer module injects a configurable audio profile — restaurant, office, call center, outdoor — at low amplitude into the outgoing TTS stream. This does not mask the agent's speech; it provides the acoustic context that real calls carry naturally. Mix levels are configurable per deployment context.

---

## 4. Failure Layer 2 — Turn-Taking Architecture

### The Levinson paradox

In 2015, Stephen Levinson and Francisco Torreira published a foundational study on human turn-taking that identified what they called a paradox: humans achieve remarkably short gaps between conversational turns — typically 200–300ms — despite needing significantly longer to formulate a linguistic response. The resolution is that humans predict when the other speaker will finish talking and begin preparing their response before that moment arrives. Turn-taking is not reactive; it is anticipatory.

Voice AI systems are structurally reactive. They wait for a confident end-of-speech signal — silence above a threshold — before beginning any response processing. This means they are architecturally incapable of matching human turn-taking timing under normal operating conditions.

The gap between expectation and reality is severe. Research across deployed production systems shows median response latency of 1,400–1,700ms — five to eight times the 200–300ms baseline humans expect from a conversation partner. Users do not consciously register this as "high latency." They register it as the agent feeling "slow," "unresponsive," or as though it "doesn't understand when I'm done talking."

### Binary VAD and its limits

Current voice agents use Voice Activity Detection (VAD) as their turn-taking model. VAD classifies audio as either "speech active" or "not active" and triggers agent response when activity stops. This binary model cannot distinguish:

- A thinking pause (the caller is mid-thought, not done)
- A sentence-ending silence (the caller has finished their turn)
- A side conversation (the caller is briefly speaking to someone nearby)
- A backchannel ("mm-hmm", "right", "yeah") — a listener signal that does not constitute a turn

CHI 2025 peer-reviewed research confirms that this rigid turn-taking architecture "lacks interactivity and initiative, limiting the flexible communication between voice agents and users." The absence of backchannel handling — where the agent provides subtle signals of active listening while the caller speaks — is itself an uncanniness signal. Human listeners expect "mm-hmm" and "yeah" during conversation. Silence from a listener feels like absence.

### The naturalvoice intervention

The Turn Manager replaces binary VAD with a three-state conversational model: `SPEAKING`, `THINKING`, and `SIDE_CONVERSATION`. State classification uses Deepgram's word-level timestamps and confidence scores alongside pause duration and utterance completeness signals. A configurable patience window prevents premature interruption. The module also generates periodic backchannel audio ("mm-hmm", "right", "I see") during extended caller speech.

---

## 5. Failure Layer 3 — Linguistic Register

### Written language vs. spoken language

LLMs produce text. TTS converts that text to audio. The problem is that text and speech are not the same register of language, and the difference is not stylistic — it is structural.

Written language is designed to be complete, grammatical, and unambiguous on the page. It does not need to hold anyone's attention in real time. It can be re-read. Spoken language operates under entirely different constraints: it must hold the floor in real time, signal to the listener that the speaker is still processing, maintain social connection during computation, and convey information through prosody as much as through words.

The difference between the two registers is visible in a simple comparison:

> **Written register:** "I am checking availability for Saturday evening. Unfortunately we have no tables available at that time."

> **Spoken register:** "Let me just — yeah, one sec, checking Saturday for you... Ahh, I'm sorry, looks like we're fully booked that evening."

The second version is not more accurate. It is more human. The filler language ("let me just", "one sec", "Ahh") is doing real conversational work: it signals that the agent is actively processing, it holds the floor so the caller doesn't wonder if the call dropped, and it softens the negative result with a prosodic marker of genuine regret.

Sesame AI, whose Conversational Speech Model (CSM) represents the leading model-layer approach to this problem, has observed that what makes their voice companions feel lifelike is not perfection — it is intentional imperfection. Stutters, pauses, elongations, false starts — these trigger a deep perceptual response in human listeners. A real user, independent of any academic research, noted the same thing: "it would help if the AI could interject some 'umms' and 'ahs' to sound like it's thinking — to cover the gaps."

### The naturalvoice intervention

The Speech Renderer is a two-stage intervention. First, a prompt-layer instruction shapes the LLM's output toward spoken register: shorter clauses, hedges, discourse markers, and natural response progressions ("Okay so..." / "Right, let me check..." / "Yeah, unfortunately..."). Second, a post-processing step applies TTS markup — ElevenLabs and Cartesia both support elongation, pause injection, and prosodic variation through text-level signals — before the text reaches the TTS engine.

---

## 6. Failure Layer 4 — Temporal Rhythm

### Pacing as uncanniness signal

Even within a single utterance, current TTS output exhibits an unnaturally consistent pacing that human listeners register as wrong over the course of a conversation. Human speech has micro-pauses between clauses, speed variation tied to cognitive load and emotional content, and emphasis shifts that carry meaning independent of word choice.

TTS systems — even state-of-the-art ones — tend toward consistent syllable-level pacing because they optimize for intelligibility and voice quality metrics that do not penalize rhythmic uniformity. The result is speech that sounds polished in a ten-second demo but fatiguing and artificial in a two-minute call.

### The naturalvoice intervention

This layer is partially outside the control of application-layer middleware, as it depends on TTS engine behavior. The Speech Renderer addresses it partially through SSML and ElevenLabs voice setting configuration. Full resolution requires TTS engine support for prosodic variation — an open problem flagged here for future work.

---

## 7. Prior Art and Landscape

### Sesame CSM

Sesame AI's Conversational Speech Model (CSM), open-sourced in March 2025 under the Apache 2.0 license, is the most significant prior work on the voice naturalness problem. Sesame's research paper frames the goal as "voice presence" — making voice interaction feel genuine, understood, and valued. Their technical approach uses a two-stage autoregressive transformer architecture that incorporates conversation history directly into speech generation, producing measurably better results on prosodic naturalness than context-free TTS.

Sesame's own evaluation found that when conversation context is included, human evaluators consistently prefer real recordings over CSM output — acknowledging that a gap remains. CSM is also currently English-only.

**naturalvoice's differentiation:** Sesame's approach is model-layer — it requires adopting a new speech generation architecture. naturalvoice is a middleware protocol that operates on top of any existing pipeline. A team running Pipecat + ElevenLabs + Deepgram today can integrate naturalvoice without changing their model stack. The two approaches are complementary: naturalvoice's interventions would still apply on top of a CSM-based TTS.

### OpenAI Realtime API

OpenAI's Realtime API brings Advanced Voice Mode to third-party applications, offering speech-to-speech capabilities designed for natural conversation. Its primary improvements over earlier voice AI are in latency reduction and interruption handling. It does not address ambient acoustic environment, linguistic register, or the three-state turn-taking problem.

### Pipecat

Pipecat (Daily.co) is the open-source Python framework that naturalvoice uses as its integration target. Pipecat handles pipeline orchestration, STT/TTS integration, and WebRTC transport. It does not address any of the four naturalness failure layers at the framework level — those are left to application developers. naturalvoice fills this gap with composable modules that plug directly into Pipecat's processor architecture.

### The gap

No existing open-source project provides a composable, model-agnostic middleware layer targeting all four naturalness failure layers simultaneously. naturalvoice is the first attempt to define such a protocol.

---

## 8. The naturalvoice Protocol

naturalvoice is organized around three composable modules that each target one or more failure layers:

| Module | Failure Layer(s) | Mechanism |
|---|---|---|
| Ambient Layer | Acoustic Environment | Audio mixing at TTS output |
| Turn Manager | Turn-Taking | Three-state VAD + backchannel generation |
| Speech Renderer | Linguistic Register + Temporal Rhythm | Prompt shaping + TTS markup |

Each module is independently deployable. A team that only wants to address turn-taking can integrate the Turn Manager without adopting the other modules. Each module exposes a configuration interface for tuning behavior per deployment context (e.g. patience window duration, ambient audio profile, filler language intensity).

The protocol is designed for Pipecat as a primary integration target but is architecturally portable to any pipeline that exposes audio and text processing hooks.

---

## 9. Open Problems

naturalvoice does not solve the following, and acknowledges them openly:

**Emotional mirroring.** If a caller sounds frustrated or distressed, the agent's tone should shift accordingly. This requires real-time sentiment analysis driving TTS voice settings — achievable in principle but not implemented in v0.1.

**Multilingual naturalness.** Spoken register, filler language, and turn-taking conventions vary significantly across languages. The current Speech Renderer is optimized for English.

**Temporal rhythm at the TTS layer.** Full resolution of Failure Layer 4 requires TTS engine support for prosodic variation that most current engines do not provide reliably. This is flagged as a dependency on upstream TTS improvement.

**Phone-line audio simulation.** A more complete Ambient Layer would also simulate phone line compression artifacts and microphone coloration, not just background noise. This is technically feasible and on the roadmap.

**Evaluation metrics.** There is no standard benchmark for conversational naturalness in voice agents. naturalvoice would benefit from contributing to or adopting a naturalness evaluation framework — this is an open area of research.

---

## 10. References

- Levinson, S. C. & Torreira, F. (2015). Timing in turn-taking and its implications for processing models of language. *Frontiers in Psychology.*
- CHI 2025. "Toward Enabling Natural Conversation with Older Adults via the Design of LLM-Powered Voice Agents that Support Interruptions and Backchannels." *ACM CHI Conference on Human Factors in Computing Systems.*
- ScienceDirect (2024). "Deviation from typical organic voices best explains a vocal uncanny valley."
- Sesame AI (2025). "Crossing the Uncanny Valley of Conversational Voice." sesame.com/blog.
- Mori, M. (1970). The uncanny valley. *Energy*, 7(4), 33–35. (Trans. MacDorman & Kageki, 2012.)
- Hamming AI (2026). "Voice AI Latency: What's Fast, What's Slow, and How to Fix It." hamming.ai/resources.
- Tavus (2026). "Factors affecting latency in real-time voice AI conversations." tavus.io.
- Ekstedt, E. & Skantze, G. (2022). Voice Activity Projection: Self-supervised learning of turn-taking events. *Interspeech 2022.*
- Wang et al. (2024). Turn-taking and backchannel prediction with acoustic and large language model fusion. *ICASSP 2024.*
