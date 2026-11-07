import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from hospital_monitor import pipelines as pl
from hospital_monitor.anomalies.vitals import VITAL_LIMITS
from hospital_monitor.synthetic import make_movement, make_prescriptions, make_vitals

SEV_COLOR = {3: "#C50F1F", 2: "#F7630C", 1: "#0F6CBD"}


def _load(kind: str, demo_fn, columns: str, key: str) -> pd.DataFrame | None:
    mode = st.radio("Fonte de dados", ["Dados sintéticos de demonstração", "Enviar CSV"], key=f"mode_{key}", horizontal=True)
    if mode.startswith("Dados"):
        return demo_fn()
    st.caption(f"Colunas esperadas: `{columns}`")
    up = st.file_uploader(f"CSV de {kind}", type="csv", key=f"up_{key}")
    return pd.read_csv(up, parse_dates=["timestamp"]) if up else None


def _vitals_tab(center):
    df = _load("sinais vitais", make_vitals, "timestamp, hr, sbp, dbp, spo2", "vitals")
    with st.expander("Parâmetros de detecção"):
        window = st.slider("Janela do z-score robusto (amostras)", 10, 120, 30)
        z = st.slider("Limiar do z-score", 2.0, 8.0, 4.0, 0.5)
        cont = st.slider("Contaminação do Isolation Forest", 0.005, 0.10, 0.02, 0.005)
    if df is None:
        return
    events, episodes, alerts = pl.analyze_vitals(df, window=window, z_threshold=z, contamination=cont)
    center.replace_source(pl.SRC_VITALS, alerts)

    signals = [s for s in VITAL_LIMITS if s in df.columns]
    pick = st.selectbox("Sinal", signals, format_func=lambda s: VITAL_LIMITS[s]["label"])
    fig = go.Figure(go.Scatter(x=df["timestamp"], y=df[pick], mode="lines", name=pick, line={"color": "#605E5C"}))
    ev = events[events["signal"] == pick]
    for sev, grp in ev.groupby("severity"):
        fig.add_trace(go.Scatter(x=grp["timestamp"], y=grp["value"], mode="markers",
                                 name={3: "crítico", 2: "alerta"}.get(int(sev), "info"),
                                 marker={"color": SEV_COLOR[int(sev)], "size": 8}))
    fig.update_layout(height=380, margin={"l": 0, "r": 0, "t": 20, "b": 0})
    st.plotly_chart(fig, use_container_width=True)
    st.metric("Episódios anômalos", len(episodes))
    st.dataframe(episodes, use_container_width=True, hide_index=True)


def _rx_tab(center):
    df = _load("prescrições", make_prescriptions, "timestamp, drug, dose_mg, frequency_per_day", "rx")
    if df is None:
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    events, alerts = pl.analyze_prescriptions(df)
    center.replace_source(pl.SRC_RX, alerts)
    st.subheader(f"{len(events)} anomalia(s) na prescrição")
    st.dataframe(events, use_container_width=True, hide_index=True)


def _move_tab(center):
    df = _load("movimentação", make_movement, "timestamp, activity", "move")
    with st.expander("Parâmetros de detecção"):
        thr = st.slider("Limiar de imobilidade (atividade)", 0.0, 0.3, 0.05, 0.01)
        hours = st.slider("Horas mínimas de imobilidade diurna", 1.0, 8.0, 3.0, 0.5)
        spike = st.slider("Limiar de pico (z-score)", 3.0, 10.0, 5.0, 0.5)
    if df is None:
        return
    events, alerts = pl.analyze_movement(df, inactivity_threshold=thr, inactivity_min_hours=hours, spike_z=spike)
    center.replace_source(pl.SRC_MOVE, alerts)
    fig = go.Figure(go.Scatter(x=df["timestamp"], y=df["activity"], mode="lines", line={"color": "#605E5C"}))
    for _, e in events.iterrows():
        fig.add_vrect(x0=e["start"], x1=e["end"], fillcolor=SEV_COLOR[int(e["severity"])], opacity=0.25, line_width=0)
    fig.update_layout(height=340, margin={"l": 0, "r": 0, "t": 20, "b": 0}, yaxis_title="atividade")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(events, use_container_width=True, hide_index=True)


def render(settings, center):
    st.title("Detecção de anomalias")
    st.caption("Sinais vitais, evolução de prescrições e padrões de movimentação. Cada análise atualiza a central de alertas.")
    t1, t2, t3 = st.tabs(["Sinais vitais", "Prescrições", "Movimentação"])
    with t1:
        _vitals_tab(center)
    with t2:
        _rx_tab(center)
    with t3:
        _move_tab(center)
