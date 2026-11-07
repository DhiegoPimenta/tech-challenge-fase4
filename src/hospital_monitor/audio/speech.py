"""Transcrição com Azure AI Speech (Speech to Text), reconhecimento contínuo de arquivo WAV."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass


@dataclass
class Segment:
    offset_s: float
    duration_s: float
    text: str
    confidence: float | None


@dataclass
class Transcription:
    segments: list[Segment]

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments).strip()

    @property
    def mean_confidence(self) -> float | None:
        vals = [s.confidence for s in self.segments if s.confidence is not None]
        return sum(vals) / len(vals) if vals else None

    @property
    def words_per_minute(self) -> float | None:
        """Palavras por minuto de fala (do início do 1º ao fim do último segmento)."""
        if not self.segments:
            return None
        span = self.segments[-1].offset_s + self.segments[-1].duration_s - self.segments[0].offset_s
        words = len(self.text.split())
        return words / (span / 60.0) if span > 0 else None


def transcribe_wav(
    wav_path: str, key: str, region: str, language: str = "pt-BR", timeout_s: int = 300
) -> Transcription:
    """``wav_path`` deve ser WAV PCM 16 kHz mono (use ``audio.io.to_wav_16k_mono``)."""
    import azure.cognitiveservices.speech as speechsdk

    cfg = speechsdk.SpeechConfig(subscription=key, region=region)
    cfg.speech_recognition_language = language
    cfg.output_format = speechsdk.OutputFormat.Detailed

    audio = speechsdk.audio.AudioConfig(filename=wav_path)
    recognizer = speechsdk.SpeechRecognizer(speech_config=cfg, audio_config=audio)

    done = threading.Event()
    segments: list[Segment] = []
    errors: list[str] = []

    def on_recognized(evt):
        res = evt.result
        if res.reason == speechsdk.ResultReason.RecognizedSpeech and res.text:
            nbest = json.loads(res.json).get("NBest", [{}])
            segments.append(
                Segment(
                    offset_s=res.offset / 1e7,  # unidades de 100 ns
                    duration_s=res.duration / 1e7,
                    text=res.text,
                    confidence=nbest[0].get("Confidence") if nbest else None,
                )
            )

    def on_canceled(evt):
        if evt.reason == speechsdk.CancellationReason.Error:
            errors.append(f"{evt.error_code}: {evt.error_details}")
        done.set()  # EndOfStream também cai aqui

    recognizer.recognized.connect(on_recognized)
    recognizer.canceled.connect(on_canceled)
    recognizer.session_stopped.connect(lambda _evt: done.set())

    recognizer.start_continuous_recognition()
    finished = done.wait(timeout_s)
    recognizer.stop_continuous_recognition()

    if errors:
        raise RuntimeError(f"Azure Speech falhou: {errors[0]}")
    if not finished:
        raise TimeoutError("A transcrição excedeu o tempo limite.")
    return Transcription(segments=sorted(segments, key=lambda s: s.offset_s))
