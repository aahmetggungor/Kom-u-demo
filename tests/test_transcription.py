import json
import wave

import pytest
from komsu.transcription import AudioRejected, LocalWhisperTranscriber, NoSpeechDetected


def transcriber(tmp_path):
    model = tmp_path / "model"
    audio = tmp_path / "audio"
    model.mkdir()
    audio.mkdir()
    (model / "PROVENANCE.json").write_text(
        json.dumps(
            {
                "repository": "openai/whisper-tiny",
                "revision": "abc",
                "weights_file": "model.safetensors",
                "weights_sha256": "0" * 64,
            }
        )
    )
    return LocalWhisperTranscriber(model, audio), audio


def write_wav(path, frames, *, channels=1, width=2, rate=16_000):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(channels)
        stream.setsampwidth(width)
        stream.setframerate(rate)
        stream.writeframes(frames)


def test_silence_is_rejected_before_loading_model(tmp_path):
    adapter, audio = transcriber(tmp_path)
    path = audio / "silence.wav"
    write_wav(path, b"\0\0" * 16_000)
    with pytest.raises(NoSpeechDetected):
        adapter.transcribe(str(path), "tr")


def test_audio_must_be_inside_approved_root_and_pcm16k(tmp_path):
    adapter, audio = transcriber(tmp_path)
    outside = tmp_path / "outside.wav"
    write_wav(outside, b"\0\0" * 16_000)
    with pytest.raises(AudioRejected, match="approved"):
        adapter.transcribe(str(outside), "en")
    wrong = audio / "stereo.wav"
    write_wav(wrong, b"\0\0" * 32_000, channels=2)
    with pytest.raises(AudioRejected, match="mono"):
        adapter.transcribe(str(wrong), "en")


def test_language_hint_is_restricted_before_reading_audio(tmp_path):
    adapter, _ = transcriber(tmp_path)
    with pytest.raises(AudioRejected, match="Language"):
        adapter.transcribe("missing.wav", "fr")
