# Key Coding Principles for Viventium

**Purpose**: This document serves as the definitive reference for all AI assistants working on this codebase. These principles must be followed in every interaction to ensure consistent, high-quality development.

---

## 🎯 Core Development Principles

### 1. Beautifully Simple and Efficient
- **Do not overcomplicate things** - Seek elegant, efficient solutions
- Study the codebase, components, and research web for inspiration to identify the most beautiful and efficient way to implement features
- Code must be user-friendly for other engineers and developers
- Make code dynamic - **avoid hardcoding things**
- **MOST IMPORTANTLY**: **SEPARATION OF CONCERNS PRINCIPLE MUST BE FOLLOWED AT ALL TIMES** to maintain a clear modular design so the project does not turn into entangled spaghetti code

### 2. Documentation First
- Document steps in `.md` format in `docs/` folder
- Ensure compatibility and easiness for other developers to edit and extend code without headache
- When developing new features: create unit tests, run them, analyze failures, and make necessary adjustments

### 2.1 Repository Boundary Discipline
- `viventium_core` is the product/public-facing engineering surface
- the dedicated private companion repo is the only place for personal state, private prompts, private docs, backups, snapshots, machine-specific runtime data, and explicit user-approved secret-bearing transfer files
- the dedicated enterprise deployment repo is the only place for deployment-as-a-service code, enterprise overlays, and operator runbooks
- the private and enterprise companion repos may live locally either beside `viventium_core` or under its root for unified-workspace convenience, but when nested they must remain separate git repos, ignored by the main repo, and excluded from every public export or tracked public surface
- If a file is not required to install, run, test, document, or release the v0.4 product surface, it does not belong in the tracked public-facing repo roots or any publishable export generated from them
- When in doubt:
  - personal / confidential / owner-specific / machine-specific -> private repo
  - deployment / infra / customer-ops / enterprise-only -> enterprise repo
  - installer / CLI / canonical config / tests / docs / launch wrappers / product code -> `viventium_core`

### 2.2 Canonical Config Discipline
- End-user configuration must converge on one human-facing source of truth:
  - `~/Library/Application Support/Viventium/config.yaml`
- Service-local `.env` files and YAML fragments are generated artifacts, not hand-maintained sources of truth
- Legacy repo-local `.env*` files are compatibility inputs for the private owner workflow only and must not become the public install story
- If a private machine-transfer or restore workflow needs explicit secrets, keep those files only in the private companion repo and document the exception there

### 2.3 Auth and Upgrade Discipline
- Do not drift into generic LibreChat credential behavior when Viventium has a documented product rule
- Provider auth precedence must stay:
  - user connected account first when supported and available
  - explicit API key from canonical/generated runtime env next
  - otherwise show a clear action to connect the account or provide the key
- Do not silently seed or expose models that the current configured auth mode cannot actually use
- Local installer and runtime health checks must be honest about mixed-mode dependencies:
  - if a feature still needs Docker Desktop in a nominally native install, say so before startup
- `bin/viventium upgrade` is the canonical path for refreshing a local install:
  - pull the current branch
  - detect/install new prerequisites in one batch
  - refresh pinned components
  - recompile generated runtime files
  - rerun doctor before restart

### 2.4 Installer and QA Discipline
- A clean-machine install must be proven through the public product paths only:
  - `./install.sh`
  - `bin/viventium upgrade`
  - `bin/viventium start`
- Do not "save" a broken test machine with hand edits inside App Support, local component trees, Mongo, or service state and then claim the installer works
- If a nested component change is required for installer correctness on private branches, the shipped private snapshot must also be refreshed:
  - component source
  - the shipped component snapshot manifest
  - `components.lock.json`
- Per-machine integrations must come from canonical config or approved transfer presets, not from reusing the developer machine's live tokens:
  - example: Telegram bot tokens must be machine/environment-specific when concurrent bot sessions would conflict
