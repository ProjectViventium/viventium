# Background Activation Model Eval

<!-- qa-evidence-exempt: Machine-generated activation-eval ledger retained as supporting evidence; user-path acceptance lives in the feature run report. -->

- Mode: live
- Status: passed
- Family: background_activation_routing
- Selected cases: 67
- Selected cortex targets: 11
- Repetitions: 1
- Pass: 737/737
- End-to-end required recall: 100.0%
- Semantic required recall (completed calls): 100.0%
- Activation precision: 100.0%
- False positives: 0
- False negatives: 0
- Completed calls: 737/737 (100.0%)
- Unavailable required calls: 0
- Timeout/provider errors: 737
- Inconsistent repeated semantic decisions: 0
- Optional allowed-activation variance: 0
- Availability flaps across repetitions: 0
- Classifier latency p50/p95/max: 551/779/1319 ms
- Wall duration: 54129 ms
- Source bundle hash: 513d52ea409b6618
- Prompt bank hash: 26831f271c6cb9a7

Transport note: `Timeout/provider errors` counts failed provider attempts, not failed classifier
decisions. In this run every configured Groq/Qwen primary attempt was provider-rejected; the declared
xAI fallback returned all 737 valid decisions. Semantic/fallback acceptance passed, while primary-
provider health is degraded and remains a release-health follow-up.

## Per-cortex metrics

| Cortex key | Pass | E2E recall | Semantic recall | Precision | FP | FN | Unavailable required | p50 | p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| background_analysis | 67/67 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 569 ms | 721 ms |
| confirmation_bias | 67/67 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 562 ms | 731 ms |
| red_team | 67/67 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 558 ms | 857 ms |
| deep_research | 67/67 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 533 ms | 748 ms |
| ms365 | 67/67 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 547 ms | 748 ms |
| parietal | 67/67 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 557 ms | 771 ms |
| pattern_recognition | 67/67 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 532 ms | 831 ms |
| emotional_resonance | 67/67 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 569 ms | 904 ms |
| strategic_planning | 67/67 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 552 ms | 768 ms |
| support | 67/67 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 550 ms | 818 ms |
| google | 67/67 | 100.0% | 100.0% | 100.0% | 0 | 0 | 0 | 521 ms | 1110 ms |

Raw prompts, responses, account identifiers, and provider request details are private-only.
