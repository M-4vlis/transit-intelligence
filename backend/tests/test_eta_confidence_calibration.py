from datetime import UTC, datetime, timedelta

from scripts.calibrate_eta_confidence import build_calibration_report


def _cohort(anchor: datetime, *, observations_per_band: int = 10) -> dict:
    observations = []
    errors = {"high": -10, "medium": -30, "low": -60}
    scores = {"high": 95, "medium": 82, "low": 60}
    for band in ("high", "medium", "low"):
        for index in range(observations_per_band):
            signed_error = errors[band]
            observations.append(
                {
                    "score": scores[band],
                    "candidate_band": band,
                    "signed_error_seconds": signed_error,
                    "absolute_error_seconds": abs(signed_error),
                    "predicted_eta_seconds": 120,
                    "actual_eta_seconds": 120 - signed_error,
                    "eta_method": (
                        "vehicle_recent_speed"
                        if index % 2
                        else "historical_segment_time_band"
                    ),
                    "match_method": "exact_trip",
                    "route_id": f"route-{index}",
                    "spatial_cell": f"cell-{index % 4}",
                }
            )
    return {
        "evaluation_schema_version": 2,
        "calibration_observation_schema_version": 2,
        "parameters": {
            "effective_anchor_at": anchor.isoformat(),
            "sampling_method": "deterministic_vehicle_hash_v1",
        },
        "calibration_observations": observations,
    }


def test_calibrator_fails_closed_without_independent_days() -> None:
    report = build_calibration_report([], generated_at=datetime(2026, 9, 13, tzinfo=UTC))

    assert report["status"] == "insufficient_data"
    assert report["promotion_authorized"] is False
    assert report["source"]["eligible_cohort_count"] == 0
    assert report["calibration_candidate"] is None
    assert report["gates"] == {
        "seven_independent_days": False,
        "all_dayparts": False,
        "minimum_50_outcomes_per_band": False,
        "maximum_single_route_share_20_percent": True,
        "minimum_10_routes_per_band": False,
        "maximum_single_route_share_20_percent_per_band": True,
        "minimum_3_spatial_cells_per_band": False,
        "maximum_single_spatial_cell_share_50_percent_per_band": True,
        "maximum_single_eta_method_share_95_percent_per_band": True,
    }


def test_calibrator_uses_last_two_days_as_heldout_and_never_auto_promotes() -> None:
    start = datetime(2026, 9, 1, 7, tzinfo=UTC)
    utc_hours = (10, 15, 20, 3, 10, 15, 20)
    reports = [
        _cohort(
            (start + timedelta(days=index)).replace(hour=hour),
        )
        for index, hour in enumerate(utc_hours)
    ]

    report = build_calibration_report(
        reports, generated_at=datetime(2026, 9, 8, tzinfo=UTC)
    )

    assert report["status"] == "candidate_for_manual_review"
    assert report["promotion_authorized"] is False
    assert all(report["gates"].values())
    assert report["coverage"]["independent_day_count"] == 7
    assert report["coverage"]["band_outcomes"] == {
        "high": 70,
        "medium": 70,
        "low": 70,
    }
    candidate = report["calibration_candidate"]
    assert len(candidate["training_dates"]) == 5
    assert len(candidate["heldout_dates"]) == 2
    assert candidate["heldout_monotonic_mae"] is True
    assert candidate["heldout_interval_coverage"] == {
        "high": 1,
        "medium": 1,
        "low": 1,
    }
    assert candidate["proposed_interval_offsets_seconds"]["high"] == {
        "lower_seconds": 10,
        "upper_seconds": 10,
    }
    high_diversity = report["coverage"]["diversity_by_band"]["high"]
    assert high_diversity["route_count"] == 10
    assert high_diversity["spatial_cell_count"] == 4
    assert high_diversity["maximum_single_route_share"] == 0.1
    assert high_diversity["maximum_single_spatial_cell_share"] == 0.3


def test_calibrator_ignores_legacy_or_non_deterministic_reports() -> None:
    anchor = datetime(2026, 9, 1, 10, tzinfo=UTC)
    legacy = _cohort(anchor)
    legacy["evaluation_schema_version"] = 1
    biased = _cohort(anchor + timedelta(hours=1))
    biased["parameters"]["sampling_method"] = "lexicographic_v0"

    report = build_calibration_report(
        [legacy, biased], generated_at=datetime(2026, 9, 1, 12, tzinfo=UTC)
    )

    assert report["source"]["eligible_cohort_count"] == 0
    assert report["coverage"]["outcome_count"] == 0


def test_calibrator_rejects_band_concentration() -> None:
    start = datetime(2026, 9, 1, 10, tzinfo=UTC)
    reports = [_cohort(start + timedelta(days=index)) for index in range(7)]
    for report in reports:
        for observation in report["calibration_observations"]:
            if observation["candidate_band"] == "high":
                observation["eta_method"] = "vehicle_recent_speed"
                observation["spatial_cell"] = "single-cell"

    calibration = build_calibration_report(
        reports, generated_at=datetime(2026, 9, 8, tzinfo=UTC)
    )

    assert calibration["status"] == "insufficient_data"
    assert (
        calibration["gates"][
            "maximum_single_spatial_cell_share_50_percent_per_band"
        ]
        is False
    )
    assert (
        calibration["gates"][
            "maximum_single_eta_method_share_95_percent_per_band"
        ]
        is False
    )
    high = calibration["coverage"]["diversity_by_band"]["high"]
    assert high["maximum_single_spatial_cell_share"] == 1
    assert high["maximum_single_eta_method_share"] == 1