- Installer acceptance is not complete until the product is validated from another device or machine over LAN/public origin where relevant:
  - API/config inspection alone is insufficient
  - real browser QA must confirm the visible surface, login flow, provider picker, connected-account actions, and remote call routing
- Cold-start behavior must be treated as part of product quality:
  - honest progress and timeouts for first-build Docker paths
  - honest health checks during first package builds
  - no false "healthy" claim before the actual user-facing surfaces respond

### 3. Study Before Acting
- **Do not make assumptions** about the codebase, components, or anything
- **You must provide proof and references** to truth in codebase and online resources to ensure you are grounded in reality and not making things up
- When requesting new features: **study the project systematically** to map it out and understand the best place to add the new feature in concert with existing codebase and behavior
- Strictly follow a modular design that is efficient, beautifully simple, does not overcomplicate things, and perfectly gets the job done
- **Avoid recreating the wheel** by analyzing the components and modules you can use that are either already in the project or can be imported

---

## 📖 Requirements & Learnings Directory

### Purpose of `docs/requirements_and_learnings/`
The `docs/requirements_and_learnings/` directory serves as the **central repository** for all key requirements and learnings across the project. This directory ensures that all feature-specific knowledge, requirements, specifications, and learnings are consolidated in one place.

### Critical Rules:

#### 1. Single Source of Truth Per Feature
- **DO NOT EVER LET THERE BE MULTIPLE DOCUMENTS FOR THE SAME FEATURE / REQUIREMENT**
- Instead: **compile, update, and add** to existing documents
- Each feature/concept should have exactly **one comprehensive document** that contains everything about it

#### 2. When Working on New Features/Projects
- **All documents in this directory must be added/updated** when working on new features or projects
- If the new feature/project has key requirements or learnings tied to a single concept or feature, they **must be documented here**
- Example: If working on background agents and how they surface results:
  - User's requirements → Document in the background agents document
  - Your learnings → Add to the same document
  - Specifications → Include in the same document
  - Use cases → Document in the same document

#### 3. Document Completeness Standard
A developer referring to a single document about a respective feature **must perfectly become up to speed** about:
- ✅ **Requirements** - What the feature must do
- ✅ **Specifications** - How it should work technically
- ✅ **Use Cases** - When and why to use it
- ✅ **Learnings** - What was discovered during development
- ✅ **Edge Cases** - Known limitations or special considerations
- ✅ **Integration Points** - How it connects with other parts of the system

#### 4. Document Naming Convention
- Use descriptive, feature-specific names (e.g., `02_Background_Agents.md`, `03_Memory_System.md`)
- Number documents for easy reference (e.g., `01_`, `02_`, `03_`)
- Keep names concise but clear

#### 5. Maintenance Responsibility
- When adding new requirements or learnings, **first check if a document exists** for that feature/concept
- If it exists: **update the existing document** - do not create a new one
- If it doesn't exist: **create a new document** following the naming convention
- Always ensure the document remains comprehensive and up-to-date

### Example Workflow:
```
1. Starting work on "Background Agents" feature
   → Check: Does `02_Background_Agents.md` exist?
   
2. If YES:
   → Read existing document
   → Add new requirements/learnings to it
   → Update specifications if changed
   
3. If NO:
   → Create `02_Background_Agents.md`
   → Document all requirements, specifications, use cases, and learnings
   
4. Result: One complete document that tells the full story
```

### Benefits:
- ✅ **No information fragmentation** - Everything about a feature in one place
- ✅ **Easy onboarding** - New developers can understand features quickly
- ✅ **Knowledge preservation** - Learnings don't get lost
- ✅ **Consistency** - Single source prevents conflicting information
- ✅ **Maintainability** - Easier to keep documentation current

---

## 🔍 Root Cause Analysis Methodology

