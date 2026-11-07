"""Ponto de entrada do Streamlit: `streamlit run app/streamlit_app.py`."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import streamlit as st  # noqa: E402
from views import alerts_view, anomalies, audio, overview, video  # noqa: E402

from hospital_monitor.alerts import AlertCenter  # noqa: E402
from hospital_monitor.config import load_settings  # noqa: E402

st.set_page_config(page_title="Monitor Clínico Multimodal", page_icon="🏥", layout="wide")

if "alerts" not in st.session_state:
    st.session_state.alerts = AlertCenter()

settings = load_settings()
center: AlertCenter = st.session_state.alerts

PAGES = {
    "🏠 Visão geral": overview.render,
    "🎥 Vídeo": video.render,
    "🎙️ Áudio": audio.render,
    "📈 Anomalias": anomalies.render,
    "🚨 Alertas e relatório": alerts_view.render,
}

st.sidebar.title("🏥 Monitor Clínico")
page = st.sidebar.radio("Navegação", list(PAGES), label_visibility="collapsed")
st.sidebar.divider()
counts = center.counts()
st.sidebar.metric("Alertas críticos", counts["CRÍTICO"])
st.sidebar.metric("Alertas", counts["ALERTA"])
st.sidebar.caption("Tech Challenge - IADT Fase 4. Apoio à decisão; não substitui avaliação clínica.")

PAGES[page](settings, center)
