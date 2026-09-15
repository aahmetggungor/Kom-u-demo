"""Evaluate pinned local Whisper on two disclosed synthetic TTS fixtures."""

import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path

from komsu.transcription import LocalWhisperTranscriber

AUDIO_ROOT = Path("data/audio.synthetic")
CASES = [
    {
        "file": "en-trapped-number-eight.wav",
        "language": "en",
        "reference": "Three people are trapped at number eight Seaside Street. Do not send food.",
        "voice": "Microsoft Zira Desktop / en-US",
    },
    {
        "file": "tr-enkaz-alsancak.wav",
        "language": "tr",
        "reference": "Alsancak bin dört yüz altmış iki sokak, sekiz numara. Enkaz altında üç kişi var. Su gerekmiyor.",
        "voice": "Microsoft Tolga / tr-TR",
    },
]


def words(value: str) -> list[str]:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.findall(r"[^\W_]+", value, flags=re.UNICODE)


def word_error_rate(reference: str, hypothesis: str) -> tuple[int, int, float]:
    expected, actual = words(reference), words(hypothesis)
    previous = list(range(len(actual) + 1))
    for row, expected_word in enumerate(expected, 1):
        current = [row]
        for column, actual_word in enumerate(actual, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (expected_word != actual_word),
                )
            )
        previous = current
    errors = previous[-1]
    return errors, len(expected), round(errors / max(1, len(expected)), 4)


def main() -> None:
    adapter = LocalWhisperTranscriber("models/whisper-tiny", AUDIO_ROOT)
    results = []
    for case in CASES:
        path = AUDIO_ROOT / case["file"]
        started = time.perf_counter()
        output = adapter.transcribe(str(path), case["language"])
        errors, reference_words, wer = word_error_rate(case["reference"], output.text)
        with path.open("rb") as stream:
            audio_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        row = {
            **case,
            "audio_sha256": audio_sha256,
            "transcript": output.text,
            "model_revision": output.model_revision,
            "audio_seconds": output.duration_seconds,
            "inference_seconds": round(time.perf_counter() - started, 3),
            "word_errors": errors,
            "reference_words": reference_words,
            "wer": wer,
            "warnings": list(output.warnings),
        }
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    summary = {
        "kind": "synthetic-os-tts-smoke-not-human-speech-validation",
        "cases": len(results),
        "languages": ["en", "tr"],
        "greek_audio": "NOT_AVAILABLE",
        "micro_wer": round(
            sum(row["word_errors"] for row in results)
            / sum(row["reference_words"] for row in results),
            4,
        ),
        "human_transcript_review_required": True,
    }
    Path("docs/evaluation/whisper-diagnostic.json").write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