### When There Are Issues:
1. **Break down the problem** to the smallest steps and things you can - small and full coverage
2. **Go to first principle thinking** and truly nail down the issue
3. **Stop assuming you have a fix and jumping to the build!**
4. **You need to have complete concrete evidence** only after you've gone through EVERYTHING
5. **Then finally refer to web** for additional context if needed
6. **LEAVE NO STONE UNTURNED**

### Priority-Based Approach
- Address issues in priority order based on severity (Critical → High → Medium → Low)
- Create comprehensive analysis documents before implementation
- Validate, test, and explore fixes before implementing

---

## 📚 Codebase Study Requirements

### General Rules:
- **Do not overfit!** Read the documentation priority to any change for both `viventium_v0_3_py/viventium_v1` and `viventium_v0_4` (we are no longer updating v0_3, so assume features and fixes and changes are all meant for viventium_v0_4)
- Ask yourself, based on the codebase and docs, what other parallel usecases are supported? and would my plan or solution fix only this? or the full scope for various cases. 
- Based on documentation, gain the background and context before making changes
- **Do not patch** Do a full analysis of components and things that are involved so that you fix the root cause without breaking any other functionality at its root, instead of patch of patch!
- **Do Not re-invent the wheel** First, study the code base and root project files to find similar things that you can use. Second, search web, online github repositories, forums, online docs, community notes, and various things. (Because reality is... everything has already been done in many ways by many people and if you dont find exactly the trusted reliable answer, you will find close inspiration to use)
- **Study the codebase** and understand the existing logic, flow, patterns, and principles
- Make changes the proper way in full, covering edge cases
- Ensure changes are consistent with the existing codebase and principles

### Before Any Change:
- Understand existing components, patterns, and abstractions
- Identify where existing functionality can be reused
- Map out the proper integration points
- Ensure minimal changes that leverage existing code

### Runtime vs Prompt Decision Gate (MANDATORY)
- **Classify output ownership first** before proposing fixes:
  - `runtime-generated` = deterministic strings/behavior from code paths (controllers, services, dispatch, adapters)
  - `model-generated` = LLM output influenced by prompts/configuration
- **Prompt-change gate**:
  - If behavior is `runtime-generated`, fix the runtime path first
  - Prompt/config edits are allowed only when root cause is `model-generated`
- **Do not use prompt edits to suppress deterministic runtime placeholders**; fix the source code path emitting them
- **Provide a concrete causal chain** for every issue: `trigger -> transformation -> user-visible output`, with file:line references
- **Plumbing budget rule**: before adding new request fields/routes/config keys, prove existing context signals are insufficient (e.g., existing ids/metadata already flowing)
- **Cross-surface regression check**: evaluate impact across Telegram, Scheduler, LibreChat Web UI, and Voice before finalizing
- **Activation classifier rule**:
  - If a background-agent activation bug is `model-generated`, fix the user-configured activation prompt/source-of-truth first and prove it with evals.
  - Do **not** add runtime string blacklists or message-specific "if text contains X, suppress agent Y" gates for classifier false positives.
  - Runtime changes are allowed only for structural activation plumbing defects (for example: wrong context assembly, broken latest-turn extraction, missing fallback wiring, or bad scope metadata propagation). This bullet does **not** override the CRITICAL RULE below.
  - For productivity agents specifically, "reply/respond/say/return" must never be hardcoded as special-case deny words in code; the classifier prompt must distinguish chat-format instructions from real email/content actions.
  - Do **not** infer agent role from hardcoded agent names, cortex titles, or tool names when explicit config metadata can carry the intent. User systems may rename agents, replace tools, or define different specialist shapes entirely.

### CRITICAL RULE: No Hardcoded NLU in Runtime Code
- Intent detection, provider clarification, and history classification must be owned by LLM activation classifiers plus YAML-configured activation prompts.
- Runtime code must **not** use regex, substring matching, or hand-written NLU helpers on user/assistant message text to:
  - decide cortex activation
  - classify provider intent such as Gmail / Outlook / Ms365
  - pre-filter or rewrite activation history based on guessed semantics
  - create "deterministic fast paths" that bypass the activation classifier
