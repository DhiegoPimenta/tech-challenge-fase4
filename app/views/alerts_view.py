import streamlit as st

from hospital_monitor.alerts import Severity
from hospital_monitor.report import build_markdown_report


def render(settings, center):
    st.title("Alertas e relatório")
    counts = center.counts()
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Críticos", counts["CRÍTICO"])
    c2.metric("🟠 Alertas", counts["ALERTA"])
    c3.metric("🔵 Informativos", counts["INFO"])

    if len(center) == 0:
        st.info("Nenhum alerta ainda. Rode a demonstração na Visão geral ou analise vídeo/áudio/séries.")
        return

    min_label = st.selectbox("Mostrar a partir de", ["INFO", "ALERTA", "CRÍTICO"], index=0)
    min_sev = {"INFO": Severity.INFO, "ALERTA": Severity.WARNING, "CRÍTICO": Severity.CRITICAL}[min_label]
    df = center.to_dataframe()
    order = {"CRÍTICO": 3, "ALERTA": 2, "INFO": 1}
    df = df[df["severity"].map(order) >= int(min_sev)]
    st.dataframe(df, width="stretch", hide_index=True)

    st.divider()
    st.subheader("Notificar a equipe médica")
    if settings.webhook_enabled:
        if st.button("📨 Enviar alertas (ALERTA e acima) ao webhook", type="primary"):
            try:
                n = center.dispatch_webhook(settings.alert_webhook_url)
                st.success(f"{n} alerta(s) enviados.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Falha ao enviar: {exc}")
    else:
        st.caption("Configure ALERT_WEBHOOK_URL (Teams/Slack/Logic App) para enviar notificações externas.")

    patient = st.text_input("Identificação do paciente (fictícia na demonstração)", "PAC-0001")
    notes = st.text_area("Observações", "")
    st.download_button(
        "⬇️ Baixar relatório (Markdown)",
        build_markdown_report(patient, center, notes),
        file_name=f"relatorio_{patient or 'paciente'}.md",
        mime="text/markdown",
    )
    if st.button("Limpar alertas"):
        center.clear()
        st.rerun()
