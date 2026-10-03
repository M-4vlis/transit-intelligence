from scripts.plan_capacity_guard import build_plan


def test_capacity_guard_observes_healthy_host() -> None:
    plan = build_plan(
        root_used_percent=47,
        object_storage_bytes=10_700_000_000,
        object_storage_status="current",
        paused_by_guard=False,
    )
    assert plan["reason"] == "within_capacity"
    assert plan["actions"] == {
        "pause_collector": False,
        "attempt_verified_retention": False,
        "resume_collector": False,
    }


def test_capacity_guard_triggers_only_verified_retention_at_warning() -> None:
    plan = build_plan(
        root_used_percent=82,
        object_storage_bytes=12_000_000_000,
        object_storage_status="current",
        paused_by_guard=False,
    )
    assert plan["reason"] == "root_filesystem_warning"
    assert plan["actions"]["attempt_verified_retention"] is True
    assert plan["actions"]["pause_collector"] is False


def test_capacity_guard_pauses_collector_at_critical_disk() -> None:
    plan = build_plan(
        root_used_percent=91,
        object_storage_bytes=12_000_000_000,
        object_storage_status="current",
        paused_by_guard=False,
    )
    assert plan["reason"] == "root_filesystem_critical"
    assert plan["actions"]["pause_collector"] is True
    assert plan["actions"]["attempt_verified_retention"] is True


def test_capacity_guard_fails_closed_when_storage_measurement_is_missing() -> None:
    plan = build_plan(
        root_used_percent=91,
        object_storage_bytes=None,
        object_storage_status="stale",
        paused_by_guard=False,
    )
    assert plan["actions"]["pause_collector"] is True
    assert plan["actions"]["attempt_verified_retention"] is False


def test_capacity_guard_blocks_before_object_storage_free_tier() -> None:
    plan = build_plan(
        root_used_percent=50,
        object_storage_bytes=18_000_000_000,
        object_storage_status="current",
        paused_by_guard=False,
    )
    assert plan["reason"] == "object_storage_hard_guard"
    assert plan["actions"]["pause_collector"] is True
    assert plan["actions"]["attempt_verified_retention"] is False


def test_capacity_guard_resumes_only_its_own_pause_with_hysteresis() -> None:
    plan = build_plan(
        root_used_percent=70,
        object_storage_bytes=12_000_000_000,
        object_storage_status="current",
        paused_by_guard=True,
    )
    assert plan["reason"] == "capacity_recovered"
    assert plan["actions"]["resume_collector"] is True
