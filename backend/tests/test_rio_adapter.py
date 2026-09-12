from datetime import UTC, datetime

import httpx
import pytest

from app.modules.mobility.adapters.base import TransitSourceUnavailable
from app.modules.mobility.adapters.rio import RIO_AGENCY, RioRealtimeAdapter, RioVehiclePositionRaw
from app.modules.mobility.sources.http import ResilientJsonClient, RetryPolicy


def current_contract_record() -> dict[str, object]:
    return {
        "id_veiculo": "A1",
        "servico": "457",
        "latitude": -22.9,
        "longitude": -43.2,
        "datetime": "2026-09-03T12:00:00Z",
    }


def test_rio_raw_normalizes_legacy_field_names() -> None:
    raw = RioVehiclePositionRaw.model_validate(
        {
            "ordem": "D12345",
            "linha": "457",
            "trip_id": "T1",
            "shape_id": "SH1",
            "latitude": -22.9,
            "longitude": -43.2,
            "velocidade": 36,
            "direcao": 360,
            "datahora": "2026-09-01 10:00:00",
        }
    )
    canonical = raw.to_canonical()

    assert canonical.agency_id == RIO_AGENCY
    assert canonical.vehicle_id == "D12345"
    assert canonical.route_id == "457"
    assert canonical.trip_id == "T1"
    assert canonical.shape_id == "SH1"
    assert canonical.speed_mps == pytest.approx(10.0)
    assert canonical.bearing_deg == 0
    assert canonical.observed_at.tzinfo is not None
    assert canonical.observed_at.astimezone(UTC).hour == 13


@pytest.mark.asyncio
async def test_rio_adapter_quarantines_bad_record_and_keeps_good_record() -> None:
    payload = {
        "veiculos": [
            {
                "id_veiculo": "A1",
                "servico": "457",
                "latitude": -22.9,
                "longitude": -43.2,
                "timestamp_gps": "2026-09-01T13:00:00Z",
            },
            {"id_veiculo": "BAD"},
        ]
    }

    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = RioRealtimeAdapter(
            client=ResilientJsonClient(client),
            url="https://example.invalid/gps",
        )
        batch = await adapter.fetch_vehicle_positions()

    assert len(batch.positions) == 1
    assert len(batch.rejected) == 1
    assert batch.rejected[0].reason_code == "record_schema_invalid"


