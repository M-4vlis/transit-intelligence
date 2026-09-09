import pytest

from app.workers.rio_ingestion import remaining_poll_delay


def test_poll_delay_is_anchored_to_cycle_start():
    assert remaining_poll_delay(elapsed_seconds=2.5, poll_interval_seconds=30) == pytest.approx(27.5)


def test_slow_cycle_does_not_add_extra_interval():
    assert remaining_poll_delay(elapsed_seconds=35, poll_interval_seconds=30) == 0


def test_negative_elapsed_is_defensive():
    assert remaining_poll_delay(elapsed_seconds=-1, poll_interval_seconds=30) == 30


def test_poll_interval_must_be_positive():
    with pytest.raises(ValueError):
        remaining_poll_delay(elapsed_seconds=1, poll_interval_seconds=0)
