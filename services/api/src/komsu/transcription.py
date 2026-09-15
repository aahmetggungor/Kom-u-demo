"""Conservative local Whisper adapter for approved bounded PCM WAV files."""

import hashlib
import json
import math
import sys
import wave
from array import array
from copy import deepcopy
from io import BytesIO
from pathlib import Path

from .ai import TranscriptionOutput

LANGUAGES = frozenset({"tr", "el", "en"})


class AudioRejected(ValueError):
    pass


class NoSpeechDetected(AudioRejected):
    pass


class LocalWhisperTranscriber:
    def __init__(
        self,
        model_path: str | Path,
        approved_audio_root: str | Path,
        *,
        max_seconds: float = 30.0,
        max_new_tokens: int = 192,
    ):
        if not 1 <= max_seconds <= 30:
            raise ValueError("max_seconds must be 1..30")
        if not 16 <= max_new_tokens <= 448:
            raise ValueError("max_new_tokens must be 16..448")
        self.model_path = Path(model_path).resolve()
        self.audio_root = Path(approved_audio_root).resolve()
        metadata = json.loads((self.model_path / "PROVENANCE.json").read_text(encoding="utf-8"))
        self.revision = f"{metadata['repository']}@{metadata['revision']}"
        self.weights_file = metadata["weights_file"]
        self.weights_sha256 = metadata["weights_sha256"]
        self.max_seconds = max_seconds
        self.max_new_tokens = max_new_tokens
        self._processor = None
        self._model = None

    def _audio_bytes(self, payload: bytes):
        if not payload or len(payload) > 2_000_000:
            raise AudioRejected("Only bounded WAV input is accepted")
        try:
            with wave.open(BytesIO(payload), "rb") as stream:
                if (
                    stream.getnchannels() != 1
                    or stream.getsampwidth() != 2
                    or stream.getframerate() != 16_000
                    or stream.getcomptype() != "NONE"
                ):
                    raise AudioRejected("WAV must be mono 16-bit PCM at 16 kHz")
                frames = stream.getnframes()
                duration = frames / 16_000
                if not 0.2 <= duration <= self.max_seconds:
                    raise AudioRejected("Audio duration is outside 0.2..30 seconds")
                raw = stream.readframes(frames)
        except (EOFError, wave.Error) as exc:
            raise AudioRejected("Malformed WAV") from exc
        samples = array("h")
        samples.frombytes(raw)
        if sys.byteorder != "little":
            samples.byteswap()
        rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples)) / 32768.0
        peak = max(abs(sample) for sample in samples) / 32768.0
        if rms < 0.003 or peak < 0.01:
            raise NoSpeechDetected("Audio energy is below the conservative speech gate")
        import numpy as np

        audio = np.asarray(samples, dtype="float32") / 32768.0
        return audio, duration

    def _audio(self, value: str | Path):
        path = Path(value).resolve()
        if self.audio_root not in path.parents or not path.is_file():
            raise AudioRejected("Audio path is outside the approved local root")
        if path.suffix.casefold() != ".wav" or path.stat().st_size > 2_000_000:
            raise AudioRejected("Only bounded WAV input is accepted")
        return self._audio_bytes(path.read_bytes())

    def _load(self):
        if self._model is not None:
            return self._processor, self._model
        weights = (self.model_path / self.weights_file).resolve()
        if self.model_path not in weights.parents or not weights.is_file():
            raise ValueError("Whisper weights escape or are absent from approved model root")
        with weights.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != self.weights_sha256:
            raise ValueError("Whisper weights fail recorded SHA-256 verification")
        from transformers import AutoProcessor, WhisperForConditionalGeneration

        self._processor = AutoProcessor.from_pretrained(  # nosec B615
            self.model_path, local_files_only=True, trust_remote_code=False
        )
        self._model = WhisperForConditionalGeneration.from_pretrained(  # nosec B615
            self.model_path,
            local_files_only=True,
            trust_remote_code=False,
            weights_only=True,
        ).eval()
        return self._processor, self._model

    def transcribe(
        self, approved_local_audio: str, language_hint: str | None = None
    ) -> TranscriptionOutput:
        if language_hint is not None and language_hint not in LANGUAGES:
            raise AudioRejected("Language hint must be tr, el or en")
        audio, duration = self._audio(approved_local_audio)
        return self._transcribe_audio(audio, duration, language_hint)

    def transcribe_bytes(
        self, approved_audio: bytes, language_hint: str | None = None
    ) -> TranscriptionOutput:
        if language_hint is not None and language_hint not in LANGUAGES:
            raise AudioRejected("Language hint must be tr, el or en")
        audio, duration = self._audio_bytes(approved_audio)
        return self._transcribe_audio(audio, duration, language_hint)

    def _transcribe_audio(self, audio, duration, language_hint):
        import torch

        processor, model = self._load()
        features = processor(audio, sampling_rate=16_000, return_tensors="pt").input_features
        generation = deepcopy(model.generation_config)
        generation.max_length = self.max_new_tokens
        generation.do_sample = False
        generation.task = "transcribe"
        if language_hint:
            generation.language = language_hint
        with torch.inference_mode():
            tokens = model.generate(features, generation_config=generation)
        text = processor.batch_decode(
            tokens, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0].strip()
        if not text or len(text) > 8000:
            raise NoSpeechDetected("Whisper returned empty or unbounded text")
        language = language_hint or "und"
        warnings = (
            "LANGUAGE_NOT_AUTOMATICALLY_CONFIRMED" if language_hint else "LANGUAGE_UNDETERMINED",
            "HUMAN_TRANSCRIPT_REVIEW_REQUIRED",
        )
        return TranscriptionOutput(text, language, self.revision, round(duration, 3), warnings)