- Allowed runtime string handling is limited to deterministic structural parsing:
  - identifier extraction such as URLs, file IDs, email addresses, or protocol strings
  - message metadata such as role, timestamp, length, attachment presence, or configured scope keys
  - message-content normalization needed to read stored text blocks safely
- If a fix requires teaching the system to understand new phrasing, the change belongs in `viventium_v0_4/LibreChat/viventium/source_of_truth/<env>.viventium-agents.yaml`, not in JavaScript.
- If classifier reliability is the issue, fix it with `activation.fallbacks` and live eval coverage, not with heuristic runtime preempts.
- Any PR that reintroduces regex or keyword NLU in runtime routing layers is a critical review block unless it proves the logic is deterministic-by-construction and not user-intent classification.

### User-Level Configurations and System Prompts
- **Do not overfit user-level designs** such as system prompts and configurations
- System prompts are not a substitute for fixing deterministic runtime behavior in backend pipelines
- Viventium is an agentic platform with a real agent builder, editable background cortex configs, and configurable activation models:
  - use those config surfaces instead of sneaking business logic into runtime code when the problem is classifier behavior
  - when a prompt/config change is made, add/update reusable QA docs and automated regression coverage so future engineers can verify the intended behavior without rediscovering it
- Before modifying or creating system prompts/configurations, **always pull the latest user-level configs** to understand current state:
  ```bash
  node viventium_v0_4/LibreChat/scripts/viventium-sync-agents.js pull
  ```
- This provides visibility into the inner workings of user-level agent configurations, system prompts, and related settings
- Before any push/update to live user-level agents, **always run a live-vs-source comparison** and review:
  - A = current live user-level agent bundle
  - B = tracked source-of-truth bundle
  - C = current repo/source-of-truth edits that are not yet in live
- Present the A/B/C drift to the user before syncing when there is any difference in user-managed
  fields such as instructions, conversation starters, tools, provider/model, or background cortex config.
- Treat live user edits as protected state until they are intentionally reconciled. Do **not** assume
  the tracked scaffold should automatically overwrite live user-managed config.
- If the symptom is capability availability rather than prompt text alone, inspect adjacent
  scaffold/runtime config too (for example `viventium_v0_4/LibreChat/viventium/source_of_truth/<env>.librechat.yaml`).
  Global toggles such as `interface.webSearch` can disable behavior even when the agent bundle still
  contains the expected tool entries.
- Non-dry-run sync should fail closed when reviewed live-vs-source drift still exists. Only proceed
  with an explicit acknowledgement such as `--compare-reviewed` after the A/B/C diff has been shown
  and intentionally accepted.
- When syncing agent model/provider fields into a live local Mongo surface, the sync path must honor
  the canonical generated runtime env. Do not treat the raw git-tracked bundle as the live model
  truth when the runtime compiler/seed path defines the actual assignment for that machine.
- To update user-level configs:
  1. Pull the latest configs: `viventium-sync-agents.js pull --env=<env>`
  2. Compare live vs source-of-truth vs current repo edits: `viventium-sync-agents.js compare --env=<env>`
  3. Edit the **git-tracked source-of-truth** file for clean diffs:
     - `viventium_v0_4/LibreChat/viventium/source_of_truth/<env>.viventium-agents.yaml`
     - (Snapshots are still written under `.viventium/artifacts/agents-sync/runs/<timestamp>-<env>/viventium-agents.yaml`)
  4. Push the updated configs using the **correct push mode**:
    - `viventium-sync-agents.js push --prompts-only --env=<env>` — for prompt/instruction/cortex activation changes
     - `viventium-sync-agents.js push --activation-config-only --activation-fields=prompt,model,provider,fallbacks,intent_scope --env=<env>` — for selected background cortex activation config changes
     - `viventium-sync-agents.js push --model-config-only --env=<env>` — for provider/model updates only
     - `viventium-sync-agents.js push --env=<env>` — full push (DANGEROUS, see warning below)
