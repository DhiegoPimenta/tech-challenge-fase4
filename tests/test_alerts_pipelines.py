import pandas as pd

from hospital_monitor import pipelines as pl
from hospital_monitor.alerts import Alert, AlertCenter, Severity
from hospital_monitor.config import load_settings
from hospital_monitor.report import build_markdown_report
from hospital_monitor.synthetic import make_movement, make_prescriptions, make_vitals


def test_alert_center_counts_and_replace():
    c = AlertCenter()
    c.add(Alert("Vídeo", Severity.CRITICAL, "a", "m"))
    c.add(Alert("Áudio", Severity.WARNING, "b", "m"))
    c.replace_source("Vídeo", [Alert("Vídeo", Severity.INFO, "c", "m")])
    assert c.counts() == {"CRÍTICO": 0, "ALERTA": 1, "INFO": 1}
    assert c.alerts[0].severity == Severity.WARNING  # ordenado por severidade
    c.clear()
    assert len(c) == 0
    assert list(c.to_dataframe().columns) == ["severity", "source", "title", "message", "when"]


def test_format_text_filters_by_severity():
    c = AlertCenter()
    c.add(Alert("Áudio", Severity.INFO, "x", "y"))
    assert "Nenhum alerta" in c.format_text(Severity.WARNING)


def test_pipelines_produce_alerts_for_every_series_source():
    _, episodes, a1 = pl.analyze_vitals(make_vitals())
    _, a2 = pl.analyze_prescriptions(make_prescriptions())
    _, a3 = pl.analyze_movement(make_movement())
    assert a1 and a2 and a3
    assert len(a1) == len(episodes)
    assert {a.source for a in a1 + a2 + a3} == {pl.SRC_VITALS, pl.SRC_RX, pl.SRC_MOVE}
    assert any(a.severity == Severity.CRITICAL for a in a1)


def test_report_contains_sections():
    c = AlertCenter()
    _, a = pl.analyze_prescriptions(make_prescriptions())
    c.replace_source(pl.SRC_RX, a)
    md = build_markdown_report("PAC-1", c, notes="obs")
    assert "PAC-1" in md and "## Prescrições" in md and "CRÍTICO" in md and "obs" in md


def test_report_empty():
    assert "Nenhuma anomalia" in build_markdown_report("PAC-1", AlertCenter())


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("AZURE_SPEECH_KEY", "k")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "brazilsouth")
    monkeypatch.delenv("AZURE_LANGUAGE_KEY", raising=False)
    s = load_settings()
    assert s.speech_enabled and not s.language_enabled


def test_episode_grouping_merges_close_points():
    from hospital_monitor.anomalies.episodes import group_episodes

    ts = pd.to_datetime(["2025-01-01 10:00", "2025-01-01 10:01", "2025-01-01 10:02", "2025-01-01 11:00"])
    ev = pd.DataFrame({"timestamp": ts, "signal": "hr", "value": [1.0, 2, 3, 4], "severity": [2, 3, 2, 2], "reason": "r"})
    out = group_episodes(ev, pd.Timedelta(minutes=5))
    assert len(out) == 2
    assert out.loc[0, "severity"] == 3 and out.loc[0, "n_points"] == 3


def test_episode_reasons_are_not_repeated():
    from hospital_monitor.anomalies.episodes import group_episodes

    ts = pd.to_datetime(["2025-01-01 10:00", "2025-01-01 10:01", "2025-01-01 10:02"])
    ev = pd.DataFrame(
        {
            "timestamp": ts,
            "signal": "hr",
            "value": [1.0, 2.0, 3.0],
            "severity": [3, 3, 2],
            "reason": ["fora do limite; variação abrupta", "fora do limite", "variação abrupta; atípico"],
        }
    )
    reasons = group_episodes(ev, pd.Timedelta(minutes=5)).loc[0, "reasons"].split("; ")
    assert len(reasons) == len(set(reasons)) == 3
