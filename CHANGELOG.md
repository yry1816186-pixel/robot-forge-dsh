# Changelog

## [2.0.2] - 2026-11-11

CI portability release: 2.0.1 was correct on a UTF-8 developer console, but its first public GitHub Actions run (43011968820) failed all 12 jobs. 2.0.2 removes both environment assumptions that local runs hid.

- `validate.py` now forces UTF-8 on stdout/stderr before printing diagnostics. GitHub's Windows runners use cp1252, where the Chinese status line raised `UnicodeEncodeError` and failed all six Windows jobs before validation could report.
- CI sets `PYTHONDONTWRITEBYTECODE=1`, `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1` for every step, and runs pytest with `-p no:cacheprovider`. The previous Ubuntu jobs validated cleanly but then failed Blueprint selftest because pytest's `.pytest_cache` tripped P071.
- `npm test` / `npm run test:engine` now pass `-p no:cacheprovider`, so the documented local command cannot poison the release tree.
- No generated-project contract, tool schema, scoring rule, reference, or blueprint changed. 2.0.2 is a drop-in replacement for 2.0.1 and 2.0.0; no migration is required.
- Verification log: `docs/v2.0.2-release-report.md`.

## [2.0.1] - 2026-11-11

CI hardening release: clean Linux runners exposed two validator false negatives; both are fixed, and the bundle now validates without PyYAML and without leaving bytecode caches.

- P021 no longer fails when PyYAML is absent. `_parse_yaml` still prefers PyYAML, but falls back to the stdlib `yamlmini` subset used at runtime; only a failure of both parsers is an error. This matches the bundle's stdlib-only runtime contract and unblocks clean CI runners.
- Both `scripts/validate_plugin.py` entrypoints set `sys.dont_write_bytecode = True` before importing `forgekit`, so validation cannot create the `__pycache__` that P071 rejects. Validation is now idempotent and leaves the tree clean.
- No generated-project contract, tool schema, scoring rule, reference, or blueprint changed. 2.0.1 is a drop-in replacement for 2.0.0; no migration is required.
- Verification log: `docs/v2.0.1-release-report.md`.

## [2.0.0] - 2026-11-11

National-release-grade rebuild: from a two-blueprint gate demo to a full-stack robotics delivery system that a non-technical user can drive with one wish.

**Intake and form coverage**
- New `rf_intake` / `forge.py intake`: natural-language classification into 12 archetypes (wheel rover, desktop companion, arm, quadruped, drone, sensor node, mobile manipulator, lawn mower, education kit, camera gimbal, underwater, freeform), with confidence, runner-up, budget/gear defaults, architecture hints, safety flags, benchmark musts, assumptions, and at most 3 questions — each with a default so the agent never blocks.
- Nine safety/regulatory flags (battery, mains, motion, laser, privacy, network, children, outdoor, medical) plus hard blocks for weapons, explosives, stalking and covert surveillance, with safe alternatives.
- `references/archetypes.md`: per-archetype parts, buses, software stack, must requirements, acceptance benchmarks, evidence plan, upgrade path and pitfalls.

**Design and engineering depth**
- New `rf_design` / `forge.py design`: wheel torque, arm joint torque, speed/acceleration/slope, power rails, battery runtime, C-rate, wire gauge (AWG table), thermal density, mass, cost coverage and safety review; writes `forge/design.md`.
- New rules DSN-01…DSN-11 wired into deep check, with duplicate suppression against the existing S6/S7.
- Two blueprints now carry `mass_kg`, `drive_count`, per-component `mass_g`, `torque_kgcm`, `rated_current_ma`, `stall_current_ma`, `architecture.host`, `compliance` and `security` blocks.

**Cross-artifact consistency**
- New `consistency.py` CST-01…CST-14: firmware GPIO declarations vs manifest, I2C pins vs `Wire.begin`, host protocol tokens vs firmware, requirement→verify→evidence mapping, secrets, test quality, sourcing/EOL/delivery, compliance block presence, docs/07 term coverage, network security block, BOM↔docs parts, feature→component binding.
- Safety-flag detection now reads actual feature/architecture text but excludes `wish.forbidden`, so “no camera” cannot trigger a privacy flag.

**Audit, blind review and release**
- New `rf_trace` (`forge/trace.md`): requirement × verify command × evidence × coverage matrix.
- New `rf_review`: reproducible blind-review packet (`forge/review-packet.md/json`) with commands, trace, recent evidence, machine findings, review template and packet SHA-256. The independent reviewer's verdict/score/findings can be recorded into `forge/review.json`; audit only releases when that record is current, `pass`, blocker-free and >= 70.
- New `rf_package`: refuses errors/blocked, emits `dist/<slug>-<version>.zip` with `RELEASE.json` (per-file SHA-256, score, scorecard, fingerprint) and `SHA256SUMS`.
- Audit now returns a six-dimension scorecard (buyable 15 / buildable 20 / runnable 25 / explainable 15 / evidenced 15 / safety 10), a stable verdict and `release_level` release|beta|blocked.
- `next` now walks design → verify/evidence → trace → review → deliver, and its error message uses the real `msg` field.