- `env` is set via `--env=<env>` (or `VIVENTIUM_ENV=<env>`); use the target runtime environment name for pull/push operations.
- This ensures you're working with the actual deployed configurations, not assumptions
- Canonical artifact/snapshot path conventions are documented in `docs/requirements_and_learnings/27_Artifact_Storage_Standard.md`

#### CRITICAL: Push Safety Rules (Learned 2026-02-15)
- **ALWAYS use `--prompts-only` for prompt/instruction/cortex activation changes**. This is the safe mode that skips `tools`, `model`, `provider`, and other UI-managed fields.
- **ALWAYS review `compare --env=<env>` output before push**. If live user config differs from the tracked scaffold on user-managed fields, reconcile intentionally and present that drift to the user before applying changes.
- **NEVER use default `push` (without `--prompts-only`) unless you are certain the YAML `tools` arrays exactly match the live target environment state**. Default push overwrites ALL fields including `tools`, which breaks MCP server links that were configured via the LibreChat UI. The user then has to manually re-add each MCP server one by one.
- **Why it breaks**: Default push writes 16 fields including `tools` (string arrays like `sys__server__sys_mcp_scheduling-cortex`). If the YAML was pulled at time T1 and someone changed MCP tools via UI between T1 and push at T2, the stale T1 tools array overwrites the UI changes.
- **Do not blindly overwrite live instructions or conversation starters either**. A stale scaffold can erase user-authored main-agent or background-agent prompt edits just as easily as it can erase tools.
- **`--prompts-only` safe fields**: `id`, `name`, `description`, `instructions`, `conversation_starters`, `background_cortices` (with safe merge that only touches `activation.enabled`, `activation.prompt`, `activation.confidence_threshold`).
- **`--activation-config-only` safe fields**: only `background_cortices`, with an allowlist merge over `activation.enabled`, `activation.prompt`, `activation.confidence_threshold`, `activation.model`, `activation.provider`, `activation.cooldown_ms`, `activation.max_history`, and `activation.intent_scope`. Use `--activation-fields=...` to narrow further.
- **`--model-config-only` safe fields**: only top-level agent model fields (`provider`, `model`, `model_parameters`, `voice_llm_model`, `voice_llm_provider`). Use this when correcting stale model drift without touching tools or prompts.
- **Use `--agent-ids=...` for surgical pushes** when only a subset of background agents changed. This keeps model/prompt fixes narrowly scoped instead of rewriting the whole roster.
- **Always dry-run first**: `push --prompts-only --dry-run --env=<env>` to preview changes before applying.
- Safety UX rule for operator tooling:
  - `--help`, `-h`, and explicit usage/preview paths must be side-effect free
  - a help flag must never execute a real pull/push/write path
  - reason: sync tooling is used in high-risk configuration surfaces where one mistaken invocation can overwrite live agent state
- For activation routing/plumbing, prefer a small explicit config key such as `activation.intent_scope` over runtime title/agent-name inference.
- Runtime ownership rule for agentic systems:
  - legal: explicit config metadata (`activation.intent_scope`, selected model/provider fields, prompt text, thresholds)
  - legal: generic runtime plumbing that derives provider intent from canonical config tokens such as `productivity_<scope>` without inspecting agent names or prompt titles
  - illegal: hardcoded business logic keyed to one generated agent id, one agent title, one tool name suffix, or one specific user prompt example
  - illegal: runtime alias maps that silently treat free-form provider/tool labels (`gmail`, `google`, `outlook`, `onedrive`, etc.) as if they were valid activation scope keys when the source-of-truth config already defines canonical scope tokens
  - illegal: accepting loose provider aliases in helper-context isolation logic (`gmail`, `outlook`, `google`, `microsoft365`) when the canonical activation scope token is already available from config or a documented legacy header
  - illegal: env-override ownership rules that match cortex ids/names by substring to decide activation hold or specialist ownership when the same decision can be made from structured config metadata
  - illegal: substring-based runtime renaming of built-in agent display names (for example rewriting `Parietal Cortex` into some generic label) when the source-of-truth config already carries the intended user-facing name
  - reason: Viventium is an agent platform with user-managed agents and tools. The AI/config should stay the brain and decider; runtime code should only provide generic plumbing.