@pytest.mark.asyncio
async def test_rio_adapter_uses_incremental_utc_windows_with_overlap() -> None:
    requested: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(dict(request.url.params))
        return httpx.Response(200, json=[current_contract_record()])

    clock_values = iter(
        [
            datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
            datetime(2026, 9, 3, 12, 1, tzinfo=UTC),
        ]
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = RioRealtimeAdapter(
            client=ResilientJsonClient(client),
            url="https://dados.mobilidade.rio/gps/sppo",
            initial_window_seconds=120,
            overlap_seconds=30,
            max_window_seconds=300,
            clock=lambda: next(clock_values),
        )
        first = await adapter.fetch_vehicle_positions()
        await adapter.acknowledge_batch(first)
        await adapter.fetch_vehicle_positions()

    assert requested == [
        {
            "dataInicial": "2026-09-03 11:58:00",
            "dataFinal": "2026-09-03 12:00:00",
        },
        {
            "dataInicial": "2026-09-03 11:59:30",
            "dataFinal": "2026-09-03 12:01:00",
        },
    ]


@pytest.mark.asyncio
async def test_rio_adapter_caps_recovery_window_after_long_gap() -> None:
    requested: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(dict(request.url.params))
        return httpx.Response(200, json=[current_contract_record()])

    clock_values = iter(
        [
            datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
            datetime(2026, 9, 3, 12, 20, tzinfo=UTC),
        ]
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = RioRealtimeAdapter(
            client=ResilientJsonClient(client),
            url="https://dados.mobilidade.rio/gps/sppo",
            clock=lambda: next(clock_values),
        )
        first = await adapter.fetch_vehicle_positions()
        await adapter.acknowledge_batch(first)
        await adapter.fetch_vehicle_positions()

    assert requested[1]["dataInicial"] == "2026-09-03 12:15:00"
    assert requested[1]["dataFinal"] == "2026-09-03 12:20:00"


@pytest.mark.asyncio
async def test_rio_adapter_does_not_advance_cursor_after_failure() -> None:
    requested: list[dict[str, str]] = []
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        requested.append(dict(request.url.params))
        if calls == 1:
            return httpx.Response(500, json={"error": "temporary"})
        return httpx.Response(200, json=[current_contract_record()])

    clock_values = iter(
        [
            datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
            datetime(2026, 9, 3, 12, 1, tzinfo=UTC),
        ]
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = RioRealtimeAdapter(
            client=ResilientJsonClient(client, policy=RetryPolicy(max_attempts=1)),
            url="https://dados.mobilidade.rio/gps/sppo",
            clock=lambda: next(clock_values),
        )
        with pytest.raises(TransitSourceUnavailable):
            await adapter.fetch_vehicle_positions()
        await adapter.fetch_vehicle_positions()

    assert requested[1]["dataInicial"] == "2026-09-03 11:59:00"


@pytest.mark.asyncio
async def test_rio_adapter_replays_exact_window_until_downstream_acknowledgement() -> None:
    requested: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(dict(request.url.params))
        return httpx.Response(200, json=[current_contract_record()])

    clock_values = iter(
        [
            datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
            datetime(2026, 9, 3, 12, 1, tzinfo=UTC),
        ]
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = RioRealtimeAdapter(
            client=ResilientJsonClient(client),
            url="https://dados.mobilidade.rio/gps/sppo",
            clock=lambda: next(clock_values),
        )
        failed_downstream_batch = await adapter.fetch_vehicle_positions()
        replayed_batch = await adapter.fetch_vehicle_positions()
        await adapter.acknowledge_batch(replayed_batch)
        await adapter.fetch_vehicle_positions()

    assert replayed_batch.fetched_at == failed_downstream_batch.fetched_at
    assert requested == [
        {
            "dataInicial": "2026-09-03 11:58:00",
            "dataFinal": "2026-09-03 12:00:00",
        },
        {
            "dataInicial": "2026-09-03 11:58:00",
            "dataFinal": "2026-09-03 12:00:00",
        },
        {
            "dataInicial": "2026-09-03 11:59:30",
            "dataFinal": "2026-09-03 12:01:00",
        },
    ]


@pytest.mark.asyncio
async def test_rio_adapter_rejects_mismatched_acknowledgement() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=[current_contract_record()])
    )
    async with httpx.AsyncClient(transport=transport) as client:
        adapter = RioRealtimeAdapter(
            client=ResilientJsonClient(client),
            url="https://dados.mobilidade.rio/gps/sppo",
            clock=lambda: datetime(2026, 9, 3, 12, 0, tzinfo=UTC),
        )
        batch = await adapter.fetch_vehicle_positions()
        mismatched = batch.model_copy(
            update={"fetched_at": datetime(2026, 9, 3, 12, 1, tzinfo=UTC)}
        )

        with pytest.raises(RuntimeError, match="does not match"):
            await adapter.acknowledge_batch(mismatched)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"initial_window_seconds": 0}, "initial_window_seconds"),
        ({"overlap_seconds": -1}, "overlap_seconds"),
        ({"max_window_seconds": 0}, "max_window_seconds"),
        (
            {"initial_window_seconds": 301, "max_window_seconds": 300},
            "cannot exceed",
        ),
        ({"overlap_seconds": 300, "max_window_seconds": 300}, "must be smaller"),
    ],
)
def test_rio_adapter_rejects_unsafe_window_configuration(
    kwargs: dict[str, float], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        RioRealtimeAdapter(
            client=object(),  # type: ignore[arg-type]
            url="https://dados.mobilidade.rio/gps/sppo",
            **kwargs,
        )


def test_legacy_columnar_payload_is_supported() -> None:
    payload = {
        "COLUMNS": ["DATAHORA", "ORDEM", "LINHA", "LATITUDE", "LONGITUDE", "VELOCIDADE"],
        "DATA": [["09-01-2026 10:00:00", "D12345", "457", -22.9, -43.2, 18]],
    }
    records = RioRealtimeAdapter._extract_records(payload)
    raw = RioVehiclePositionRaw.model_validate(records[0])
    assert raw.id_veiculo == "D12345"
    assert raw.servico == "457"
    assert raw.velocidade == 18


def test_documented_current_contract_fixture_is_supported() -> None:
    import json
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "rio_gps_current.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    records = RioRealtimeAdapter._extract_records(payload)
    positions = [RioVehiclePositionRaw.model_validate(record).to_canonical() for record in records]

    assert len(positions) == 2
    assert positions[0].vehicle_id == "D12345"
    assert positions[0].route_id == "457"
    assert positions[0].speed_mps == pytest.approx(7.5)
    assert positions[0].observed_at.astimezone(UTC).hour == 13


def test_contract_fingerprint_is_stable_for_field_order() -> None:
    left = [{"id_veiculo": "A", "servico": "1", "latitude": 1, "longitude": 2}]
    right = [{"longitude": 2, "latitude": 1, "servico": "1", "id_veiculo": "A"}]

    fp_left, fields_left = RioRealtimeAdapter._contract_metadata(left)
    fp_right, fields_right = RioRealtimeAdapter._contract_metadata(right)

    assert fp_left == fp_right
    assert fields_left == fields_right
    assert fields_left == ["id_veiculo", "latitude", "longitude", "servico"]


def test_rio_error_envelope_is_not_treated_as_records() -> None:
    from app.modules.mobility.adapters.base import TransitSourceUnavailable

    payload = {
        "RetornoOK": False,
        "DescricaoErro": "O intervalo entre as datas não pode ser maior do que uma hora",
    }
    with pytest.raises(TransitSourceUnavailable, match="error envelope"):
        RioRealtimeAdapter._extract_records(payload)


def test_upstream_legacy_sppo_contract_fields_are_supported() -> None:
    raw = RioVehiclePositionRaw.model_validate(
        {
            "ordem": "D76543",
            "linha": "483",
            "latitude": -22.904,
            "longitude": -43.191,
            "datahora": "2026-09-01 12:00:00",
            "velocidade": 18.0,
            "datahoraenvio": "2026-09-01 12:00:02",
            "datahoraservidor": "2026-09-01 12:00:03",
        }
    )
    position = raw.to_canonical()
    assert position.vehicle_id == "D76543"
    assert position.route_id == "483"
    assert position.speed_mps == pytest.approx(5.0)


def test_rio_identifiers_tolerate_numeric_type_changes_and_epoch_milliseconds() -> None:
    raw = RioVehiclePositionRaw.model_validate(
        {
            "id_veiculo": 12345,
            "servico": 457.0,
            "latitude": "-22.9",
            "longitude": "-43.2",
            "velocidade_instantanea": -1,
            "direcao": 999,
            "timestamp": 1788267600000,
        }
    )
    position = raw.to_canonical()
    assert position.vehicle_id == "12345"
    assert position.route_id == "457"
    assert position.speed_mps is None
    assert position.bearing_deg is None
    assert position.observed_at.tzinfo is not None
