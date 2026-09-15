# Local transcription evidence — 2026-09-15

Komşu contains an unconnected local adapter for `openai/whisper-tiny@169d4a4341b33bc18d8881c4b69c2e104e1cc0af`. The official model card declares Apache-2.0 and TR/EL/EN support. Provisioning downloads the 151,061,672-byte `model.safetensors` file, verifies SHA-256 `7ebd0e...2395`, and records complete provenance in `whisper-provenance.json`. The runtime loads local files only, rejects remote code and repeats the digest check.

The input boundary accepts only a resolved file below an explicitly approved local directory: PCM WAV, mono, 16-bit, 16 kHz, 0.2–30 seconds, at most 2 MB. It rejects malformed/wrong-format files and low-energy silence before loading the model. This is a conservative format/energy gate, not a full voice activity detector or adversarial decoder sandbox.

## Synthetic smoke result

Two WAVs in `data/audio.synthetic` were generated with disclosed Windows system voices. They contain no person or real event.

| Language / voice | Duration | Cold/warm inference | Literal WER |
|---|---:|---:|---:|
| EN / Microsoft Zira | 5.595 s | 6.750 s cold | 0.3077 |
| TR / Microsoft Tolga | 8.225 s | 0.448 s warm | 0.4375 |
| Micro | — | — | 0.3793 |

Whisper rendered “Seaside” as “c-side” and split Turkish “enkaz” into “en kaz”. Number formatting also changed words into digits. The examples retained the negative instruction, but two clean TTS clips cannot estimate false negatives, hallucination rate, language identification, accent/noise performance or field latency. A Greek system voice was unavailable.

The adapter requires a caller-supplied TR/EL/EN hint and labels it as not automatically confirmed. All transcripts require human comparison with playable source audio. There is deliberately no audio upload endpoint yet: encrypted durable custody, emergency-end deletion including backups/device caches, decode isolation, queue retry/idempotency, size/rate abuse controls and consent/legal handling must be built first.
