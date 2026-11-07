import pandas as pd
import pytest

from hospital_monitor.anomalies.movement import detect_movement_anomalies
from hospital_monitor.anomalies.prescriptions import detect_prescription_anomalies
from hospital_monitor.anomalies.vitals import detect_vitals_anomalies, vitals_episodes
from hospital_monitor.synthetic import make_movement, make_prescriptions, make_vitals
from hospital_monitor.utils import find_runs


def test_find_runs():
    assert find_runs([0, 1, 1, 0, 1]) == [(1, 2), (4, 4)]
    assert find_runs([]) == []
    assert find_runs([1, 1]) == [(0, 1)]


def test_vitals_detects_injected_tachycardia_and_desaturation():
    df = make_vitals()
    events = detect_vitals_anomalies(df)
    hr = events[events["signal"] == "hr"]
    window = (hr["timestamp"] >= df["timestamp"][200]) & (hr["timestamp"] <= df["timestamp"][214])
    assert window.sum() >= 10
    spo2 = events[events["signal"] == "spo2"]
    assert (spo2["severity"] == 3).any()

    episodes = vitals_episodes(events)
    assert {"hr", "spo2", "sbp"} <= set(episodes["signal"])


def test_vitals_clean_series_has_few_alerts():
    df = make_vitals(inject=False)
    events = detect_vitals_anomalies(df, use_isolation_forest=False)
    assert len(events) < 0.03 * len(df)
    assert not (events["severity"] == 3).any()


def test_vitals_requires_timestamp():
    with pytest.raises(ValueError):
        detect_vitals_anomalies(pd.DataFrame({"hr": [70, 71]}))


def test_prescriptions_detects_jumps_and_interactions():
    ev = detect_prescription_anomalies(make_prescriptions())
    assert "enalapril" not in set(ev["drug"])
    assert ((ev["drug"] == "dipirona") & (ev["severity"] == 3)).any()
    assert ((ev["drug"] == "tramadol") & (ev["severity"] == 3)).any()
    assert ev["reason"].str.contains("varfarina").any()


def test_prescriptions_missing_columns():
    with pytest.raises(ValueError):
        detect_prescription_anomalies(pd.DataFrame({"drug": ["x"]}))


def test_movement_detects_inactivity_and_fall():
    events = detect_movement_anomalies(make_movement())
    kinds = set(events["kind"])
    assert "imobilidade" in kinds
    assert "queda_suspeita" in kinds


def test_movement_clean_has_no_events():
    assert detect_movement_anomalies(make_movement(inject=False)).empty


def test_vitals_clean_series_with_isolation_forest_stays_quiet():
    # O Isolation Forest sozinho marcaria ~2% dos pontos; a corroboração por z-score evita isso.
    events = detect_vitals_anomalies(make_vitals(inject=False))
    assert len(events) <= 5
    assert not (events["severity"] == 3).any()
