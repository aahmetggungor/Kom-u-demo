# Synthetic audio fixtures

These two WAV files were generated on Windows with `System.Speech` at 16 kHz, 16-bit, mono PCM on 2026-09-15. `en-trapped-number-eight.wav` uses Microsoft Zira Desktop (`en-US`); `tr-enkaz-alsancak.wav` uses Microsoft Tolga (`tr-TR`). The exact spoken references and file SHA-256 values are recorded by `scripts/evaluate_whisper.py` in `docs/evaluation/whisper-diagnostic.json`.

They contain no real person or emergency. Synthetic TTS is useful only for deterministic plumbing checks and substantially differs from noisy, stressed, accented telephone or field audio. A Greek system voice was unavailable, so there is no Greek audio result.