- **After push, restart the target LibreChat runtime** so it reloads from MongoDB. Environment-specific deployment commands belong in the private deployment runbooks, not the public source-of-truth doc.

#### Model Governance Rule (Launch-Ready Baseline)
- Out-of-the-box Viventium background agents must stay within the current launch-ready model families unless a newer documented evaluation replaces them:
  - `anthropic / claude-sonnet-4-6`
  - `anthropic / claude-opus-4-6`
  - `openAI / gpt-5.4`
- Foundation provider rule:
  - Groq remains required for activation detection
  - at least one of `OpenAI` or `Anthropic` must be configured for main/background execution on install
  - do not treat `x_ai` alone as a sufficient built-in background-agent foundation for launch-ready installs
- Do **not** silently drift back to older defaults such as `gpt-4o` or `gpt-4o-mini` just because a pull or reset changed stored config.
- The same rule applies to secondary runtime paths such as deferred/background follow-up generation:
  - if agent metadata is incomplete, the fallback must still come from the approved launch-ready families above
  - do not hide stale-model drift inside "just a fallback" code paths
- Model selection must be **environment-proven**, not wishful:
  - choose from the allowed latest families above
  - prove the chosen family actually works in the target environment with real runs
  - if one preferred provider/model is unavailable, move to another allowed latest family rather than regressing to stale models
- Before changing live agent models:
  - capture a timestamped snapshot of the pulled agent bundle
  - back up the tracked source-of-truth file
  - use `--model-config-only --agent-ids=...` for surgical updates
  - treat raw tracked source-of-truth as the default sync input; runtime-aware rewrite is opt-in only via `--runtime-aware`
- Multi-source authority rule for background-agent model work:
  - the authoritative launch baseline is the combination of:
    - the public git-tracked source-of-truth bundle
    - the latest pulled live bundle for the target environment
    - the current governance/contract tests
  - private curated snapshots are evidence and backups, not a higher source of truth
  - if the private curated file drifts away from the public/live/tested baseline, snapshot it first
    and then reconcile it back to the proven baseline instead of treating the drift as a new truth
  - reason: private drift can silently reintroduce stale provider/model assignments even when the
    public bundle, live runtime, and QA docs already agree on the correct launch-ready roster
- Contract-test rule:
  - keep a release test that validates the shipped background-agent roster, the QA catalog,
    the coverage matrix, and the signoff manifest stay in sync
  - keep a release or API test that rejects stale built-in execution or activation families before
    they can quietly return
  - keep a cross-contract check between the Python release guard and the JS runtime-model helper so
    the documented launch-ready families cannot drift apart between source-of-truth validation and
    live Mongo rewrite logic
  - reason: model drift and QA drift are both launch regressions, even when the app still boots
- Inventory hygiene rule:
  - local model-picker inventories and helper/title models must also stay aligned with the current approved families
  - example: Groq inventory/title defaults should prefer the documented Llama 4 activation family, not stale Llama 3.x leftovers
  - reason: stale picker defaults and title-model entries quietly reintroduce old-model drift even when the agent source-of-truth bundle is correct
- If a required provider session drops locally (for example OpenAI account disconnects in the desktop app), reconnect the provider and then re-run the real product QA flows. Do not "fix" the situation by silently downgrading shipped agent models to stale families such as `gpt-4o`.

#### Fail-Loud Source-Of-Truth Rule
- When an operator tool needs a default bundle or schedule input, prefer explicit current
  source-of-truth files or verified reviewed artifacts only.
