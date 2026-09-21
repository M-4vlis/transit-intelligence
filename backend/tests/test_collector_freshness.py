from scripts.check_collector_freshness import build_report, parse_last_success


def test_collector_freshness_parses_source_and_passes_recent_success() -> None:
    metrics = (
        '# HELP transit_ingestion_last_success_unixtime Last success\n'
        'transit_ingestion_last_success_unixtime{source="other"} 10\n'
        'transit_ingestion_last_success_unixtime{source="rio-smtr-gps"} 1000\n'
    )

    last_success = parse_last_success(metrics, source="rio-smtr-gps")
    report = build_report(
        now_unix=1120,
        last_success_unix=last_success,
        maximum_age_seconds=300,
    )

    assert last_success == 1000
    assert report["status"] == "passed"
    assert report["last_success_age_seconds"] == 120


def test_collector_freshness_fails_closed_for_missing_or_old_metric() -> None:
    assert parse_last_success("# no sample", source="rio-smtr-gps") is None
    missing = build_report(
        now_unix=1000,
        last_success_unix=None,
        maximum_age_seconds=300,
    )
    old = build_report(
        now_unix=1400,
        last_success_unix=1000,
        maximum_age_seconds=300,
    )

    assert missing["status"] == "failed"
    assert old["status"] == "failed"
