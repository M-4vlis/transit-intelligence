from __future__ import annotations

import csv
import hashlib
import stat
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile, ZipInfo

from app.modules.mobility.gtfs.models import GtfsMemberManifest, GtfsSnapshotManifest


class GtfsValidationError(ValueError):
    pass


_REQUIRED_COLUMNS: dict[str, set[str]] = {
    "stops.txt": {"stop_id", "stop_name", "stop_lat", "stop_lon"},
    "routes.txt": {"route_id", "route_type"},
    "trips.txt": {"route_id", "service_id", "trip_id"},
    "stop_times.txt": {
        "trip_id",
        "arrival_time",
        "departure_time",
        "stop_id",
        "stop_sequence",
    },
    "calendar.txt": {
        "service_id",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "start_date",
        "end_date",
    },
    "calendar_dates.txt": {"service_id", "date", "exception_type"},
}
_CORE_FILES = {"stops.txt", "routes.txt", "trips.txt", "stop_times.txt"}
_CALENDAR_FILES = {"calendar.txt", "calendar_dates.txt"}
_MAX_HEADER_BYTES = 128 * 1024
_READ_CHUNK_BYTES = 64 * 1024
_MAX_COMPRESSION_RATIO = 250


def _safe_member_name(info: ZipInfo) -> str:
    raw_name = info.filename
    normalized = raw_name.replace("\\", "/")
    path = PurePosixPath(normalized)
    unix_mode = info.external_attr >> 16

    if info.is_dir():
        raise GtfsValidationError("GTFS archive must not contain directories")
    if stat.S_ISLNK(unix_mode):
        raise GtfsValidationError("GTFS archive must not contain symbolic links")
    if info.flag_bits & 0x1:
        raise GtfsValidationError("GTFS archive must not contain encrypted files")
    if (
        not normalized
        or path.is_absolute()
        or len(path.parts) != 1
        or ".." in path.parts
        or ":" in normalized
        or not normalized.casefold().endswith(".txt")
    ):
        raise GtfsValidationError(f"unsafe or unsupported GTFS member: {raw_name!r}")
    return normalized


