from pathlib import Path

import pytest

from medihub.application.synthetic_mapping import (
    SyntheticMappingConfigError,
    load_synthetic_mapping,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_MAPPING = REPOSITORY_ROOT / "config" / "synthetic-mapping.example.toml"


def test_example_mapping_loads_with_an_explicit_synthetic_only_scope() -> None:
    mapping = load_synthetic_mapping(EXAMPLE_MAPPING)

    assert mapping.scope == "synthetic_only"
    assert mapping.mapping_set_id == "synthetic-scalar-demo"
    assert mapping.version == "1.0.0"
    assert len(mapping.entries) == 1


def test_loader_rejects_live_scope_and_unknown_fields_without_echoing_values(
    tmp_path: Path,
) -> None:
    secret = "SYNTHETIC-NOT-A-REAL-CREDENTIAL"
    invalid_scope_path = tmp_path / "live-scope.toml"
    invalid_scope_path.write_text(
        EXAMPLE_MAPPING.read_text(encoding="utf-8").replace(
            'scope = "synthetic_only"', 'scope = "production"'
        ),
        encoding="utf-8",
    )
    unknown_field_path = tmp_path / "unknown-key.toml"
    example_content = EXAMPLE_MAPPING.read_text(encoding="utf-8")
    unknown_field_path.write_text(
        f'api_token = "{secret}"\n' + example_content,
        encoding="utf-8",
    )

    for path in (invalid_scope_path, unknown_field_path):
        with pytest.raises(SyntheticMappingConfigError) as error:
            load_synthetic_mapping(path)
        assert error.value.code == "invalid_mapping_schema"
        assert secret not in str(error.value)
        assert "api_token" not in str(error.value)


def test_loader_reports_safe_file_errors(tmp_path: Path) -> None:
    with pytest.raises(SyntheticMappingConfigError) as error:
        load_synthetic_mapping(tmp_path / "missing-mapping.toml")

    assert error.value.code == "mapping_file_unreadable"
