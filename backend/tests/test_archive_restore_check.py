import pytest

from scripts.archive_restore_check import _object_key


def test_object_key_is_extracted_from_configured_bucket():
    assert _object_key(
        "s3://transit-history/archive/rio/2026/09/01.parquet",
        bucket="transit-history",
    ) == "archive/rio/2026/09/01.parquet"


def test_object_key_rejects_other_bucket():
    with pytest.raises(ValueError):
        _object_key("s3://other/archive.parquet", bucket="transit-history")


def test_object_key_rejects_traversal():
    with pytest.raises(ValueError):
        _object_key("s3://transit-history/archive/../secret", bucket="transit-history")