def _read_member_and_header(
    archive: ZipFile,
    info: ZipInfo,
    *,
    remaining_bytes: int,
) -> tuple[int, tuple[str, ...]]:
    actual_bytes = 0
    first_line = bytearray()
    line_complete = False

    try:
        with archive.open(info, "r") as source:
            while chunk := source.read(_READ_CHUNK_BYTES):
                actual_bytes += len(chunk)
                if actual_bytes > remaining_bytes:
                    raise GtfsValidationError("GTFS archive exceeded uncompressed size limit")

                if not line_complete:
                    newline_at = chunk.find(b"\n")
                    if newline_at >= 0:
                        first_line.extend(chunk[:newline_at])
                        line_complete = True
                    else:
                        first_line.extend(chunk)
                    if len(first_line) > _MAX_HEADER_BYTES:
                        raise GtfsValidationError(
                            f"GTFS header exceeded size limit in {info.filename}"
                        )
    except (BadZipFile, RuntimeError, OSError) as exc:
        raise GtfsValidationError(f"unable to read GTFS member {info.filename}") from exc

    if actual_bytes != info.file_size:
        raise GtfsValidationError(f"GTFS member size mismatch in {info.filename}")
    if not first_line:
        raise GtfsValidationError(f"GTFS member is empty: {info.filename}")

    try:
        decoded = bytes(first_line).decode("utf-8-sig").rstrip("\r")
        columns = tuple(column.strip() for column in next(csv.reader([decoded])))
    except (UnicodeDecodeError, csv.Error, StopIteration) as exc:
        raise GtfsValidationError(f"invalid CSV header in {info.filename}") from exc

    if not columns or any(not column for column in columns):
        raise GtfsValidationError(f"invalid CSV header in {info.filename}")
    if len({column.casefold() for column in columns}) != len(columns):
        raise GtfsValidationError(f"duplicate CSV columns in {info.filename}")
    return actual_bytes, columns


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_gtfs_snapshot(
    path: Path,
    *,
    source_url: str,
    fetched_at: datetime | None = None,
    expected_sha256: str | None = None,
    max_compressed_bytes: int = 64 * 1024 * 1024,
    max_uncompressed_bytes: int = 512 * 1024 * 1024,
    max_members: int = 128,
) -> GtfsSnapshotManifest:
    try:
        compressed_bytes = path.stat().st_size
    except OSError as exc:
        raise GtfsValidationError("GTFS snapshot is not readable") from exc
    if compressed_bytes <= 0 or compressed_bytes > max_compressed_bytes:
        raise GtfsValidationError("GTFS snapshot exceeded compressed size limit")

    snapshot_id = _sha256(path)
    if expected_sha256 is not None and snapshot_id != expected_sha256.lower():
        raise GtfsValidationError("GTFS snapshot SHA-256 mismatch")

    member_manifests: list[GtfsMemberManifest] = []
    seen_names: set[str] = set()
    total_uncompressed = 0

    try:
        with ZipFile(path, "r") as archive:
            entries = archive.infolist()
            if not entries or len(entries) > max_members:
                raise GtfsValidationError("GTFS archive member count is outside limits")

            for info in entries:
                filename = _safe_member_name(info)
                canonical_name = filename.casefold()
                if canonical_name in seen_names:
                    raise GtfsValidationError(f"duplicate GTFS member: {filename}")
                seen_names.add(canonical_name)

                if info.file_size > max_uncompressed_bytes - total_uncompressed:
                    raise GtfsValidationError("GTFS archive exceeded uncompressed size limit")
                if info.file_size > 0:
                    if info.compress_size <= 0:
                        raise GtfsValidationError(f"invalid compressed size in {filename}")
                    if info.file_size / info.compress_size > _MAX_COMPRESSION_RATIO:
                        raise GtfsValidationError(f"suspicious compression ratio in {filename}")

                actual_bytes, columns = _read_member_and_header(
                    archive,
                    info,
                    remaining_bytes=max_uncompressed_bytes - total_uncompressed,
                )
                total_uncompressed += actual_bytes
                member_manifests.append(
                    GtfsMemberManifest(
                        filename=filename,
                        compressed_bytes=info.compress_size,
                        uncompressed_bytes=actual_bytes,
                        crc32=f"{info.CRC:08x}",
                        columns=columns,
                    )
                )
    except BadZipFile as exc:
        raise GtfsValidationError("GTFS snapshot is not a valid ZIP archive") from exc

    missing_core = sorted(_CORE_FILES - seen_names)
    if missing_core:
        raise GtfsValidationError(f"GTFS archive is missing: {', '.join(missing_core)}")
    calendar_files = tuple(sorted(_CALENDAR_FILES & seen_names))
    if not calendar_files:
        raise GtfsValidationError("GTFS archive requires calendar.txt or calendar_dates.txt")

    by_name = {member.filename.casefold(): member for member in member_manifests}
    for filename in sorted(_CORE_FILES | set(calendar_files)):
        required = _REQUIRED_COLUMNS[filename]
        observed = {column.casefold() for column in by_name[filename].columns}
        missing_columns = sorted(required - observed)
        if missing_columns:
            raise GtfsValidationError(
                f"{filename} is missing columns: {', '.join(missing_columns)}"
            )

    observed_at = fetched_at or datetime.now(UTC)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise GtfsValidationError("fetched_at must include a timezone")

    return GtfsSnapshotManifest(
        snapshot_id=snapshot_id,
        source_url=source_url,
        fetched_at=observed_at.astimezone(UTC),
        compressed_bytes=compressed_bytes,
        uncompressed_bytes=total_uncompressed,
        member_count=len(member_manifests),
        service_calendar_files=calendar_files,
        files=tuple(sorted(member_manifests, key=lambda member: member.filename.casefold())),
    )