- Illegal behavior:
  - silently falling back to a guessed `tmp/` export
  - silently falling back to a guessed legacy `scripts/` yaml
  - silently accepting a missing reviewed artifact and then reviving stale historical config
- Legal behavior:
  - explicit operator-provided path
  - tracked source-of-truth path
  - reviewed artifact path only when the required file truly exists
  - otherwise fail loudly with a clear operator error
- Reason:
  - silent fallback is a hidden configuration fork and causes exactly the kind of stale-model,
    stale-prompt, and stale-tooling regressions this project is trying to eliminate.

#### Operator Communication Rule
- When explaining an issue to the product owner or operator:
  - translate internal names (`executeCortex`, `loadCustomConfig`, validation flags, etc.) into
    plain product language first
  - always include:
    - what happened
    - why it matters to the operator
    - recommended action
    - important alternative options and consequences when there is a tradeoff
- Internal function names are developer evidence, not user-facing explanations.

### Deployment Env Parity (LibreChat Google/Gemini)
- LibreChat's Google endpoint **requires `GOOGLE_KEY`** (or a service account) to enable Gemini models
- **When using Gemini API keys, set `GOOGLE_KEY` to the same secret as `GEMINI_API_KEY`**
- LibreChat Agents (LangChain Google provider via `@librechat/agents`) **requires `GOOGLE_API_KEY`**
  - Set `GOOGLE_API_KEY` to the same secret as `GOOGLE_KEY`/`GEMINI_API_KEY` for full parity (main agents + follow-ups)
- Keep `GOOGLE_MODELS` aligned with enabled Gemini models to avoid broken UI entries

### Deployment Env Parity (Model Lists)
- **`<PROVIDER>_MODELS` env vars take absolute priority** over hard-coded model lists in LibreChat code
- When set, `getAnthropicModels()` / `getGoogleModels()` / etc. return `splitAndTrim(process.env.<PROVIDER>_MODELS)` directly
- **When adding new models** (e.g., `claude-sonnet-4-6`), update the env var on the container — no code changes or rebuild needed:
  ```bash
  update the target runtime env so `ANTHROPIC_MODELS` includes the new values
  ```
- **Also update the environment-specific deploy template** to keep the hosted config in sync with live state
- Key env vars: `ANTHROPIC_MODELS`, `GOOGLE_MODELS`, `XAI_MODELS`, `OPENAI_MODELS`
- Hosted environment-specific model rollout details live in the private deployment documentation.

---

## 🔧 Open Source Project Handling

### VIVENTIUM Modifications Tracking
- This project is based on multiple open source projects
- **All changes to open source projects must be tracked** with comments wrapping (must also include detailed explanation of the change and reason behind it and its purpose and feature so when we are applying these changes onto a new version of the original repositories, we would have full context and background there):
  ```
  VIVENTIUM START
  Description of change / feature 
  Explanation of the approach / the why 

  [your changes]
  VIVENTIUM END
  ```

  - Note: if the file is created by us and was not originally in the repository, the VIVENTIUM START comment should only be at the top / beginning of the file, and hennce if you create a new file in the projects, ensure top of the file has the full VIVENTIUM START and documentation text there. On the otherhand, if you see a file starts with VIVENTIUM comment at the top, then you must not put VIVENTIUM START / END commants in the middle of that file.

- **Prefer creating new files and packages** rather than modifying many places that will cause a lot of merge conflicts

### Upstream Changes Management (IF USER SPECIFICALLY REQUESTS UPDATING FROM UPSTREAM)
- **NEVER pull code changes directly** - upstream makes radical huge changes
- **Instead**: Pull their changes into a branch, test they work and run pure
- **Then**: Let the AI plan a list of all the VIVENTIUM START/END comments in our own code
- **One by one**: Bring all changes to the new codebase
- **NO GIT COMMANDS TO POP CHANGES** or some shit like that which can be very risky

