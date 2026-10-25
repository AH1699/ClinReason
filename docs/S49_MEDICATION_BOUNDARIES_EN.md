# Medication wording: 28 offline contrasts, no new scores

We now have 14 authored answer profiles in English and Chinese to investigate H136, H137 and H140. They reuse `HC-MT-MEDSAFE-013`; they are **not 28 new cases**, approved labels or evidence that the judge can distinguish the answers correctly. The draft makes the disputed boundaries inspectable without changing existing scores.

## What the examples vary

| Target | Answer profiles | Current status |
|---|---|---|
| Update criterion 3: temporary medication hold | Explicit hold; equivalent next-dose skip | Author hypothesis: `met` |
| Same target | Ask clinician about medicines; no update instruction; hold mentioned only in the initial answer | Author hypothesis: `partial` under the existing stage-specific rule |
| Same target | Do not add a new medicine; do not increase the usual dose; ambiguous “leave it alone” wording | Unlabelled; H140/H136 must be resolved prospectively |
| Initial criterion 2: clinician-led illness plan | Both ketone-check and medication-pause questions included | Author hypothesis: `met` |
| Same target | Neither question included; both questions left to a self-directed plan | Author hypothesis: `partial` |
| Same target | Only ketones; only medication pause; generic clinician contact followed by separate self-directed actions | Unlabelled; H137 component and relationship boundary |

Across both languages: **28 packets, 16 author hypotheses, 12 unlabelled packets and 22 one-component contrast pairs**. Some profiles deliberately contain incomplete or questionable advice. These are fictional evaluation artifacts, not patient instructions. Initial-only hold also raises a separate initial-stage appropriateness question; the focused packet does not assess that initial criterion.

The hold examples keep the emergency/testing explanation and diagnostic uncertainty constant, changing one action clause. The initial-only pair keeps the update exactly identical and changes only the prior answer. Four illness-plan pairs vary one missing question; self-directed and generic-contact examples are exploratory and are not represented as one-component pairs.

## Where to inspect or run the offline checks

- [Draft wording and author hypotheses](../data/multiturn/s49_medication_boundaries_draft_v1.json)
- [Packet builder and audit](../scripts/medication_boundaries_s49.py)
- [Eight integrity tests](../tests/test_medication_boundaries_s49.py)
- [Reproducible audit summary](../data/audit/s49_medication_boundaries_summary.json)

Run `python3 -m scripts.medication_boundaries_s49` and `python3 -m unittest tests.test_medication_boundaries_s49 -q`. There is no network path. Packets bind the existing case and anchor hashes, expose only the selected requirement, and exclude profile names, model identity, author hypotheses and review flags. Initial-stage packets cannot see the future user turn or update answer. These are focused diagnostic packets, not directly interchangeable with the full-score judge schema.

## What still needs to happen

Prepare a new focused judge adapter and freeze its output contract, blinded packet hashes, repeat schedule and analysis plan before any boundary calls. Keep all six ambiguous profiles per language exploratory: report how the judge reads them, not an “accuracy” percentage against invented truth. Even the other hypotheses are developer expectations, not clinical gold labels. No boundary calls are authorized or made here.

Resolve any proposed wording/credit change as a new draft version, explain its clinical and conversational implications, and test it prospectively. Preserve S48's recorded 95 and H140; do not deduct points merely because this draft exists. Later clinical/bilingual review must address the temporary-hold requirement itself, whether prior advice should count, one-component partial credit and English/Chinese equivalence. Do not fit these choices to 60–70 / ~80 / ~90 aspirations.

Only after this narrow check should the nine-family panel use a uniform prospective judging policy. The [S49 output-cap supplement](S49_CAP_SUPPLEMENT_PROTOCOL_EN.md) is a separate one-call technical experiment, not authorization for these tests or the larger panel.
