import pytest

from medihub.adapters.devices.astm import AstmParseError, parse_e1394_message

SYNTHETIC_MESSAGE = (
    b"H|\\^&|||MINDRAY^CL-900i\r"
    b"P|1|SYNTH-PATIENT-001\r"
    b"O|1|SYNTH-SAMPLE-001||^^^TSH\r"
    b"R|1|^^^TSH|2.30|mIU/L|0.40-4.00|N||F\r"
    b"L|1|N\r"
)


def test_parser_preserves_generic_records_without_clinical_interpretation() -> None:
    message = parse_e1394_message(SYNTHETIC_MESSAGE)

    assert message.complete is True
    assert message.warnings == ()
    assert message.delimiters.field == "|"
    assert message.delimiters.repeat == "\\"
    assert message.delimiters.component == "^"
    assert message.delimiters.escape == "&"
    assert [record.record_type for record in message.records] == ["H", "P", "O", "R", "L"]
    assert message.records[1].fields == ("1", "SYNTH-PATIENT-001")
    assert message.records[3].fields == (
        "1",
        "^^^TSH",
        "2.30",
        "mIU/L",
        "0.40-4.00",
        "N",
        "",
        "F",
    )


def test_parser_preserves_an_encoded_delimiter_and_hides_fields_from_repr() -> None:
    payload = SYNTHETIC_MESSAGE.replace(b"SYNTH-PATIENT-001", b"SYNTH&F&PATIENT-001")

    message = parse_e1394_message(payload)

    assert message.records[1].fields[1] == "SYNTH&F&PATIENT-001"
    assert "SYNTH&F&PATIENT-001" not in repr(message)
    assert "SYNTH&F&PATIENT-001" not in repr(message.records[1])


def test_parser_uses_message_declared_delimiters() -> None:
    payload = "H*%?#*|MINDRAY^CL-900i\rP*1*SYNTH#F#SAMPLE-001\rR*1*TSH*2.30*mIU/L\rL*1*N\r"

    message = parse_e1394_message(payload)

    assert message.delimiters.field == "*"
    assert message.delimiters.repeat == "%"
    assert message.delimiters.component == "?"
    assert message.delimiters.escape == "#"
    assert message.records[1].fields == ("1", "SYNTH#F#SAMPLE-001")


def test_parser_accepts_crlf_and_marks_missing_terminator_incomplete() -> None:
    payload = SYNTHETIC_MESSAGE.replace(b"\r", b"\r\n").rsplit(b"L|", maxsplit=1)[0]

    message = parse_e1394_message(payload)

    assert message.complete is False
    assert message.warnings == ("message_terminator_missing",)


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"", "message_empty"),
        (b"P|1|SYNTH-PATIENT-001\r", "header_missing"),
        (b"H|\\^&|||TEST\nP|1|SAMPLE\rL|1|N\r", "record_separator_invalid"),
        (b"H|\\^&|||TEST\rP|1|broken&\rL|1|N\r", "escape_sequence_unclosed"),
        (
            b"H|\\^&|||TEST\rL|1|N\rP|1|SAMPLE\r",
            "records_after_terminator",
        ),
        (
            b"H|\\^&|||TEST\rH|\\^&|||SECOND\rL|1|N\r",
            "multiple_headers",
        ),
    ],
)
def test_parser_rejects_malformed_streams_with_value_free_codes(payload: bytes, code: str) -> None:
    with pytest.raises(AstmParseError) as error:
        parse_e1394_message(payload)

    assert error.value.code == code
    assert "SYNTH-PATIENT-001" not in str(error.value)


def test_parser_bounds_message_size_and_rejects_unsupported_encoding() -> None:
    with pytest.raises(AstmParseError, match="message_too_large"):
        parse_e1394_message(SYNTHETIC_MESSAGE, max_message_bytes=10)

    with pytest.raises(AstmParseError, match="message_encoding_invalid"):
        parse_e1394_message(b"H|\\^&|||\xff\rL|1|N\r", encoding="ascii")


def test_parser_enforces_field_count_bound() -> None:
    many_fields = "|".join("x" for _ in range(1_025))
    payload = f"H|\\^&|||TEST\rP|{many_fields}\rL|1|N\r"

    with pytest.raises(AstmParseError, match="field_count_exceeded"):
        parse_e1394_message(payload)
