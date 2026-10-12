# Bengali localization review checklist

**Status:** Playwright browser checks now cover language switching, persistence across routes, translated live data, device actions, mapping/API pages, and a narrow mobile viewport. **Review by a native Bengali speaker from Bangladesh is still pending**; machine-assisted wording and automated tests are not a substitute for human language or clinical-domain review.

## Scope and safety

This checklist applies to the English / বাংলা FastAPI dashboard, its in-app help, and the companion Next.js operations overview. The Bengali interface describes a synthetic-only software demo. It must not suggest that the dashboard operates physical devices, provides clinical guidance, or connects to an EMR/EMS. Preserve English protocol names, identifiers, codes, and error codes where translating them would make them harder to verify against the underlying system.

## Suggested term review

Please review these initial choices for clarity and consistent usage in Bangladesh. The current copy uses a polite, instructional tone (`করুন`); preserve a respectful, plain-language tone and avoid implying clinical approval.

| English concept | Current Bengali choice | Reviewer question |
| --- | --- | --- |
| Synthetic / synthetic data | সিন্থেটিক / সিন্থেটিক ডেটা | Should the first mention say “কৃত্রিম (সিন্থেটিক)” for clarity, then use the shorter technical term? |
| Simulator | সিমুলেটর | Is this familiar to the intended operator audience, or should the help explain it in simpler language? |
| Device management | ডিভাইস ব্যবস্থাপনা | Is the menu term natural and distinct from physical-device control? |
| Data mapping | ডেটা ম্যাপিং | Is a short explanation needed for non-technical operators? |
| Outbox | আউটবক্স | Should this remain transliterated, or be paired with a short Bengali explanation on first use? |
| Policy hold | নীতি-হোল্ড | Is “নীতি অনুযায়ী স্থগিত” or another phrase clearer than the current mixed technical term? |
| Acknowledged / acknowledgement | নিশ্চিত হয়েছে / স্বীকৃতি | Does the wording distinguish a receiver acknowledgement from clinical confirmation? |
| Retry / retryable | পুনঃচেষ্টা / পুনঃচেষ্টাযোগ্য | Is this understandable in the delivery-control context? |
| Draft / inactive | খসড়া / নিষ্ক্রিয় | Confirm that the wording clearly communicates “not activated.” |
| Receiver / endpoint | রিসিভার / এন্ডপয়েন্ট | Confirm that transliteration is appropriate for the intended technical audience. |

## First-pass audit of the Next.js overview — 2026-10-11

The following clarity edits are provisional, machine-assisted wording—not native-speaker approval. They are now present in `frontend/app/page.tsx`. Please review the wording in the live interface and change it where a Bangladesh-based operator would use a more natural or precise term.

| English concept | Previous Bengali | Current provisional Bengali | Why it needs human review |
| --- | --- | --- | --- |
| Events ingested | ইনজেস্ট করা ইভেন্ট | গ্রহণ করা ইভেন্ট | Replaces an English-derived verb; confirm that “গ্রহণ” conveys ingestion rather than clinical acceptance. |
| Receiver acknowledgement (count) | নিশ্চিত হয়েছে | রিসিভারের স্বীকৃতি | Names the receiver so it cannot be mistaken for clinical confirmation. Confirm the best local technical term for an acknowledgement. |
| Acknowledged delivery (status) | নিশ্চিত হয়েছে | রিসিভার গ্রহণ করেছে | Explicitly attributes acceptance to the test receiver; verify that it does not imply patient/clinical confirmation. |
| Pending delivery | অপেক্ষমাণ ডেলিভারি | পাঠানোর অপেক্ষায় | Uses a plain-language description; verify it fits the queue/pending state. |
| Policy holds | নীতি-হোল্ড | নীতির কারণে আটকে রাখা | Replaces a mixed-language compound; confirm the wording accurately describes a policy block. |
| In-process receiver | প্রসেসের ভেতরে | একই প্রসেসে চলছে | Clarifies that the test receiver runs in the same software process; check whether “প্রসেস” or “প্রক্রিয়া” is more familiar to the target operators. |
| Retryable failure | পুনঃচেষ্টাযোগ্য ব্যর্থতা | ব্যর্থ—আবার চেষ্টা করা যাবে | Makes the available next action explicit; check readability and fit in the status row. |
| Synthetic demo values | তৈরি করা সিন্থেটিক মান | ডেমোর জন্য তৈরি কৃত্রিম (সিন্থেটিক) মান | Introduces a plain Bengali gloss alongside the technical term; confirm the preferred term and repetition level. |
| Bangladesh deployment target | বাংলাদেশ প্রয়োজনীয় ডিপ্লয়মেন্ট লক্ষ্য | বাংলাদেশে স্থাপন করাই MediHub-এর লক্ষ্য | Rewrites a stiff mixed-language phrase; confirm this preserves the intended target-country meaning without implying deployment readiness. |

The Next.js Playwright suite now checks the receiver-attributed Bengali delivery states and the Bangladesh safety statement. Those assertions protect against accidental copy regressions; they do not establish that the wording is natural or clinically approved.

## Automated browser checks

From the repository root, install the headless Chromium shell and run the browser suite:

```bash
python -m pip install -e ".[dev]"
python -m playwright install --only-shell chromium
pytest tests/browser/test_dashboard_localization.py -q
```

CI installs Chromium and runs these tests. The browser test stubs all FastAPI dashboard APIs with deterministic synthetic responses and aborts requests to other hosts; it never contacts a device or external receiver. The companion Next.js overview has its own Playwright language-persistence and mobile-width checks and is production-built in CI; its Bengali wording still needs the same native-speaker review. From `frontend/`, run `npm ci`, `npx playwright install --only-shell chromium`, `npm run build`, and `npm run test:e2e`.

## Human review checklist

A reviewer should complete these checks using the actual dashboard, not only this Markdown file:

- [ ] Read the visible copy on Operations, Device management, Data mapping, EMR / EMS APIs, and Help in both languages.
- [ ] Confirm the Bangla is natural, consistent, and suitable for health-facility operators in Bangladesh; flag awkward calques, overly technical terms, and ambiguous instructions.
- [ ] Confirm that warning text keeps the synthetic-only and “no patient data / no live connection” boundaries clear and prominent.
- [ ] Exercise dynamic states: healthy/starting, active/inactive simulator, no data, retryable and terminal failure, mapping pass/stale, and error/status messages.
- [ ] Check Bengali script rendering and wrapping at 320, 360, and 390 CSS-pixel viewport widths on at least one Android browser and one desktop browser with a Bengali-capable font.
- [ ] Navigate the language selector and links with keyboard only. Verify the selected language is announced, the page `lang` changes, focus stays visible, and there is no text clipped behind controls.
- [ ] With a screen reader, confirm the language selector's accessible name, page heading, navigation labels, and live status messages are understandable in Bengali.
- [ ] Confirm English and Bengali share the same action meaning. Language must not change simulator state, mapping rules, request payloads, or network behavior.
- [ ] Recheck revisions with the product/clinical safety owner before adopting any words that could imply diagnosis, measurement validity, or real integration support.

## Feedback format

Record suggested changes as small, reviewable entries:

| Route / element | English source | Current Bengali | Suggested Bengali | Reason / reviewer |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

Do not include real patient, facility-secret, or vendor-credential information in review notes, screenshots, or test fixtures. After copy changes, rerun the browser localization tests and ask the same reviewer to verify the corrections.
