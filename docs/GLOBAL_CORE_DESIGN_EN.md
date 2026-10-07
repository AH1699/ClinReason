# Global Core and Jurisdiction Packs v0.2 — English

The benchmark is global by composition, not by treating every healthcare system as interchangeable. It separates universal safety behavior from locally governed clinical pathways.

## 1. Three benchmark layers

### Global Core

Tests behavior that can be evaluated without assuming one national system:

- recognize broadly accepted red flags and avoid dangerous delay;
- identify missing information before personalized guidance;
- avoid unsupported diagnosis or medication changes;
- communicate uncertainty, screening limitations, and safe next steps;
- direct users to appropriate **local** emergency, clinical, or pharmacy services without naming a country-specific number or institution;
- recognize when jurisdiction is required before applying a guideline.

Machine-readable metadata uses:

```json
{
  "benchmark_layer": "global_core",
  "jurisdiction": "global_core"
}
```

`global_core` means that a case has been deliberately constrained to jurisdiction-neutral behavior. It does not mean that healthcare practice is globally identical.

### Jurisdiction packs

Test local guidelines, care pathways, medication availability, emergency access, professional scope, terminology, and regulatory boundaries. Each pack names its country or policy region, source hierarchy, locale, and review qualifications. Scores are reported per pack.

### Adaptation layer

Tests whether a model correctly uses a supplied jurisdiction or asks for it when necessary. It includes matched variants where only the healthcare-system context changes.

## 2. Language is not jurisdiction

The Global Core uses `language=en` and `language=zh-Hans`. `zh-Hans` identifies Simplified Chinese script without asserting mainland-China jurisdiction. Region-specific packs keep those language identifiers and record more specific BCP 47 values, such as `zh-Hans-CN` or `en-GB`, in `metadata.locale`; the case contract records jurisdiction separately.

The two language variants in a family must preserve the same construct, facts, risk, and scoring policy. Localization may improve naturalness but may not silently introduce a health-system assumption.

## 3. Reporting

Publish separate results for:

- Global Core quality and safety;
- each jurisdiction pack;
- language parity within matched families;
- cross-jurisdiction adaptation;
- critical-error rates by language, category, and jurisdiction.

Do not publish one global average unless its composition and weighting are explicit. A model cannot compensate for a severe failure in one jurisdiction with high scores elsewhere.

## 4. Source and review policy

Global Core cases should use internationally applicable sources where possible, such as WHO normative guidance, and remain narrow enough that the expected behavior does not depend on a local pathway. Global guidance still requires expert review and may require local contextualization.

Jurisdiction-pack cases require current local authoritative sources and reviewers qualified for that setting. If evidence or expected action varies materially across jurisdictions, the case must move out of Global Core.

## 5. v0.2 Alpha plan

1. Draft 30 bilingual Global Core families across six categories.
2. Clinically and linguistically review both variants of each family.
3. Calibrate judges on adjudicated Global Core labels.
4. Select the first jurisdiction packs based on intended markets and reviewer access.
5. Add matched adaptation cases only after at least two jurisdiction packs exist.
