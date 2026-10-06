import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from medihub.cli import main
from medihub.domain import (
    Coding,
    DeviceReference,
    EventOrigin,
    ObservationEvent,
    SourceProvenance,
    TimeQuality,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_MAPPING = REPOSITORY_ROOT / "config" / "synthetic-mapping.example.toml"
OBSERVED_AT = datetime(2026, 10, 7, 8, 0, tzinfo=UTC)


def make_synthetic_event(*, metric_code: str = "simulated-scalar-reading") -> ObservationEvent:
    return ObservationEvent(
        event_id=uuid4(),
        site_id="synthetic-site",
        device=DeviceReference(
            device_id="sim-device-001",
            manufacturer="MediHub Synthetic",
            model="scalar-simulator-v1",
            firmware_version="1.0",
        ),
        metric=Coding(
            system="https://example.invalid/medihub/synthetic-metrics",
            code=metric_code,
        ),
        value=41.25,
        source_unit=Coding(system="http://unitsofmeasure.org", code="1"),
        observed_at=OBSERVED_AT,
        received_at=OBSERVED_AT,
        time_quality=TimeQuality.DEVICE_SYNCHRONIZED,
        provenance=SourceProvenance(
            adapter_id="medihub.synthetic-device",
            adapter_version="0.2.0",
        ),
        origin=EventOrigin.SYNTHETIC,
    )


def test_map_synthetic_cli_outputs_versioned_mapped_ndjson(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "synthetic-events.ndjson"
    input_path.write_text(make_synthetic_event().model_dump_json() + "\n", encoding="utf-8")

    exit_code = main(["map-synthetic", str(input_path), "--mapping", str(SYNTHETIC_MAPPING)])
    output = capsys.readouterr().out
    result = json.loads(output)

    assert exit_code == 0
    assert result["origin"] == "synthetic"
    assert result["mapping_set_id"] == "synthetic-scalar-demo"
    assert result["mapping_version"] == "1.0.0"
    assert result["source_value"] == "41.25"
    assert result["normalized_value"] == "41.25"
    assert result["normalized_metric"]["code"] == "mapped-synthetic-scalar"
    assert "patient" not in output.lower()
    assert "source_message_id" not in output


def test_map_synthetic_cli_emits_no_partial_output_on_mapping_failure(
    tmp_path: Path,
    capsys,
) -> None:
    input_path = tmp_path / "partially-mappable.ndjson"
    events = [make_synthetic_event(), make_synthetic_event(metric_code="synthetic-unknown-code")]
    input_path.write_text(
        "".join(event.model_dump_json() + "\n" for event in events),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as error:
        main(["map-synthetic", str(input_path), "--mapping", str(SYNTHETIC_MAPPING)])
    captured = capsys.readouterr()

    assert error.value.code == 2
    assert captured.out == ""
    assert "mapping_entry_not_found" in captured.err
    assert "41.25" not in captured.err
    assert str(input_path) not in captured.err
