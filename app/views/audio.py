import os
import tempfile

import streamlit as st

from hospital_monitor import pipelines as pl
from hospital_monitor.audio.io import load_audio, to_wav_16k_mono
from hospital_monitor.audio.text_analytics import analyze_text
from hospital_monitor.audio.voice_features import assess_voice, extract_voice_features

SAMPLE = (
    "Doutor, eu estou muito cansado nos últimos dias. Sinto uma falta de ar quando subo a escada "
    "e ontem tive uma tontura forte. Também estou com dor no peito de vez em quando e me sinto fraco."
)


def render(settings, center):
    st.title("Análise de áudio da consulta")
    st.caption("Características vocais (pausas, tom, jitter) + Azure Speech to Text + Azure AI Language + termos críticos.")

    audio_file = st.file_uploader("Gravação da consulta", type=["wav", "flac", "ogg"])
    if hasattr(st, "audio_input"):
        rec = st.audio_input("...ou grave agora")
        audio_file = audio_file or rec
    if audio_file is None:
        st.info("Envie ou grave um áudio. Para a demonstração, 20-60 s de fala em português funcionam bem.")
        return

    data = audio_file.getvalue()
    # Trocou de áudio: descarta transcrição, confiança e palavras/min do arquivo anterior.
    signature = (getattr(audio_file, "name", ""), len(data))
    if st.session_state.get("audio_signature") != signature:
        for key in ("transcript", "wpm", "stt_conf"):
            st.session_state.pop(key, None)
        st.session_state["audio_signature"] = signature
    st.audio(data)
    try:
        y, sr = load_audio(data)
        feat = extract_voice_features(y, sr)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Não foi possível processar o áudio: {exc}")
        return

    st.subheader("1. Características vocais")
    c = st.columns(5)
    c[0].metric("Duração", f"{feat.duration_s:.1f} s")
    c[1].metric("Silêncio", f"{feat.silence_ratio:.0%}")
    c[2].metric("Pausas/min", f"{feat.pauses_per_min:.0f}")
    c[3].metric("f0 médio", "-" if feat.f0_mean_hz != feat.f0_mean_hz else f"{feat.f0_mean_hz:.0f} Hz")
    c[4].metric("Jitter aprox.", "-" if feat.jitter_pct != feat.jitter_pct else f"{feat.jitter_pct:.1f}%")

    st.subheader("2. Transcrição (Azure Speech to Text)")
    if settings.speech_enabled:
        if st.button("🎙️ Transcrever com Azure Speech"):
            with st.spinner("Transcrevendo..."):
                wav = to_wav_16k_mono(y, sr)
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    tmp.write(wav)
                    path = tmp.name
                try:
                    from hospital_monitor.audio.speech import transcribe_wav

                    tr = transcribe_wav(path, settings.speech_key, settings.speech_region, settings.speech_language)
                    st.session_state["transcript"] = tr.text
                    st.session_state["wpm"] = tr.words_per_minute
                    st.session_state["stt_conf"] = tr.mean_confidence
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Falha na transcrição: {exc}")
                finally:
                    os.unlink(path)
    else:
        st.warning("Azure Speech não configurado (AZURE_SPEECH_KEY / AZURE_SPEECH_REGION). Cole a transcrição manualmente.")

    if st.button("Usar texto de exemplo"):
        st.session_state["transcript"] = SAMPLE
        st.session_state.pop("wpm", None)
    transcript = st.text_area("Transcrição", key="transcript", height=140)
    if st.session_state.get("stt_conf") is not None:
        st.caption(f"Confiança média do reconhecimento: {st.session_state['stt_conf']:.0%}")

    wpm = st.session_state.get("wpm")
    if wpm is None and transcript.strip():
        speech_s = max(feat.duration_s * (1 - feat.silence_ratio), 1e-6)
        wpm = len(transcript.split()) / (speech_s / 60.0)
    findings = assess_voice(feat, words_per_min=wpm)

    st.subheader("3. Análise de texto (Azure AI Language + termos críticos)")
    insights = None
    if transcript.strip():
        try:
            insights = analyze_text(transcript, settings.language_endpoint, settings.language_key)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Azure AI Language falhou ({exc}); usando análise local.")
            insights = analyze_text(transcript)
        st.caption(f"Fonte da análise: **{insights.source}**")
        s1, s2 = st.columns(2)
        s1.metric("Sentimento predominante", insights.sentiment)
        s2.bar_chart(insights.scores)
        if insights.key_phrases:
            st.write("**Frases-chave:** " + ", ".join(insights.key_phrases[:15]))
        if insights.entities:
            st.dataframe(insights.entities, width="stretch", hide_index=True)
        if insights.critical_terms:
            st.error("Termos críticos: " + ", ".join(f"{t['term']} ({t['category']})" for t in insights.critical_terms))

    st.subheader("4. Indicadores de alerta")
    if wpm:
        st.caption(f"Velocidade de fala estimada: {wpm:.0f} palavras/min")
    if not findings:
        st.success("Nenhum indicador vocal fora do padrão.")
    for f in findings:
        st.warning(f.message)

    alerts = pl.audio_alerts(findings, insights)
    center.replace_source(pl.SRC_AUDIO, alerts)
    st.caption(f"{len(alerts)} alerta(s) enviados à central.")
