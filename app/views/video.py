import os
import tempfile

import plotly.graph_objects as go
import streamlit as st

from hospital_monitor import pipelines as pl
from hospital_monitor.video.pose_metrics import PROFILES

WATCHABLE = ["scissors", "knife", "cell phone", "bottle", "cup"]


@st.cache_resource(show_spinner="Carregando modelos YOLOv8 (1ª vez baixa os pesos)...")
def _models(models_dir: str):
    from hospital_monitor.video.detector import load_models

    return load_models(models_dir)


def render(settings, center):
    import cv2  # noqa: F401  (falha cedo e com mensagem clara se faltar)

    from hospital_monitor.video.detector import analyze_video

    st.title("Análise de vídeo clínico")
    st.caption("YOLOv8-pose extrai 17 keypoints (postura); YOLOv8 detecta objetos e áreas críticas. Eventos fora do padrão viram alertas.")

    up = st.file_uploader("Vídeo (fisioterapia ou procedimento gravado)", type=["mp4", "mov", "avi", "mkv"])
    c1, c2, c3 = st.columns(3)
    profile_name = c1.selectbox("Perfil do exercício/procedimento", list(PROFILES))
    stride = c2.slider("Analisar 1 a cada N quadros", 1, 10, 3, help="Maior = mais rápido, menos preciso")
    max_s = c3.slider("Duração máxima analisada (s)", 10, 300, 90)
    st.caption(PROFILES[profile_name].description)

    roi = None
    watch: tuple[str, ...] = ("scissors", "knife")
    with st.expander("Área crítica (ROI) e objetos observados"):
        if st.checkbox("Definir área crítica"):
            x = st.slider("Horizontal (fração da imagem)", 0.0, 1.0, (0.6, 1.0))
            y = st.slider("Vertical (fração da imagem)", 0.0, 1.0, (0.5, 1.0))
            roi = (x[0], y[0], x[1], y[1])
            watch = tuple(st.multiselect("Objetos que não devem entrar na área", WATCHABLE, default=["scissors", "knife"]))

    if not up:
        st.info("Envie um vídeo para começar. Dica: use um clipe curto (10-30 s) de agachamento ou caminhada.")
        return
    if not st.button("🔍 Analisar vídeo", type="primary"):
        return

    suffix = os.path.splitext(up.name)[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(up.getbuffer())
        path = tmp.name
    bar = st.progress(0.0, text="Processando quadros...")
    try:
        result = analyze_video(
            path, PROFILES[profile_name], _models(settings.models_dir),
            stride=stride, max_seconds=max_s, roi=roi, watch_classes=watch,
            progress_cb=lambda p: bar.progress(p, text=f"Processando quadros... {p:.0%}"),
        )
    finally:
        os.unlink(path)
        bar.empty()

    st.session_state["video_result"] = result
    center.replace_source(pl.SRC_VIDEO, pl.video_alerts(result.events))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Duração analisada", f"{result.duration_s:.1f} s")
    m2.metric("Quadros analisados", result.frames_analyzed)
    m3.metric("Eventos", len(result.events))
    m4.metric("Críticos", sum(1 for e in result.events if int(e.severity) == 3))

    st.subheader("Ângulos articulares ao longo do tempo")
    fig = go.Figure()
    for col in ("knee_l", "knee_r", "trunk_tilt"):
        fig.add_trace(go.Scatter(x=result.metrics["time_s"], y=result.metrics[col], mode="lines", name=col))
    for e in result.events:
        fig.add_vrect(x0=e.t_start, x1=max(e.t_end, e.t_start + 0.2), fillcolor="#C50F1F" if int(e.severity) == 3 else "#F7630C",
                      opacity=0.2, line_width=0)
    fig.update_layout(height=360, margin={"l": 0, "r": 0, "t": 20, "b": 0}, xaxis_title="tempo (s)", yaxis_title="graus")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Eventos detectados")
    if not result.events:
        st.success("Nenhum desvio relevante encontrado.")
    for e in result.events:
        with st.expander(f"[{e.severity.label}] {e.t_start:.1f}s - {e.kind.replace('_', ' ')}: {e.message}"):
            snap = result.nearest_snapshot(e.t_start)
            if snap:
                st.image(snap[1][:, :, ::-1], caption=f"Quadro anotado em {snap[0]:.1f}s", use_container_width=True)

    if result.object_frames:
        st.subheader("Objetos detectados (nº de quadros em que apareceram)")
        st.bar_chart(result.object_frames)
