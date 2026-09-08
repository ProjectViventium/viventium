# Viventium documentation

Viventium's active product stack is `viventium_v0_4/`.

<a id="read-order"></a>

## Start here

1. [Key principles and product rules](requirements_and_learnings/01_Key_Principles.md)
2. [Architecture overview](architecture/overview.md)
3. [Systems map](architecture/systems-map.md)
4. [Install and operate](how-to/install-and-operate.md)
5. [Upgrade, restore, and migrate](how-to/upgrade-and-migrate.md)
6. [Contributor setup](04_SETUP_GUIDE.md#contributor-setup)
7. [QA catalog](../qa/catalog.yaml)

**GOV-008:** This read order links each capability to its owning detailed contracts and acceptance.

## Capabilities and acceptance

| Capability | Start here | QA |
| --- | --- | --- |
| Background cognition | [background cognition](requirements_and_learnings/02_Background_Agents.md) | [cases](../qa/background-cognition/cases.yaml) |
| Telegram channels | [Telegram](requirements_and_learnings/03_Telegram_Bridge.md), [scheduling UX](requirements_and_learnings/25_Scheduling_Telegram_UX_Fixes.md) | [cases](../qa/telegram-channels/cases.yaml) |
| Runtime, install, and release | [runtime-install-release](requirements_and_learnings/capabilities/runtime-install-release.md) | [cases](../qa/runtime-install-release/cases.yaml) |
| Voice | [voice](requirements_and_learnings/capabilities/voice.md) | [cases](../qa/voice/cases.yaml) |
| Scheduling and continuity | [main-scheduling-continuity](requirements_and_learnings/capabilities/main-scheduling-continuity.md) | [cases](../qa/main-scheduling-continuity/cases.yaml) |
| Interaction delivery | [interaction-delivery](requirements_and_learnings/capabilities/interaction-delivery.md) | [cases](../qa/interaction-delivery/cases.yaml) |
| Parallel Work | [parallel-work](requirements_and_learnings/capabilities/parallel-work.md) | [cases](../qa/parallel-work/cases.yaml) |
| GlassHive | [glasshive](requirements_and_learnings/capabilities/glasshive.md) | [cases](../qa/glasshive/cases.yaml) |
| Prompt Workbench | [prompt-workbench](requirements_and_learnings/capabilities/prompt-workbench.md) | [cases](../qa/prompt-workbench/cases.yaml) |
| Memory and recall | [memory-recall-transcripts](requirements_and_learnings/capabilities/memory-recall-transcripts.md) | [cases](../qa/memory-recall-transcripts/cases.yaml) |
| Feelings and truth seeking | [feelings-truth-seeking](requirements_and_learnings/capabilities/feelings-truth-seeking.md) | [cases](../qa/feelings-truth-seeking/cases.yaml) |
| Connected tools and search | [connected-tools-search](requirements_and_learnings/capabilities/connected-tools-search.md) | [cases](../qa/connected-tools-search/cases.yaml) |
| Interface and brand | [interface-brand](requirements_and_learnings/capabilities/interface-brand.md) | [cases](../qa/interface-brand/cases.yaml) |
| Periphery insights | [periphery insights](requirements_and_learnings/53_Viventium_Periphery_Nightly_Insights.md) | [cases](../qa/periphery-insights/cases.yaml) |
| Health and WHOOP | [health-whoop](requirements_and_learnings/capabilities/health-whoop.md) | [cases](../qa/health-whoop/cases.yaml) |
| Life | [life](requirements_and_learnings/capabilities/life.md) | [cases](../qa/life/cases.yaml) |

Read the global principles, then the capability page, its detailed contracts, and the owning QA
journey. The retained numeric contracts and detailed case banks remain active during lossless owner
reconciliation. The shorter routes do not retire requirements, stable aliases, or unique tests.
Do not use historical reports as current status.

Background cognition, Telegram, and periphery insights remain at their linked legacy owners until
their exact loss, consumer, and safety gates pass. Runtime implementation detail lives in
[v0.4 component documentation](../viventium_v0_4/docs/README.md); shared repository rules live in
[AGENTS.md](../AGENTS.md).

## Retained entrypoints

- [Source setup](04_SETUP_GUIDE.md), [environment](05_ENVIRONMENT.md), and
  [troubleshooting](06_TROUBLESHOOTING.md) retain their detailed procedures.
- [Runtime feature and QA map](requirements_and_learnings/45_Runtime_Feature_QA_Map.md)
  retains detailed legacy ownership and compatibility links.
- [Migration context](07_MIGRATION_GUIDE.md) retains the historical stack comparison;
  v0.4 is the active product.

## Document status

Capability routing does not certify completion. Candidate-bound QA reports own execution results;
unresolved owner, surface, seam, and planned acceptance mappings remain open until reviewed.
