"""Relatório consolidado em Markdown (baixável pela interface)."""

from __future__ import annotations

from datetime import datetime

from .alerts import AlertCenter, Severity


def build_markdown_report(patient: str, center: AlertCenter, notes: str = "") -> str:
    counts = center.counts()
    lines = [
        f"# Relatório de monitoramento - paciente {patient or 'não informado'}",
        f"_Gerado em {datetime.now():%d/%m/%Y %H:%M}_",
        "",
        "## Resumo",
        f"- Críticos: **{counts['CRÍTICO']}**",
        f"- Alertas: **{counts['ALERTA']}**",
        f"- Informativos: **{counts['INFO']}**",
        "",
    ]
    for source in sorted({a.source for a in center.alerts}):
        lines += [f"## {source}", "", "| Severidade | Título | Detalhe | Quando |", "|---|---|---|---|"]
        for a in center.alerts:
            if a.source == source:
                lines.append(f"| {a.severity.label} | {a.title} | {a.message} | {a.when} |")
        lines.append("")
    if len(center) == 0:
        lines += ["Nenhuma anomalia registrada nesta sessão.", ""]
    if notes:
        lines += ["## Observações", notes, ""]
    lines += [
        "---",
        "> Os alertas são gerados por heurísticas e modelos de apoio à decisão. "
        "Não substituem avaliação clínica.",
    ]
    return "\n".join(lines)


__all__ = ["build_markdown_report", "Severity"]
