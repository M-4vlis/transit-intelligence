from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, date
from hashlib import sha256
import os
from pathlib import Path
import re

from app.modules.mobility.archive.models import ArchiveArtifact, ArchiveVerification
from app.modules.mobility.models import VehiclePosition


_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_component(value: str) -> str:
    cleaned = _SAFE_COMPONENT.sub("_", value).strip("._")
    if not cleaned:
        raise ValueError("archive source cannot produce an empty filesystem component")
    return cleaned


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


class LocalParquetArchiveWriter:
    """Development/local writer. Production retention must use a durable external store."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    @staticmethod
    def _load_pyarrow():
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ModuleNotFoundError as exc:  # pragma: no cover - environment-specific
            raise RuntimeError(
                "Parquet support requires pyarrow; install project archive dependencies"
            ) from exc
        return pa, pq

    def _paths(self, *, source: str, day: date) -> tuple[Path, Path]:
        source_dir = _safe_component(source)
        target_dir = self.root / source_dir / f"{day:%Y}" / f"{day:%m}"
        target_dir.mkdir(parents=True, exist_ok=True)
        final = target_dir / f"{day.isoformat()}.parquet"
        temporary = final.with_suffix(".parquet.tmp")
        return temporary, final

    @staticmethod
    def _schema(pa):
        return pa.schema(
            [
                ("agency_id", pa.string()),
                ("vehicle_id", pa.string()),
                ("route_id", pa.string()),
                ("trip_id", pa.string()),
                ("latitude", pa.float64()),
                ("longitude", pa.float64()),
                ("speed_mps", pa.float32()),
                ("bearing_deg", pa.float32()),
                ("observed_at", pa.timestamp("us", tz="UTC")),
                ("received_at", pa.timestamp("us", tz="UTC")),
                ("source", pa.string()),
                ("quality_status", pa.string()),
                ("quality_score", pa.float32()),
                ("ingest_key", pa.string()),
            ]
        )

    @staticmethod
    def _row(position: VehiclePosition) -> dict[str, object]:
        observed_at = position.observed_at
        received_at = position.received_at
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=UTC)
        return {
            "agency_id": position.agency_id,
            "vehicle_id": position.vehicle_id,
            "route_id": position.route_id,
            "trip_id": position.trip_id,
            "latitude": position.latitude,
            "longitude": position.longitude,
            "speed_mps": position.speed_mps,
            "bearing_deg": position.bearing_deg,
            "observed_at": observed_at.astimezone(UTC),
            "received_at": received_at.astimezone(UTC),
            "source": position.source,
            "quality_status": position.quality_status.value,
            "quality_score": position.quality_score,
            "ingest_key": position.dedupe_key(),
        }

    async def write_day(
        self,
        *,
        source: str,
        day: date,
        batches: AsyncIterator[Sequence[VehiclePosition]],
    ) -> ArchiveArtifact:
        pa, pq = self._load_pyarrow()
        temporary, final = self._paths(source=source, day=day)
        temporary.unlink(missing_ok=True)

        row_count = 0
        writer = pq.ParquetWriter(
            temporary,
            self._schema(pa),
            compression="zstd",
            use_dictionary=True,
            write_statistics=True,
        )
        try:
            async for batch in batches:
                if not batch:
                    continue
                table = pa.Table.from_pylist(
                    [self._row(position) for position in batch],
                    schema=self._schema(pa),
                )
                writer.write_table(table)
                row_count += len(batch)
        except Exception:
            writer.close()
            temporary.unlink(missing_ok=True)
            raise
        else:
            writer.close()

        # Empty archives are still valid Parquet files and are useful as explicit evidence that
        # a source/day was checked. Atomic replace prevents readers from observing partial files.
        os.replace(temporary, final)
        byte_size = final.stat().st_size
        digest = _sha256_file(final)
        return ArchiveArtifact(
            source=source,
            archive_day=day,
            object_uri=final.as_uri(),
            local_path=final,
            row_count=row_count,
            byte_size=byte_size,
            sha256=digest,
        )

    async def verify(self, artifact: ArchiveArtifact) -> ArchiveVerification:
        _, pq = self._load_pyarrow()
        path = artifact.local_path
        if path is None:
            raise ValueError("local parquet verifier requires artifact.local_path")
        path = path.resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("archive path is outside configured root") from exc

        parquet = pq.ParquetFile(path)
        row_count = int(parquet.metadata.num_rows)
        byte_size = path.stat().st_size
        digest = _sha256_file(path)
        valid = (
            row_count == artifact.row_count
            and byte_size == artifact.byte_size
            and digest == artifact.sha256
        )
        return ArchiveVerification(
            valid=valid,
            row_count=row_count,
            byte_size=byte_size,
            sha256=digest,
            detail="" if valid else "Parquet metadata/hash mismatch",
        )


class S3CompatibleParquetArchiveWriter:
    """Durable writer for OCI Object Storage, Cloudflare R2, or another S3-compatible store."""

    def __init__(
        self,
        *,
        client,
        bucket: str,
        prefix: str,
        spool_root: Path,
    ) -> None:
        if not bucket.strip():
            raise ValueError("S3 archive bucket is required")
        self.client = client
        self.bucket = bucket.strip()
        self.prefix = prefix.strip("/")
        self.local = LocalParquetArchiveWriter(spool_root)

    def _object_key(self, *, source: str, day: date) -> str:
        parts = [
            self.prefix,
            _safe_component(source),
            f"{day:%Y}",
            f"{day:%m}",
            f"{day.isoformat()}.parquet",
        ]
        return "/".join(part for part in parts if part)

    async def write_day(
        self,
        *,
        source: str,
        day: date,
        batches: AsyncIterator[Sequence[VehiclePosition]],
    ) -> ArchiveArtifact:
        import asyncio

        local_artifact = await self.local.write_day(source=source, day=day, batches=batches)
        local_verification = await self.local.verify(local_artifact)
        if not local_verification.valid:
            raise RuntimeError("local Parquet failed verification before remote upload")
        path = local_artifact.local_path
        if path is None:
            raise RuntimeError("local Parquet artifact has no spool path")

        key = self._object_key(source=source, day=day)
        extra = {
            "ContentType": "application/vnd.apache.parquet",
            "Metadata": {
                "sha256": local_artifact.sha256,
                "row-count": str(local_artifact.row_count),
            },
        }
        try:
            await asyncio.to_thread(
                self.client.upload_file,
                str(path),
                self.bucket,
                key,
                ExtraArgs=extra,
            )
        except Exception:
            path.unlink(missing_ok=True)
            raise

        return ArchiveArtifact(
            source=source,
            archive_day=day,
            object_uri=f"s3://{self.bucket}/{key}",
            local_path=path,
            row_count=local_artifact.row_count,
            byte_size=local_artifact.byte_size,
            sha256=local_artifact.sha256,
        )

    def _remote_hash_and_size(self, key: str) -> tuple[str, int, dict[str, str]]:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        body = response["Body"]
        digest = sha256()
        total = 0
        try:
            for chunk in body.iter_chunks(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                digest.update(chunk)
                total += len(chunk)
        finally:
            body.close()
        metadata = {str(k).lower(): str(v) for k, v in response.get("Metadata", {}).items()}
        return digest.hexdigest(), total, metadata

    async def verify(self, artifact: ArchiveArtifact) -> ArchiveVerification:
        import asyncio

        prefix = f"s3://{self.bucket}/"
        if not artifact.object_uri.startswith(prefix):
            raise ValueError("artifact does not belong to configured S3 bucket")
        key = artifact.object_uri[len(prefix) :]
        digest, byte_size, metadata = await asyncio.to_thread(self._remote_hash_and_size, key)
        metadata_hash = metadata.get("sha256")
        metadata_rows = metadata.get("row-count")
        metadata_valid = (
            metadata_hash in {None, artifact.sha256}
            and metadata_rows in {None, str(artifact.row_count)}
        )
        valid = digest == artifact.sha256 and byte_size == artifact.byte_size and metadata_valid
        if valid and artifact.local_path is not None:
            artifact.local_path.unlink(missing_ok=True)
        return ArchiveVerification(
            valid=valid,
            row_count=artifact.row_count,
            byte_size=byte_size,
            sha256=digest,
            detail="" if valid else "remote S3-compatible object hash/metadata mismatch",
        )


def create_s3_compatible_client(
    *,
    endpoint_url: str,
    region_name: str,
    access_key_id: str,
    secret_access_key: str,
):
    import boto3
    from botocore.config import Config

    if not endpoint_url.startswith("https://"):
        raise ValueError("S3-compatible archive endpoint must use HTTPS")
    if not all((region_name, access_key_id, secret_access_key)):
        raise ValueError("S3-compatible archive credentials/region are incomplete")
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region_name,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            # Recent botocore releases calculate optional request checksums by
            # default. That turns PutObject bodies into an aws-chunked stream,
            # which is not accepted by every S3-compatible endpoint (including
            # the OCI endpoint used by production). Keep modeled/required
            # checksums while relying on our full-object SHA-256 verification.
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )
