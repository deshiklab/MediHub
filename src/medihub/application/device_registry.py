"""Bangladesh-oriented device discovery catalogue and non-connectable profiles.

This module contains no transport, endpoint, credential, patient, or measurement
configuration. Catalogue entries are research leads, not supported-device claims.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import Field, StringConstraints, model_validator

from medihub.domain.base import AwareDateTime, DomainModel

DeviceFamily = Literal[
    "immunoassay",
    "hematology",
    "clinical_chemistry",
    "urinalysis",
    "electrolyte",
    "coagulation",
    "hba1c",
    "blood_gas",
    "point_of_care",
    "other",
]
DeviceTransport = Literal["unconfirmed", "tcp", "serial", "file_feed", "vendor_gateway"]
DeviceProtocol = Literal[
    "unconfirmed",
    "astm_e1394",
    "hl7_v2",
    "vendor_defined",
    "other",
]
ApprovalStatus = Literal["pending", "approved"]

SafeProfileLabel = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=80,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9 .()_-]{0,79}$",
    ),
]
SafeEvidenceReference = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
    ),
]


class DeviceLibraryCandidate(DomainModel):
    """A local-market discovery lead; never implies an installed base or driver."""

    candidate_id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    manufacturer: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=80)
    device_family: DeviceFamily
    discovery_basis: Literal[
        "user_selected_target",
        "bangladesh_seller_listing",
        "bangladesh_supplier_category",
        "bangladesh_facility_self_report",
    ]
    evidence_note: str = Field(min_length=1, max_length=180)
    source_url: str | None = Field(default=None, pattern=r"^https://")
    evidence_reviewed_on: date | None = None
    status: Literal["discovery_only"] = "discovery_only"
    compatibility_verified: Literal[False] = False
    live_adapter_available: Literal[False] = False


DEVICE_LIBRARY_CANDIDATES: tuple[DeviceLibraryCandidate, ...] = (
    DeviceLibraryCandidate(
        candidate_id="mindray-cl900i",
        manufacturer="Mindray",
        model="CL-900i",
        device_family="immunoassay",
        discovery_basis="user_selected_target",
        evidence_note=(
            "User-selected integration target; installed base, firmware, and host interface "
            "are unverified."
        ),
    ),
    DeviceLibraryCandidate(
        candidate_id="zecen-cia-600",
        manufacturer="Zecen",
        model="CIA 600",
        device_family="immunoassay",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Medistore Bangladesh page lists this model; its LIS/networking claims are unverified "
            "and do not identify the installed base or interface profile."
        ),
        source_url="https://www.medistorebd.com/product/cia-600-automic-chemiluminescence-analyzer/",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="zecen-cia-1200",
        manufacturer="Zecen",
        model="CIA 1200",
        device_family="immunoassay",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Medistore Bangladesh page lists this model; its LIS/networking claims are unverified "
            "and do not identify the installed base or interface profile."
        ),
        source_url="https://www.medistorebd.com/product/cia1200-full-auto-chemiluminescence-analyzer/",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="mindray-bc-20s",
        manufacturer="Mindray",
        model="BC-20s",
        device_family="hematology",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Bangladesh seller listing only; not evidence of installed-base prevalence or "
            "connectivity."
        ),
        source_url="https://www.medistorebd.com/product/hematology-analyzer-bc-20s/",
        evidence_reviewed_on=date(2026, 10, 11),
    ),
    DeviceLibraryCandidate(
        candidate_id="mindray-bc-10",
        manufacturer="Mindray",
        model="BC-10",
        device_family="hematology",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Bangladesh seller listing only; not evidence of installed-base prevalence or "
            "connectivity."
        ),
        source_url="https://www.medistorebd.com/product/mindray-bc-10-auto-hematology-analyzer/",
        evidence_reviewed_on=date(2026, 10, 11),
    ),
    DeviceLibraryCandidate(
        candidate_id="mindray-bc-30",
        manufacturer="Mindray",
        model="BC-30",
        device_family="hematology",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Techno Health Bangladesh product listing only; no evidence of installed prevalence, "
            "firmware, or host connectivity."
        ),
        source_url="https://technohealth.com.bd/vector-hematology-analyzer/",
        evidence_reviewed_on=date(2026, 10, 11),
    ),
    DeviceLibraryCandidate(
        candidate_id="mindray-bc-5000",
        manufacturer="Mindray",
        model="BC-5000",
        device_family="hematology",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Medistore Bangladesh product listing only; no evidence of installed prevalence, "
            "exact unit, or host connectivity."
        ),
        source_url="https://www.medistorebd.com/product/auto-hematology-analyzer-bc-5000/",
        evidence_reviewed_on=date(2026, 10, 11),
    ),
    DeviceLibraryCandidate(
        candidate_id="mindray-bc-5130",
        manufacturer="Mindray",
        model="BC-5130",
        device_family="hematology",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Medistore Bangladesh lists this model and claims HL7/bidirectional LIS; this is not "
            "a validated host profile or evidence of installed prevalence."
        ),
        source_url="https://www.medistorebd.com/product/mindray-bc-5130-auto-hematology-analyzer/",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="edan-h30",
        manufacturer="EDAN",
        model="H30",
        device_family="hematology",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "BMA Bazar lists EDAN H30; its LAN description is not a confirmed host profile or "
            "evidence of installed prevalence."
        ),
        source_url="https://bmabazar.com/shop/edan-3-part-different-cbc-fully-auto-hematology-analyzer-machine-for-blood-test-h30-copy/",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="dymind-dh36",
        manufacturer="Dymind",
        model="DH36",
        device_family="hematology",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Medistore Bangladesh lists DH36 and advertises bidirectional LIS; this is not a "
            "validated host profile or evidence of installed prevalence."
        ),
        source_url="https://www.medistorebd.com/product/dymind-dh36-auto-hematology-analyzer/",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="dymind-df50",
        manufacturer="Dymind",
        model="DF50",
        device_family="hematology",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Medistore Bangladesh product listing only; no evidence of installed prevalence, "
            "exact unit, or host connectivity."
        ),
        source_url="https://www.medistorebd.com/product/dymind-df50-auto-hematology-analyzer/",
        evidence_reviewed_on=date(2026, 10, 11),
    ),
    DeviceLibraryCandidate(
        candidate_id="celltus-cts-3000",
        manufacturer="Celltus",
        model="CTS-3000",
        device_family="hematology",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Medistore Bangladesh product page lists this model; installed prevalence, firmware, "
            "and host connectivity are unverified."
        ),
        source_url="https://www.medistorebd.com/product/celltus-3-part-hematology-analyzer/",
        evidence_reviewed_on=date(2026, 10, 13),
    ),
    DeviceLibraryCandidate(
        candidate_id="celltus-cts-5000",
        manufacturer="Celltus",
        model="CTS-5000",
        device_family="hematology",
        discovery_basis="bangladesh_supplier_category",
        evidence_note=(
            "Medistore Bangladesh hematology category lists this model; installed prevalence, "
            "firmware, and host connectivity are unverified."
        ),
        source_url="https://www.medistorebd.com/product-category/hematology-analyzer/",
        evidence_reviewed_on=date(2026, 10, 13),
    ),
    DeviceLibraryCandidate(
        candidate_id="dymind-df-51",
        manufacturer="Dymind",
        model="DF-51",
        device_family="hematology",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Medistore Bangladesh product page lists this model; installed prevalence, firmware, "
            "and host connectivity are unverified."
        ),
        source_url="https://www.medistorebd.com/product/dymind-auto-hematology-analyzer-df-51-5-part/",
        evidence_reviewed_on=date(2026, 10, 13),
    ),
    DeviceLibraryCandidate(
        candidate_id="sysmex-xn-3000",
        manufacturer="Sysmex",
        model="XN-3000",
        device_family="hematology",
        discovery_basis="bangladesh_facility_self_report",
        evidence_note=(
            "Padma Diagnostic Centre's page reports a local installation; self-reported and "
            "not evidence for another site's installed base."
        ),
        source_url="https://padma-bd.com/instruments/laboratoryinstruments/",
        evidence_reviewed_on=date(2026, 10, 13),
    ),
    DeviceLibraryCandidate(
        candidate_id="mindray-ba-88a",
        manufacturer="Mindray",
        model="BA-88A",
        device_family="clinical_chemistry",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Bangladesh seller listing only; confirm exact unit and any structured host output "
            "with the site."
        ),
        source_url="https://technohealth.com.bd/mindray-biochemistry-analyzer-ba-88a/",
        evidence_reviewed_on=date(2026, 10, 11),
    ),
    DeviceLibraryCandidate(
        candidate_id="erba-chem-5x",
        manufacturer="Erba",
        model="Chem 5x",
        device_family="clinical_chemistry",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Bangladesh seller listing only; confirm exact unit and any structured host output "
            "with the site."
        ),
        source_url="https://technohealth.com.bd/erba-chem-5x-biochemistry-analyzer/",
        evidence_reviewed_on=date(2026, 10, 11),
    ),
    DeviceLibraryCandidate(
        candidate_id="mindray-bs-240",
        manufacturer="Mindray",
        model="BS-240",
        device_family="clinical_chemistry",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Rapid Medical Bangladesh lists this model; the listing does not establish installed "
            "prevalence or the host profile of any unit."
        ),
        source_url="https://rapidmedicalbd.com/shop/application/laboratory-equipments/analyzer-machines/bio-chemistry-analyzer/mindray-bs-240-clinical-fully-automated-chemistry-analyzer-with-hba1c-capability/",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="erba-xl-200",
        manufacturer="Erba",
        model="XL-200",
        device_family="clinical_chemistry",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Rapid Medical Bangladesh lists this model and advertises LIS connection; the claim is "
            "not a validated host profile or evidence of installed prevalence."
        ),
        source_url="https://rapidmedicalbd.com/shop/application/laboratory-equipments/analyzer-machines/bio-chemistry-analyzer/erba-xl-200-fully-automatic-clinical-chemistry-analyzer-machine-biochemical-analyzer/",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="icubio-imagic-m7",
        manufacturer="ICUBIO",
        model="iMagic M7",
        device_family="clinical_chemistry",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Medistore Bangladesh page lists this model and claims RS-232/PC connectivity; "
            "installed prevalence, firmware, and host profile are unverified."
        ),
        source_url="https://www.medistorebd.com/product/fully-automated-bio-chemistry-analyzer-icubio-imagic-m7/",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="cornley-bg-800",
        manufacturer="Meizhou Cornley Hi-Tech",
        model="BG-800",
        device_family="blood_gas",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "BMA Bazar identifies the BG-800 blood-gas model; the listing does not establish local "
            "installations or an approved host interface."
        ),
        source_url="https://bmabazar.com/shop/blood-gas-electrolyte-analyzer-bg-8000/",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="contec-bc400",
        manufacturer="Contec",
        model="BC400",
        device_family="urinalysis",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "BMA Bazar lists the Contec BC400 urine analyzer and mentions RS-232; this is not a "
            "verified host profile or evidence of installed prevalence."
        ),
        source_url="https://bmabazar.com/shop/contec-bc400-clinical-11-parameter-urine-analyzer-machine/",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="bio-elite-klite8",
        manufacturer="Bio Elite",
        model="K-Lite8",
        device_family="electrolyte",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "BMA Bazar lists the K-Lite8 and advertises HL7/LIS; this is not a validated host "
            "profile or evidence of installed prevalence."
        ),
        source_url="https://bmabazar.com/shop/electrolyte-analyzer-k-lite8/",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="succeeder-sf-400",
        manufacturer="Succeeder",
        model="SF-400",
        device_family="coagulation",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Medistore Bangladesh lists SF-400 and advertises USB/RS-232; this is not a validated "
            "host profile or evidence of installed prevalence."
        ),
        source_url="https://www.medistorebd.com/product/automated-coagulation-analyzer/",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="aehealthcare-ms-11",
        manufacturer="AeHealthcare",
        model="MS 11",
        device_family="hba1c",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Techno Healthcare lists AeHealthcare MS 11 for HbA1c/POCT, but page branding is "
            "inconsistent; confirm identity. No installed prevalence or host profile "
            "is established."
        ),
        source_url="https://www.technohealthcare.com.bd/product/36",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="getein-gp-1100",
        manufacturer="Getein",
        model="GP 1100",
        device_family="point_of_care",
        discovery_basis="bangladesh_seller_listing",
        evidence_note=(
            "Techno Healthcare lists Getein GP 1100 as POCT/HbA1c; seller claims do not establish "
            "installed prevalence or a validated host profile."
        ),
        source_url="https://www.technohealthcare.com.bd/product/37",
        evidence_reviewed_on=date(2026, 10, 14),
    ),
    DeviceLibraryCandidate(
        candidate_id="survey-urinalysis",
        manufacturer="To be confirmed",
        model="Urinalysis analyzer to survey",
        device_family="urinalysis",
        discovery_basis="bangladesh_supplier_category",
        evidence_note="Family-level survey lead; choose an exact model from facility inventory.",
    ),
    DeviceLibraryCandidate(
        candidate_id="survey-electrolyte",
        manufacturer="To be confirmed",
        model="Electrolyte analyzer to survey",
        device_family="electrolyte",
        discovery_basis="bangladesh_supplier_category",
        evidence_note="Family-level survey lead; choose an exact model from facility inventory.",
    ),
    DeviceLibraryCandidate(
        candidate_id="survey-coagulation",
        manufacturer="To be confirmed",
        model="Coagulation analyzer to survey",
        device_family="coagulation",
        discovery_basis="bangladesh_supplier_category",
        evidence_note="Family-level survey lead; choose an exact model from facility inventory.",
    ),
    DeviceLibraryCandidate(
        candidate_id="survey-hba1c",
        manufacturer="To be confirmed",
        model="HbA1c analyzer to survey",
        device_family="hba1c",
        discovery_basis="bangladesh_supplier_category",
        evidence_note="Family-level survey lead; choose an exact model from facility inventory.",
    ),
    DeviceLibraryCandidate(
        candidate_id="survey-blood-gas",
        manufacturer="To be confirmed",
        model="Blood-gas analyzer to survey",
        device_family="blood_gas",
        discovery_basis="bangladesh_supplier_category",
        evidence_note="Family-level survey lead; choose an exact model from facility inventory.",
    ),
    DeviceLibraryCandidate(
        candidate_id="survey-point-of-care",
        manufacturer="To be confirmed",
        model="Point-of-care analyzer to survey",
        device_family="point_of_care",
        discovery_basis="bangladesh_supplier_category",
        evidence_note="Family-level survey lead; choose an exact model from facility inventory.",
    ),
)


class DeviceProfileDraft(DomainModel):
    """Non-secret discovery metadata; deliberately cannot describe a connection."""

    candidate_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9-]{2,63}$",
    )
    manufacturer: SafeProfileLabel
    model: SafeProfileLabel
    device_family: DeviceFamily
    firmware_software_scope: SafeProfileLabel = "unknown"
    transport: DeviceTransport = "unconfirmed"
    protocol: DeviceProtocol = "unconfirmed"
    protocol_version: SafeProfileLabel | None = None
    interface_document_reference: SafeEvidenceReference | None = None
    vendor_authorization_status: ApprovalStatus = "pending"
    vendor_authorization_reference: SafeEvidenceReference | None = None
    facility_authorization_status: ApprovalStatus = "pending"
    facility_authorization_reference: SafeEvidenceReference | None = None
    results_only_confirmed: bool = False
    receiver_contract_reference: SafeEvidenceReference | None = None

    @model_validator(mode="after")
    def approved_gates_need_evidence_references(self) -> DeviceProfileDraft:
        if (
            self.vendor_authorization_status == "approved"
            and self.vendor_authorization_reference is None
        ):
            raise ValueError("vendor_approval_reference_required")
        if (
            self.facility_authorization_status == "approved"
            and self.facility_authorization_reference is None
        ):
            raise ValueError("facility_approval_reference_required")
        if self.results_only_confirmed and self.interface_document_reference is None:
            raise ValueError("interface_document_reference_required")
        return self


class DeviceProfileRecord(DeviceProfileDraft):
    """Saved non-secret discovery profile; readiness never activates hardware."""

    profile_id: UUID
    created_at: AwareDateTime
    updated_at: AwareDateTime


def new_device_profile(draft: DeviceProfileDraft) -> DeviceProfileRecord:
    """Create a discovery record with server-owned identity and timestamps."""

    now = datetime.now(UTC)
    return DeviceProfileRecord(
        **draft.model_dump(),
        profile_id=uuid4(),
        created_at=now,
        updated_at=now,
    )


def device_profile_readiness(record: DeviceProfileRecord) -> dict[str, object]:
    """Return explicit, non-sensitive gates without implying support or activation."""

    firmware_confirmed = record.firmware_software_scope.casefold() not in {
        "unknown",
        "unconfirmed",
        "to be confirmed",
    }
    protocol_confirmed = record.protocol != "unconfirmed" and record.protocol_version is not None
    transport_confirmed = record.transport != "unconfirmed"
    document_recorded = record.interface_document_reference is not None
    vendor_approved = (
        record.vendor_authorization_status == "approved"
        and record.vendor_authorization_reference is not None
    )
    facility_approved = (
        record.facility_authorization_status == "approved"
        and record.facility_authorization_reference is not None
    )
    receiver_contract_recorded = record.receiver_contract_reference is not None

    checks = [
        {"id": "exact_device_identity", "status": "recorded"},
        {
            "id": "firmware_scope",
            "status": "recorded" if firmware_confirmed else "pending",
        },
        {"id": "documented_transport", "status": "recorded" if transport_confirmed else "pending"},
        {"id": "protocol_and_version", "status": "recorded" if protocol_confirmed else "pending"},
        {
            "id": "controlled_interface_document",
            "status": "recorded" if document_recorded else "pending",
        },
        {
            "id": "vendor_authorization",
            "status": "recorded" if vendor_approved else "pending",
        },
        {
            "id": "facility_authorization",
            "status": "recorded" if facility_approved else "pending",
        },
        {
            "id": "results_only_scope",
            "status": "recorded" if record.results_only_confirmed else "pending",
        },
        {
            "id": "receiver_contract",
            "status": "recorded" if receiver_contract_recorded else "pending",
        },
        {"id": "synthetic_validation", "status": "not_run"},
        {"id": "site_approval", "status": "not_approved"},
    ]

    blockers: set[str] = set()
    if not firmware_confirmed:
        blockers.add("firmware_scope_unconfirmed")
    if record.protocol == "unconfirmed":
        blockers.add("protocol_unconfirmed")
    elif record.protocol_version is None:
        blockers.add("protocol_version_missing")
    if not transport_confirmed:
        blockers.add("transport_unconfirmed")
    if not document_recorded:
        blockers.add("interface_document_reference_missing")
    if not vendor_approved:
        blockers.add("vendor_authorization_pending")
    if not facility_approved:
        blockers.add("facility_authorization_pending")
    if not record.results_only_confirmed:
        blockers.add("results_only_scope_unconfirmed")
    if not receiver_contract_recorded:
        blockers.add("receiver_contract_missing")

    ordered_blockers = sorted(blockers)
    status = (
        "discovery_only" if ordered_blockers else "discovery_complete_pending_synthetic_validation"
    )
    return {
        "status": status,
        "blockers": ordered_blockers,
        "checks": checks,
        "synthetic_validation_status": "not_run",
        "site_approval_status": "not_approved",
        "hardware_connection_enabled": False,
    }


def device_profile_payload(record: DeviceProfileRecord) -> dict[str, object]:
    """Serialize profile metadata and fail-closed readiness flags."""

    return {
        **record.model_dump(mode="json"),
        "readiness": device_profile_readiness(record),
    }


def device_library_payload() -> dict[str, object]:
    """Expose implemented adapter capabilities separately from market leads."""

    return {
        "mode": "synthetic_only",
        "country_focus": "BD",
        "candidate_count": len(DEVICE_LIBRARY_CANDIDATES),
        "installed_base_ranked": False,
        "physical_device_connections_enabled": False,
        "endpoint_fields_supported": False,
        "credential_fields_supported": False,
        "device_adapters": [
            {
                "adapter_id": "medihub.synthetic-device",
                "label": "Deterministic synthetic simulator",
                "status": "available_for_local_demo",
                "connects_to_physical_device": False,
            },
            {
                "adapter_id": "offline-astm-e1394-parser-scaffold",
                "label": "Offline ASTM E1394 record parser scaffold",
                "status": "parser_only_no_transport_or_model_profile",
                "connects_to_physical_device": False,
            },
        ],
        "candidates": [
            candidate.model_dump(mode="json") for candidate in DEVICE_LIBRARY_CANDIDATES
        ],
    }


__all__ = [
    "DEVICE_LIBRARY_CANDIDATES",
    "DeviceLibraryCandidate",
    "DeviceProfileDraft",
    "DeviceProfileRecord",
    "device_library_payload",
    "device_profile_payload",
    "device_profile_readiness",
    "new_device_profile",
]