**DSH orchestration**
- Tools: 7 → 12 (`rf_intake`, `rf_design`, `rf_trace`, `rf_review`, `rf_package` added).
- Skill rewritten as seven stages (intake → decide → architecture → build → prove → blind review → release), with a 12-tool table, seven machine gates, DSH capability map, weak-model fallback and red lines.
- Host guidance, `/forge` command, locale and package metadata updated; reference library 5 → 11 documents.
- `render.py` architecture diagrams now prefer `architecture.host` and fall back to `software.host`, so desktop and host-based projects show a host layer; `model.verify_command_rows` dead branch removed.

**Quality engineering**
- Bundle validator: 12-tool allowlist, 11 reference files, release docs, and P047 version lockstep across package/engine/skill/changelog.
- Eval set 6 → 12 cases; host tests cover all 12 tools; Python engine unit tests; CI matrix Linux/Windows × Python 3.11–3.13 × Node 22/24.
- Added SECURITY, CODE_OF_CONDUCT, SUPPORT, ROADMAP, acceptance criteria, issue/PR templates and release checklist.

## [1.1.3] - 2026-11-11

False-green hardening for generated projects: partial verification, stale measured evidence, unmapped requirements, invalid evidence and dangerous output paths are now blocked by machine gates.

- `verify --only` / `rf_verify({only})` now reports `partial: true`, lists omitted required commands, exits 1 and never prints “全部必需验证通过”; only a full required run can be `ok: true`.
- Measured AND manual evidence record a source fingerprint; changing source, firmware, CAD, sim, `robot.yaml` or `verify.yaml` makes either stale, drops coverage and makes the deep audit fail until it is rerun/re-recorded. Generated docs, README, BOM, diagrams and forge notes are excluded to avoid self-invalidation.
- `required: false` now only tolerates a missing tool (SKIP). If the tool is present and the command runs but fails, it counts as a failure; an optional firmware/CAD test can no longer fail while verify reports success.
- A must requirement's `verify` command must now map to a real `forge/verify.yaml` command (same run string or its `req` list) or validation raises S9; `manual:` steps must be substantive.
- `rf_evidence` now rejects an empty claim, unknown requirements, `measured` levels, a manual entry without a note, and artifacts outside the project root. `rf_evidence` no longer silently records an unknown REQ.
- `rf_new` rejects unsafe slugs and dangerous targets (cwd, home, root, an ancestor of cwd), refuses to overwrite a non-robot-forge directory with `--force`, and keeps `.git`.
- Publish audit is now consistently “0 error + 100% must coverage”; the score is shown as reference only. `rf_check` already reports errors, and `/forge status` handles an unreadable project.
- Added regressions: traversal slug, unknown REQ, manual note boundary, subset verify, stale fingerprint, and check-before-verify.

## [1.1.2] - 2026-11-11

Release-gate hardening: a Beta verdict can no longer be mistaken for a publishable project, and weakly evidenced manual/measured claims block the deep audit.

- CLI `audit` now exits 0 only when the verdict is “可以发布”; Beta (coverage below 100%) exits 1.
- `rf_audit` now returns `ok: true` only for “可以发布”; a Beta result is visibly `ok: false`.
- Deep audit treats manual evidence without a note, and measured evidence without a recorded command, as errors instead of warnings.
- Verify commands honor their cwd (must stay inside the project), accept the legacy timeout_s alias, and fail with exit 127 on an invalid or escaping path.
- The checker now rejects no-op verification commands (true, echo, sleep, exit 0, python -c pass/print) and resolves Python script references relative to the command's cwd.
- rf_check returns ok: false whenever the checker reports errors, so a host model cannot treat a failed check as clean.
- Added regressions for the Beta false positive, missing-note manual evidence, verify cwd, and the no-op command gate.

## [1.1.1] - 2026-11-11

Form-agnostic pass: the plugin is explicitly not humanoid-only, and blueprints are starting points rather than a whitelist.

- Skill, README and reference docs now state that any robot form (desktop, wheeled, arm, quadruped/biped/humanoid, aerial, underwater, climbing, industrial, sensor node, education kit) uses the same manifest → check → verify → evidence contract.
- `blueprints.md` maps 10 form families and explains how to derive a freeform project from the nearest blueprint; `workflow.md` only treats high-risk forms as a budget/regulatory confirmation, not a refusal.
- `rf_new` now requires an explicit `blueprint`; no default desktop template. `rf_blueprints` is the first step when no project exists.
- `render.py` no longer hardcodes a desktop environment or a voice/button/phone interface; diagrams derive labels from `wish.environment` and actual components.
- Renamed eval `arms` to `conditions` and clarified that A/B means with-plugin vs without-plugin, never a robot morphology.

## [1.1.0] - 2026-11-11

DSH-native rewrite.

- Package is now a DeepSeek Harness bundle (`package.json`, `cordis.patch.yml`, ESM Host plugin).
- Seven model-facing tools: `rf_blueprints`, `rf_new`, `rf_status`, `rf_check`, `rf_verify`, `rf_audit`, `rf_evidence`.
- `/forge` human command for status/next/check without a model message.
- Skill mounted through `@deepseek-ai/dsh-skill-filesystem` with a bundle-resolved path.
- `forge.py` gained JSON payloads and `next`; all tool decisions come from the same Python engine.
- Removed Claude Code / ZCode manifests, markdown agents and markdown commands.
- Added DSH runtime test, bundle validator, role prompt templates, and CHANGELOG.
- Validated installation into a throwaway DSH profile with `dsh plugin add` (config composition and bundled-skill path resolution).

## [1.0.0] - 2026-11-11

- Initial five-stage protocol, two blueprints, Python gates, evidence levels and release audit.