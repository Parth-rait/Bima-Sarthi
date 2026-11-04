# Evaluation report (Eval v2)

Cases evaluated: 13. Skipped (no reviewed facts): 6.

Denominators (health cases with reviewed facts, by what the rules method did): Eligible: 5 (an engine verdict). Skipped (unresolved facts): 2 (a fact the rules need is not yet reviewed; no verdict, not an abstention). Out of scope: 1. No usable ground or rule: 5.

Dataset tags (from the rules verdict and the reviewed issues): primary: 4 (in scope, at least one reviewed issue); abstention: 6 (out of scope, or no usable ground or rule); in scope without a reviewed issue: 1.

## Finding-level (primary)

Each engine finding is compared with the human-reviewed holding on that rule's issue (or on a rejection ground in the card's triggers). CHALLENGEABLE against a holding for the policyholder, or CONSISTENT against a holding for the insurer, agrees. CHALLENGEABLE against a holding for the insurer is **false hope**. NEED_INFO is an abstention. A finding with no reviewed issue, or a not-decided holding, is excluded and counted. Model-only methods give one verdict per case and are compared only when the case has exactly one decided reviewed issue. The abstention set is reported separately.

| Method | Agreement | False-hope rate | Abstentions | Excluded | Quote coverage | Stability | Mean latency (ms) | Cost (USD) |
|---|---|---|---|---|---|---|---|---|
| rules | Agreement n/a (0 findings) | False-hope n/a (0 findings) | Abstained 15 findings | Excluded 0 (no reviewed issue / not decided) | 100% | 100% | 0.0 | 0.0000 |

Rates are pooled over 3 repeats per case; for the rules method every repeat is identical.

### Disagreements

None.

**Limitation:** Courts weigh evidence that rules don't see, so agreement under 100% is expected. Disagreements are reported case by case.

## Case-level (secondary)