---

## 🚫 Critical Don'ts

### Never:
- ❌ Recreate the wheel
- ❌ Make assumptions without evidence
- ❌ Deviate from existing components and patterns
- ❌ Pull upstream changes directly
- ❌ Use risky git commands (pop, force push, etc.)
- ❌ Hardcode values
- ❌ Overcomplicate solutions
- ❌ Skip studying the codebase first
- ❌ Modify many places in open source code (causes merge conflicts)

### Exception (Explicit User-Approved Private Secrets)
- If the user explicitly requests committing secrets for a private repo workflow, document the exception in `docs/requirements_and_learnings/04_Git_Private_Workflow.md` and confirm the repo is private.

### Always:
- ✅ Study open source projects well and their src code
- ✅ Use as much as what's already there
- ✅ Make minimal changes for beautifully simple results
- ✅ Track VIVENTIUM modifications with comments
- ✅ Create new files/packages for major changes
- ✅ Test thoroughly before implementation
- ✅ Document your approach


---

## 📋 Testing Requirements

### When Developing New Features:
- Create unit tests for the new feature or module
- Run tests yourself and observe the results
- If tests fail, analyze the failure and make necessary adjustments
- **Make sure test files are in an organized folder and not all over the place!**
- Follow existing test organization patterns:
  - Backend tests: `viventium_v0_3_py/viventium_v1/tests/`
  - Unit tests: `viventium_v0_3_py/viventium_v1/tests/unit/`
  - Integration tests: `viventium_v0_3_py/viventium_v1/tests/integration/`

---

## 🔄 Suggested Approach for Fixes

### Implementation Workflow:
1. **Create comprehensive analysis document** (e.g., `docs/VIVENTIUM_ISSUES_ANALYSIS.md`)
2. **Identify root causes** using first principles thinking
3. **Prioritize issues** by severity (Critical → High → Medium → Low)
4. **Explore, test, validate** fixes before implementation
5. **Leverage existing patterns** - use existing functions/components rather than recreating
6. **Implement minimal changes** that solve the problem elegantly
7. **Test thoroughly** before considering complete
8. **For service-level/performance issues, capture before/after runtime evidence** (logs + timings + active revision/image IDs) in the relevant `docs/requirements_and_learnings/` feature document so future sessions do not need to rediscover the same facts


---

## 📝 Summary Checklist

Before making any change, ensure:
- [ ] Read relevant documentation for both `viventium_v0_3_py/viventium_v1` and `viventium_v0_4`
- [ ] Studied existing codebase, patterns, and components
- [ ] Identified existing functionality that can be reused
- [ ] Understood the root cause (if fixing an issue)
- [ ] Classified issue as `runtime-generated` vs `model-generated`
- [ ] Documented trigger -> transformation -> user-visible output with file:line references
- [ ] Confirmed prompt/config edits are used only for model-generated issues
- [ ] Reused existing context signals before adding new plumbing (fields/routes/config)
- [ ] Checked behavior impact across Telegram, Scheduler, Web UI, and Voice
- [ ] Planned minimal changes that leverage existing code
- [ ] Wrapped VIVENTIUM modifications with START/END comments
- [ ] Created/updated tests for new features
- [ ] Documented approach in `docs/` folder
- [ ] Kept personal/private files out of the product-facing repo and moved them to the private companion repo when appropriate
- [ ] Kept deployment-only files out of the product-facing repo and moved them to the enterprise deployment repo when appropriate
- [ ] Preserved `~/Library/Application Support/Viventium/config.yaml` as the canonical end-user config source
- [ ] For service-level fixes, documented before/after telemetry and deployed revision/image IDs
- [ ] Ensured separation of concerns
- [ ] Avoided hardcoding values
- [ ] Made code dynamic and extensible

---

**Remember**: These principles exist to maintain code quality, prevent technical debt, and ensure the project remains maintainable. Follow them consistently in every interaction.
