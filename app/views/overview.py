import streamlit as st

from hospital_monitor import pipelines as pl
from hospital_monitor.synthetic import make_movement, make_prescriptions, make_vitals

FLOW = """
digraph G {
  rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#EAF2FB", fontname="Helvetica"];
  video [label="Vídeo clínico"]; audio [label="Áudio da consulta"]; series [label="Sinais vitais\\nPrescrições\\nMovimentação"];
  yolo [label="YOLOv8-pose + YOLOv8\\n(postura, objetos, ROI)"];
  stt [label="Azure Speech\\n(Speech to Text)"]; lang [label="Azure AI Language\\n(sentimento, entidades)"];
  voice [label="Características vocais\\n(pausas, f0, jitter)"];
  ad [label="Detecção de anomalias\\n(regras + z-score + Isolation Forest)"];
  alerts [label="Central de alertas", fillcolor="#FDE7E9"]; team [label="Equipe médica\\n(painel, webhook, relatório)", fillcolor="#FDE7E9"];
  video -> yolo -> alerts; audio -> stt -> lang -> alerts; audio -> voice -> alerts; series -> ad -> alerts; alerts -> team;
}
"""


def render(settings, center):
    st.title("Monitor clínico multimodal")
    st.write(
        "Fusão de **vídeo, áudio e texto/séries temporais** para identificar sinais precoces de risco "
        "e alertar a equipe médica. Use o menu lateral para cada modalidade."
    )
    st.graphviz_chart(FLOW)

    st.subheader("Integrações Azure")
    c1, c2, c3 = st.columns(3)
    c1.metric("Azure Speech", "conectado" if settings.speech_enabled else "não configurado")
    c2.metric("Azure AI Language", "conectado" if settings.language_enabled else "não configurado")
    c3.metric("Webhook de alertas", "ativo" if settings.webhook_enabled else "não configurado")
    if not (settings.speech_enabled and settings.language_enabled):
        st.info("Sem chaves Azure o app roda em modo offline (léxico local; transcrição manual). Veja `.env.example`.")

    st.subheader("Demonstração rápida")
    st.caption("Roda os detectores de séries temporais com dados sintéticos (anomalias injetadas) e preenche a central de alertas.")
    if st.button("▶️ Rodar demonstração de séries temporais", type="primary"):
        _, _, a1 = pl.analyze_vitals(make_vitals())
        _, a2 = pl.analyze_prescriptions(make_prescriptions())
        _, a3 = pl.analyze_movement(make_movement())
        center.replace_source(pl.SRC_VITALS, a1)
        center.replace_source(pl.SRC_RX, a2)
        center.replace_source(pl.SRC_MOVE, a3)
        st.success(f"{len(a1) + len(a2) + len(a3)} alertas gerados. Veja a aba 🚨 Alertas e relatório.")