The case verdict (CHALLENGEABLE if any finding is) is compared with `case.policyholder_prevailed`, which is direction-corrected for appeals (an insurer's dismissed appeal is a policyholder win). The raw court outcome is not used. Cases whose policyholder_prevailed is unknown are excluded and counted: 0. A court may dismiss for lack of proof or on procedure, so this does not say the rule's issue was decided that way.

| Method | Agreement | False-hope rate | Abstentions |
|---|---|---|---|
| rules | Agreement n/a (0 runs) | False-hope n/a (0 runs) | Abstained 15 runs / 5 cases |

### Case-by-case
(✗ = a non-abstained verdict disagrees with who prevailed)

| case_id | prevailed | tag | rules |
|---|---|---|---|
| ik_102657860 | policyholder | abstention | NO_USABLE_GROUND_OR_RULE (no usable ground or rule) |
| ik_104709652 | insurer | abstention | NO_USABLE_GROUND_OR_RULE (no usable ground or rule) |
| ik_134085877 | insurer | skipped | SKIPPED_UNRESOLVED (skipped: unresolved facts) |
| ik_149919666 | policyholder | untagged | NEED_INFO (abstain) |
| ik_185595546 | policyholder | primary | NEED_INFO (abstain) |
| ik_55284993 | policyholder | abstention | NO_USABLE_GROUND_OR_RULE (no usable ground or rule) |
| ik_61348487 | policyholder | abstention | NO_USABLE_GROUND_OR_RULE (no usable ground or rule) |
| ik_62769190 | insurer | primary | NEED_INFO (abstain) |
| ik_72274767 | policyholder | skipped | SKIPPED_UNRESOLVED (skipped: unresolved facts) |
| ik_7246082 | policyholder | primary | NEED_INFO (abstain) |
| ik_76647766 | policyholder | primary | NEED_INFO (abstain) |
| ik_93195318 | policyholder | abstention | OUT_OF_SCOPE (out of scope) |
| ik_98838150 | policyholder | abstention | NO_USABLE_GROUND_OR_RULE (no usable ground or rule) |

## Abstention set

Cases the rules method sends to a human (out of scope, or no usable ground or rule). Safe abstention = the method produced no CHALLENGEABLE on them. For the rules method this is 100% by construction; it is informative for the model-only methods.

- rules: Safe abstention 18/18 (100%)

Out of scope: no rule in force on the claim date — sent to human review: ik_93195318 (1 case; excluded from agreement and false-hope rates).

No usable rejection ground or no rule triggered — sent to human review: ik_102657860, ik_104709652, ik_55284993, ik_61348487, ik_98838150 (5 cases; excluded from agreement and false-hope rates).

## Skipped, unresolved facts

These findings were not answered: a fact feeding the triggered card is still extracted or needs_review. They are neither engine verdicts nor abstentions and are outside every rate. Review the fact, then re-run.

- [rules] ik_134085877 SPECIFIC_WAIT: unresolved_facts:inception_date,policy_renewal_date x3
- [rules] ik_72274767 PED_WAIT_36M: unresolved_facts:ported_from_date x3

## Rule-context resolver

What the dispute is (issue family) is kept apart from which approved card can decide it. The engine ran only on candidates marked `applicable`; every other status is a reason it did not run, never a verdict. Candidate counts by status (over 13 cases): applicable 4, missing_applicability_date 1, missing_required_fact 2, no_candidate_rule 16, not_in_force 1. Family source (cases): ground 5, none 1, reviewed 7 (reviewed = human-reviewed issue family; ground = family of the reviewed rejection ground; none = neither).

Per case: families (source), then each candidate card with its status and reason.

- ik_102657860: no family (none)
  - -: no_candidate_rule: no reviewed issue family and no usable rejection ground
- ik_104709652: EXCLUSION (ground)
  - -: no_candidate_rule: issue family EXCLUSION has no candidate card (research_needed: no approved regulation card yet)
- ik_134085877: WAITING_PERIOD (ground)
  - INITIAL_30D v0: no_candidate_rule: rejection ground 'specific_waiting_period' is not a trigger of INITIAL_30D
  - PED_WAIT_36M v1: no_candidate_rule: rejection ground 'specific_waiting_period' is not a trigger of PED_WAIT_36M
  - SPECIFIC_WAIT v1: missing_required_fact: unreviewed fact(s) feed this card: inception_date, policy_renewal_date
- ik_149919666: NON_DISCLOSURE, PED_DEFINITION (reviewed)
  - MORATORIUM_60M v0: applicable: v0 in force on 2023-04-03 (policy_start_or_renewal)
  - PED_WAIT_36M v1: no_candidate_rule: rejection ground 'non_disclosure' is not a trigger of PED_WAIT_36M
- ik_185595546: PED_DEFINITION, OTHER (reviewed)
  - PED_WAIT_36M v1: applicable: v1 in force on 2024-04-21 (policy_start_or_renewal)
  - -: no_candidate_rule: issue family OTHER has no candidate card
- ik_55284993: PORTABILITY (reviewed)
  - PORTABILITY_CREDIT v1: no_candidate_rule: rejection ground 'pre_existing_disease' is not a trigger of PORTABILITY_CREDIT
- ik_61348487: EXCLUSION, PORTABILITY (reviewed)
  - -: no_candidate_rule: issue family EXCLUSION has no candidate card (research_needed: no approved regulation card yet)
  - PORTABILITY_CREDIT v1: no_candidate_rule: rejection ground 'exclusion' is not a trigger of PORTABILITY_CREDIT
- ik_62769190: OTHER, WAITING_PERIOD (reviewed)
  - -: no_candidate_rule: issue family OTHER has no candidate card
  - INITIAL_30D v0: no_candidate_rule: rejection ground 'specific_waiting_period' is not a trigger of INITIAL_30D
  - PED_WAIT_36M v1: no_candidate_rule: rejection ground 'specific_waiting_period' is not a trigger of PED_WAIT_36M
  - SPECIFIC_WAIT v0: applicable: v0 in force on 2022-12-29 (policy_start_or_renewal)
- ik_72274767: PED_DEFINITION (ground)
  - PED_WAIT_36M v1: missing_required_fact: unreviewed fact(s) feed this card: ported_from_date
- ik_7246082: WAITING_PERIOD (ground)
  - INITIAL_30D v0: no_candidate_rule: rejection ground 'specific_waiting_period' is not a trigger of INITIAL_30D
  - PED_WAIT_36M v1: no_candidate_rule: rejection ground 'specific_waiting_period' is not a trigger of PED_WAIT_36M
  - SPECIFIC_WAIT v1: missing_applicability_date: missing_claim_date
- ik_76647766: NON_DISCLOSURE (ground)
  - MORATORIUM_60M v0: applicable: v0 in force on 2023-10-23 (policy_start_or_renewal)
- ik_93195318: NON_DISCLOSURE (reviewed)
  - MORATORIUM_60M v1: not_in_force: no version in force on 2003-09-03 (in force from 2020-10-01, 2024-05-29) [warning: no policy_renewal_date: the version was chosen from inception_date, but the claim is more than a year later (a renewal may fall under a later version)]
- ik_98838150: EXCLUSION, REJECTION_PROCESS (reviewed)
  - -: no_candidate_rule: issue family EXCLUSION has no candidate card (research_needed: no approved regulation card yet)
  - REJECTION_PROCESS v1: no_candidate_rule: rejection ground 'exclusion' is not a trigger of REJECTION_PROCESS

Excluded by reviewer: ik_150681294 — government employee health scheme
Excluded by reviewer: ik_177454999 — motor insurance, not health insurance
Excluded by reviewer: ik_178058005 — government employee scheme; no substantive insurance holding in the extract
Excluded by reviewer: ik_27283437 — government employee scheme (New Health Insurance Scheme); no merits holding, adjourned to 27.01.2026
Excluded by reviewer: ik_31366034 — probable duplicate of ik_79121837 (same parties, date, outcome; text 88% similar, different IK doc id) - excluded to avoid double counting
Excluded by reviewer: ik_62761600 — out of scope; duplicate candidate of ik_177454999 (identical source sha256 and text) - motor insurance
Excluded by reviewer: ik_82916610 — no individual health-insurance claim holding

Not health: ik_140785688 (life)
Not health: ik_177454999 (motor)
Not health: ik_62761600 (motor)

Product line unknown: 318 cases not evaluated (ik_100163329, ik_100307322, ik_100398990, ik_10114899, ik_102412691, ik_102497590, ik_102973569, ik_102981245, ik_103876287, ik_104390725, ik_104568871, ik_104848748, ik_105374727, ik_105913037, ik_106163131, ik_106649628, ik_107178691, ik_107398954, ik_107405028, ik_107708603, ik_108596492, ik_109132496, ik_109299264, ik_109706666, ik_109761180, ik_111306562, ik_111331874, ik_112208826, ik_113175381, ik_113926899, ik_115005625, ik_11549813, ik_115659176, ik_11649795, ik_117117018, ik_117378259, ik_117472771, ik_117814436, ik_118487269, ik_118880376, ik_119204271, ik_119253158, ik_119737848, ik_120499068, ik_122701523, ik_123288159, ik_123387804, ik_123875955, ik_12432417, ik_125286012, ik_125724780, ik_125951631, ik_127843002, ik_128511750, ik_12937857, ik_130088332, ik_130349700, ik_130875469, ik_131022417, ik_131132601, ik_131331184, ik_131649921, ik_131951612, ik_133334246, ik_133359499, ik_133400669, ik_134564067, ik_135069843, ik_135438575, ik_135566612, ik_136520640, ik_137915333, ik_138273655, ik_138408739, ik_138794738, ik_139780985, ik_139974115, ik_140115826, ik_140492203, ik_141158899, ik_141803965, ik_143521581, ik_143666170, ik_144697234, ik_145123262, ik_146663887, ik_146735334, ik_148103266, ik_148410336, ik_148660792, ik_149965379, ik_150589960, ik_151284501, ik_151974680, ik_152732885, ik_152803937, ik_153431446, ik_156348628, ik_157874010, ik_157877802, ik_158349174, ik_158657466, ik_158677786, ik_160715664, ik_160893203, ik_161305151, ik_161540018, ik_162741725, ik_162972184, ik_16346908, ik_164653334, ik_164811762, ik_164834067, ik_165802414, ik_16678186, ik_167276298, ik_167376266, ik_167453977, ik_167508839, ik_167592546, ik_167792069, ik_169369549, ik_169879949, ik_170498641, ik_170514646, ik_17139940, ik_171685210, ik_173425574, ik_174552066, ik_175210408, ik_175248015, ik_176415131, ik_177407808, ik_177485548, ik_180069344, ik_18027577, ik_181110721, ik_181215089, ik_183418849, ik_184111187, ik_184128756, ik_184855352, ik_185680980, ik_186238150, ik_186917570, ik_187400998, ik_188584042, ik_188845601, ik_189167506, ik_189221190, ik_189463998, ik_191571541, ik_192144672, ik_19308481, ik_193384457, ik_193498478, ik_193679172, ik_194404147, ik_194878045, ik_196877102, ik_196953875, ik_197417274, ik_197911738, ik_199068701, ik_20276574, ik_21049415, ik_21061594, ik_21365755, ik_21517243, ik_21654386, ik_2206518, ik_22687480, ik_23313514, ik_23672877, ik_24534500, ik_26716278, ik_27836890, ik_28261863, ik_28862517, ik_29077387, ik_29107180, ik_29529792, ik_30854290, ik_31097958, ik_32401693, ik_33222410, ik_33698187, ik_3370200, ik_33917328, ik_34137144, ik_34951726, ik_36445160, ik_36967167, ik_37271317, ik_37293473, ik_37348112, ik_37643316, ik_37691125, ik_37939570, ik_38914684, ik_39036173, ik_40263607, ik_40970353, ik_41583238, ik_42251940, ik_42793945, ik_43989502, ik_45035350, ik_45310153, ik_45621283, ik_46832930, ik_46873238, ik_47341251, ik_47354779, ik_47487294, ik_47881076, ik_48260418, ik_48814215, ik_49114700, ik_49300754, ik_50263722, ik_52717582, ik_52925665, ik_53277852, ik_53598380, ik_53860856, ik_54062296, ik_54614705, ik_54700271, ik_56021797, ik_56926251, ik_5743116, ik_57839283, ik_58115892, ik_58258439, ik_58630367, ik_5900201, ik_5925362, ik_60005545, ik_60502752, ik_60637165, ik_61214300, ik_61879826, ik_62013032, ik_63134342, ik_63588295, ik_63692738, ik_64091033, ik_65062089, ik_65871771, ik_66647063, ik_66726613, ik_67662785, ik_67752082, ik_68060069, ik_68399725, ik_68533112, ik_69446873, ik_70405813, ik_70697559, ik_70880700, ik_71261883, ik_71293872, ik_71560286, ik_71922853, ik_72864917, ik_74074664, ik_74180243, ik_75454202, ik_75525361, ik_75809896, ik_75842068, ik_77022178, ik_77070879, ik_77395924, ik_78208874, ik_78627786, ik_78928812, ik_7984281, ik_80212359, ik_80318304, ik_80810865, ik_81072498, ik_81565183, ik_81978786, ik_82117383, ik_82908347, ik_8339644, ik_83979153, ik_84614711, ik_84863248, ik_85609732, ik_86719691, ik_87285824, ik_87867889, ik_87882563, ik_88425065, ik_89494825, ik_91085840, ik_91406064, ik_91693144, ik_9225930, ik_92350673, ik_9329076, ik_94121919, ik_94931685, ik_95375497, ik_95511474, ik_95618009, ik_95754556, ik_97584708, ik_97792751, ik_98576933, ik_98797323, ik_99126097, ik_99352395, ik_99455926, ik_9993313); set one with `cases set-product-line`.
