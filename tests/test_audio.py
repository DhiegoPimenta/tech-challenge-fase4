import numpy as np
import pytest

from hospital_monitor.alerts import Severity
from hospital_monitor.audio.clinical_terms import find_critical_terms, local_sentiment
from hospital_monitor.audio.io import load_audio, to_wav_16k_mono
from hospital_monitor.audio.speech import Segment, Transcription
from hospital_monitor.audio.text_analytics import analyze_text
from hospital_monitor.audio.voice_features import (
    VoiceFeatures,
    assess_voice,
    extract_voice_features,
)

SR = 16000


def _tone_pause_tone(freq=150.0):
    t = np.arange(SR) / SR
    tone = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    return np.concatenate([tone, np.zeros(SR, dtype=np.float32), tone])


def test_voice_features_on_synthetic_signal():
    f = extract_voice_features(_tone_pause_tone(), SR)
    assert f.duration_s == pytest.approx(3.0, abs=0.01)
    assert 0.25 < f.silence_ratio < 0.40
    assert f.n_pauses == 1
    assert 0.8 < f.longest_pause_s < 1.1
    assert f.f0_mean_hz == pytest.approx(150, abs=5)
    assert f.jitter_pct < 1.0


def test_too_short_audio():
    with pytest.raises(ValueError):
        extract_voice_features(np.zeros(100, dtype=np.float32), SR)


def _features(**kw):
    base = dict(
        duration_s=30, rms_mean_db=-20, rms_std_db=8, silence_ratio=0.2, n_pauses=3,
        longest_pause_s=1.0, pauses_per_min=6, f0_mean_hz=150, f0_std_hz=30, jitter_pct=0.8, voiced_ratio=0.8,
    )
    base.update(kw)
    return VoiceFeatures(**base)


def test_assess_voice_normal_and_abnormal():
    assert assess_voice(_features(), words_per_min=130) == []
    kinds = {f.kind for f in assess_voice(_features(silence_ratio=0.6, longest_pause_s=4.5), words_per_min=60)}
    assert {"silencio", "pausa_longa", "fala_lenta"} <= kinds


def test_wav_roundtrip_resamples_to_16k():
    y = _tone_pause_tone()
    data = to_wav_16k_mono(y, SR)
    y2, sr2 = load_audio(data)
    assert sr2 == 16000
    assert len(y2) == len(y)


def test_transcription_properties():
    tr = Transcription([Segment(0.0, 5.0, "uma duas três quatro", 0.9), Segment(10.0, 5.0, "cinco seis", 0.7)])
    assert tr.text == "uma duas três quatro cinco seis"
    assert tr.mean_confidence == pytest.approx(0.8)
    assert tr.words_per_minute == pytest.approx(6 / (15 / 60))


def test_critical_terms_accent_insensitive():
    found = {t["term"] for t in find_critical_terms("Sinto palpitações, falta de ar e NÃO consigo respirar direito")}
    assert {"palpitacoes", "falta de ar", "nao consigo respirar"} <= found


def test_critical_terms_none():
    assert find_critical_terms("Estou me sentindo bem, obrigado") == []


def test_local_sentiment_negative_vs_neutral():
    neg = local_sentiment("Estou com muita dor, piorou e tenho medo")
    neu = local_sentiment("Tudo certo com a consulta de hoje")
    assert neg["negative"] > neu["negative"]


def test_analyze_text_local_fallback():
    out = analyze_text("Tenho dor no peito e tontura desde ontem")
    assert out.source == "local"
    assert any(t["severity"] == Severity.CRITICAL for t in out.critical_terms)


def test_jitter_is_low_for_stable_tone():
    f = extract_voice_features(_tone_pause_tone(), SR)
    assert f.jitter_pct < 0.5


def test_fatigue_words_are_flagged():
    found = {t["term"] for t in find_critical_terms("Estou muito cansado e me sinto fraco")}
    assert {"cansado", "fraco"} <= found
