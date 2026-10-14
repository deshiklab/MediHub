# Bangladesh device discovery catalogue research

**Reviewed:** 2026-10-14  
**Status:** discovery-only research; not a supported-device matrix or installed-base survey

## Scope and interpretation

Six model-level leads were added to the Bangladesh-oriented device catalogue after review of public Bangladesh seller listings. A listing establishes only that a seller page names a model and category. It does **not** establish that the model is commonly installed, currently in stock, compatible with MediHub, or available at any specific facility. Seller statements about LIS, HL7, LAN, or bidirectional communication remain unverified catalog notes—not interface profiles.

All six records use `bangladesh_seller_listing`, remain `discovery_only`, and have `compatibility_verified=false` and `live_adapter_available=false`. No driver, transport, endpoint, protocol mapping, or device connection was implemented. Bangladesh installed-base priorities still require facility-authorized inventory survey evidence.

## Added catalogue leads

| Catalogue lead | Family | Public Bangladesh listing | What is recorded—and what is not |
| --- | --- | --- | --- |
| Mindray BC-5130 | Hematology | [Medistore Bangladesh](https://www.medistorebd.com/product/mindray-bc-5130-auto-hematology-analyzer/) | The seller identifies the model and advertises HL7/bidirectional LIS. This is not a validated host profile, proof of installed prevalence, or confirmation for an installed unit. |
| EDAN H30 | Hematology | [BMA Bazar](https://bmabazar.com/shop/edan-3-part-different-cbc-fully-auto-hematology-analyzer-machine-for-blood-test-h30-copy/) | The page identifies EDAN H30. Its LAN description does not specify an approved protocol, software revision, or receiver contract. |
| Dymind DH36 | Hematology | [Medistore Bangladesh](https://www.medistorebd.com/product/dymind-dh36-auto-hematology-analyzer/) | The seller identifies DH36 and advertises bidirectional LIS. The claim is not independently verified and does not establish local installations. |
| Mindray BS-240 | Clinical chemistry | [Rapid Medical Bangladesh](https://rapidmedicalbd.com/shop/application/laboratory-equipments/analyzer-machines/bio-chemistry-analyzer/mindray-bs-240-clinical-fully-automated-chemistry-analyzer-with-hba1c-capability/) | The seller identifies a clinical-chemistry model. No installed-base estimate or model/firmware-specific host contract is supplied. |
| Erba XL-200 | Clinical chemistry | [Rapid Medical Bangladesh](https://rapidmedicalbd.com/shop/application/laboratory-equipments/analyzer-machines/bio-chemistry-analyzer/erba-xl-200-fully-automatic-clinical-chemistry-analyzer-machine-biochemical-analyzer/) | The seller identifies XL-200 and advertises LIS connection. No protocol, installed-unit details, or receiver contract is supplied. |
| Meizhou Cornley Hi-Tech BG-800 | Blood gas | [BMA Bazar](https://bmabazar.com/shop/blood-gas-electrolyte-analyzer-bg-8000/) | The seller identifies a BG-800 blood-gas analyzer. The page does not establish an approved host interface or local installed base. |

The catalogue review date is a record of when these public listings were checked. It is not a claim that their contents, stock, or products remain current.

## Public GitHub research

These repositories were reviewed as architecture/context references only. They have not been adopted, audited, or treated as evidence that MediHub supports any analyzer.

- [OpenELIS Global analyzer plugins](https://github.com/DIGI-UW/openelisglobal-plugins) documents generic Mindray HL7 and several named analyzer plugins, including Sysmex and Horiba examples. Its plugin matrix does not establish profiles for the six models above; another product's plugin is not a MediHub driver or site-approved configuration.
- [eSmart LIS Connector](https://github.com/iamx-ariful-islam/eSmart-LIS-Connector) advertises broad ASTM/HL7, serial/network, and manufacturer coverage, including Dymind, Erba, and Mindray. The material reviewed did not provide controlled, model-and-firmware-specific evidence for the six leads. The broad compatibility claims are unverified; the code and security posture have not been audited.
- [astm_general tested-instruments note](https://github.com/nishishailesh/astm_general/blob/master/instruments_tested.txt) names Erba XL-300, XL-640, and XL-1000 as tested by that project, but not XL-200. Do not transfer protocol assumptions between these models.
- [lab-connector](https://github.com/harshilzala/lab-connector) includes a `mindray-bc5150` profile example. BC-5150 is not BC-5130; do not treat the nearby model number or repository configuration as evidence for BC-5130.

## Required gate before an adapter

For any candidate, confirm the exact installed model, firmware/software and interface revision; obtain the manufacturer-authorized interface documentation and written vendor/facility permission; establish the current LIS/receiver contract and technician-review workflow; and validate approved synthetic messages in a non-production environment. Until those gates are met, keep MediHub synthetic-only, results-only, and disconnected from physical devices and clinical receivers.
