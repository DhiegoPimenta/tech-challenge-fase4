import numpy as np
import pandas as pd
import pytest

from hospital_monitor.video.pose_metrics import (
    PROFILES,
    detect_fall,
    detect_pose_events,
    frame_metrics,
    joint_angle,
    trunk_tilt,
)

SQUAT = PROFILES["Agachamento (fisioterapia)"]


def _metrics(n=30, fps=10):
    return pd.DataFrame(
        {
            "time_s": np.arange(n) / fps,
            "knee_l": 90.0,
            "knee_r": 90.0,
            "trunk_tilt": 5.0,
            "detected": True,
        }
    )


def test_joint_angle():
    assert joint_angle((0, 1), (0, 0), (1, 0)) == pytest.approx(90)
    assert joint_angle((0, 0), (0, 1), (0, 2)) == pytest.approx(180)
    assert np.isnan(joint_angle((np.nan, 0), (0, 0), (1, 0)))


def test_trunk_tilt():
    upright = trunk_tilt((-1, 0), (1, 0), (-1, 2), (1, 2))
    tilted = trunk_tilt((1, 0), (3, 0), (-1, 2), (1, 2))
    assert upright == pytest.approx(0)
    assert tilted == pytest.approx(45)


def test_frame_metrics_straight_leg():
    k = np.zeros((17, 2))
    k[11], k[13], k[15] = (0, 0), (0, 1), (0, 2)  # quadril, joelho, tornozelo esquerdos
    m = frame_metrics(k, np.ones(17))
    assert m["knee_l"] == pytest.approx(180)


def test_low_confidence_keypoint_is_ignored():
    k = np.zeros((17, 2))
    k[11], k[13], k[15] = (0, 0), (0, 1), (0, 2)
    conf = np.ones(17)
    conf[13] = 0.1
    assert np.isnan(frame_metrics(k, conf)["knee_l"])


def test_clean_sequence_has_no_events():
    assert detect_pose_events(_metrics(), SQUAT) == []


def test_joint_limit_and_asymmetry_detected():
    m = _metrics()
    m.loc[10:19, "knee_l"] = 20.0  # flexão excessiva por 1 s
    events = detect_pose_events(m, SQUAT)
    kinds = {e.kind for e in events}
    assert {"limite_articular", "assimetria"} <= kinds
    limit = next(e for e in events if e.kind == "limite_articular")
    assert limit.severity == 3  # desvio de 35° > 25°


def test_patient_out_of_frame():
    m = _metrics()
    m.loc[5:, ["knee_l", "knee_r", "trunk_tilt"]] = np.nan
    m.loc[5:, "detected"] = False
    assert any(e.kind == "fora_de_quadro" for e in detect_pose_events(m, SQUAT))


def test_fall_detection():
    times = np.arange(20) / 10
    boxes = np.array([[0, 0, 50, 200]] * 10 + [[0, 0, 200, 50]] * 10, dtype=float)
    events = detect_fall(boxes, times)
    assert len(events) == 1
    assert events[0].severity == 3


def test_no_fall_when_always_lying():
    times = np.arange(20) / 10
    boxes = np.array([[0, 0, 200, 50]] * 20, dtype=float)
    assert detect_fall(boxes, times) == []
