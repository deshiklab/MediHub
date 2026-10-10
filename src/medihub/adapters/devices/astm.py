"""Offline ASTM E1394 record-stream parsing primitives.

This module does not implement ASTM E1381 framing/session control, serial/TCP
transport, a Mindray CL-900i profile, clinical mappings, or result delivery. It is
a bounded parsing scaffold for synthetic fixtures until the exact instrument
host-interface guide is approved. Record fields can contain patient data and are
intentionally hidden from ``repr``; callers must not log or persist them without
facility approval and controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

MAX_MESSAGE_BYTES: Final[int] = 1_048_576
MAX_RECORDS: Final[int] = 10_000
MAX_FIELDS_PER_RECORD: Final[int] = 1_024


class AstmParseError(ValueError):
    """A stable, value-free parser failure code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AstmDelimiters:
    """Delimiters declared by the message's H record."""

    field: str
    repeat: str
    component: str
    escape: str


@dataclass(frozen=True, slots=True)
class AstmRecord:
    """One record; fields are retained verbatim and hidden from repr."""

    record_type: str
    fields: tuple[str, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class AstmMessage:
    """A parsed record stream without vendor or clinical interpretation."""

    delimiters: AstmDelimiters
    records: tuple[AstmRecord, ...] = field(repr=False)
    complete: bool
    warnings: tuple[str, ...] = ()


def parse_e1394_message(
    payload: bytes | str,
    *,
    encoding: str = "latin-1",
    max_message_bytes: int = MAX_MESSAGE_BYTES,
) -> AstmMessage:
    """Parse one CR-delimited ASTM E1394 record stream, preserving raw fields.

    The payload must already be de-framed. Latin-1 preserves each input byte by default;
    use the instrument's documented character set when it is known. This
    function deliberately does not decode ASTM escape codes, map R-record fields,
    infer results, or accept multiple messages concatenated together.
    """

    if max_message_bytes < 1:
        raise ValueError("max_message_bytes must be positive")
    try:
        if isinstance(payload, bytes):
            if len(payload) > max_message_bytes:
                raise AstmParseError("message_too_large")
            text = payload.decode(encoding, errors="strict")
            byte_length = len(payload)
        elif isinstance(payload, str):
            if len(payload) > max_message_bytes:
                raise AstmParseError("message_too_large")
            encoded = payload.encode(encoding, errors="strict")
            byte_length = len(encoded)
            if byte_length > max_message_bytes:
                raise AstmParseError("message_too_large")
            text = payload
        else:
            raise AstmParseError("message_type_unsupported")
    except AstmParseError:
        raise
    except (LookupError, UnicodeError):
        raise AstmParseError("message_encoding_invalid") from None

    if byte_length == 0 or not text:
        raise AstmParseError("message_empty")

    text = text.replace("\r\n", "\r")
    if "\n" in text:
        raise AstmParseError("record_separator_invalid")
    if text.endswith("\r"):
        text = text[:-1]

    lines = text.split("\r")
    if not lines or any(not line for line in lines):
        raise AstmParseError("record_empty")
    if any(ord(char) < 32 for line in lines for char in line):
        raise AstmParseError("record_control_character")
    if len(lines) > MAX_RECORDS:
        raise AstmParseError("record_count_exceeded")

    header = lines[0]
    if len(header) < 3 or header[0] != "H":
        raise AstmParseError("header_missing")
    field_delimiter = header[1]
    if not _is_delimiter(field_delimiter):
        raise AstmParseError("header_delimiter_invalid")

    header_tail = header[2:]
    delimiter_spec, separator, remainder = header_tail.partition(field_delimiter)
    if not separator:
        delimiter_spec = header_tail
        remainder = ""
    if len(delimiter_spec) != 3:
        raise AstmParseError("header_delimiter_spec_invalid")
    repeat_delimiter, component_delimiter, escape_delimiter = delimiter_spec
    declared = (
        field_delimiter,
        repeat_delimiter,
        component_delimiter,
        escape_delimiter,
    )
    if any(not _is_delimiter(char) for char in declared) or len(set(declared)) != 4:
        raise AstmParseError("header_delimiter_spec_invalid")

    delimiters = AstmDelimiters(
        field=field_delimiter,
        repeat=repeat_delimiter,
        component=component_delimiter,
        escape=escape_delimiter,
    )
    header_fields = (delimiter_spec,)
    if separator:
        header_fields += _split_fields(remainder, delimiters)
    if len(header_fields) > MAX_FIELDS_PER_RECORD:
        raise AstmParseError("field_count_exceeded")
    records: list[AstmRecord] = [AstmRecord("H", header_fields)]
    terminated = False

    for line in lines[1:]:
        if len(line) < 2 or line[1] != field_delimiter:
            raise AstmParseError("record_delimiter_invalid")
        record_type = line[0]
        if not record_type.isascii() or not record_type.isalpha() or not record_type.isupper():
            raise AstmParseError("record_type_invalid")
        if record_type == "H":
            raise AstmParseError("multiple_headers")
        if terminated:
            raise AstmParseError("records_after_terminator")

        fields = _split_fields(line[2:], delimiters)
        if len(fields) > MAX_FIELDS_PER_RECORD:
            raise AstmParseError("field_count_exceeded")
        records.append(AstmRecord(record_type, fields))
        terminated = record_type == "L"

    complete = terminated
    warnings = () if complete else ("message_terminator_missing",)
    return AstmMessage(
        delimiters=delimiters,
        records=tuple(records),
        complete=complete,
        warnings=warnings,
    )


def _split_fields(content: str, delimiters: AstmDelimiters) -> tuple[str, ...]:
    """Split on the declared field delimiter without interpreting escapes."""

    fields: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(content):
        char = content[index]
        if char == delimiters.escape:
            closing = content.find(delimiters.escape, index + 1)
            if closing < 0:
                raise AstmParseError("escape_sequence_unclosed")
            current.append(content[index : closing + 1])
            index = closing + 1
        elif char == delimiters.field:
            if len(fields) >= MAX_FIELDS_PER_RECORD:
                raise AstmParseError("field_count_exceeded")
            fields.append("".join(current))
            current.clear()
            index += 1
        else:
            current.append(char)
            index += 1

    if len(fields) >= MAX_FIELDS_PER_RECORD:
        raise AstmParseError("field_count_exceeded")
    fields.append("".join(current))
    return tuple(fields)


def _is_delimiter(char: str) -> bool:
    return len(char) == 1 and char.isascii() and char.isprintable() and not char.isalnum()
