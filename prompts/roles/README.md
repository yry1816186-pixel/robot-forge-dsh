# Role prompts for subagents

These files are **prompt templates**, not automatically loaded DSH agents. The
main agent reads one and passes it to `subagent` (or a forked child) when a
second, independent context is useful.

| File | Use |
|---|---|
| `planner.md` | turn a wish into scope, budget, must/nice/forbidden |
| `hardware.md` | BOM, sourcing, power budget, wiring |
| `embedded.md` | firmware, protocol, pins, safety interlocks |
| `software.md` | host software, mock/real boundary, tests |
| `sim.md` | simulation, kinematics, scene checks |
| `integrator.md` | end-to-end wiring, docs, release reproducibility |
| `verifier.md` | read-only fresh-evidence verification |
| `reviewer.md` | blind scoring and release verdict |
| `researcher.md` | sourcing, alternatives, license checks |

Map roles to the seven stages (A 接单 → B 定案 → C 架构 → D 建造 → E 证明 → F 盲审 → G 发布):

| Stage | Lead role | Typical helpers | Exit gate |
|---|---|---|---|
| A 接单 | planner | researcher | `rf_intake` classified, ≤3 questions, safety flags listed |
| B 定案 | planner | hardware, software | `rf_new` project exists, one-page plan confirmed |
| C 架构 | hardware + embedded | software, sim | `rf_design` numbers pass, `rf_check` 0 error |
| D 建造 | domain owners | researcher | `rf_check --deep` 0 error, all required verify exit 0 |
| E 证明 | verifier | — | `rf_verify` fresh, `rf_trace` must 100% |
| F 盲审 | reviewer | — | packet reviewed; Lead records valid `pass`, no blocker, score ≥70 |
| G 发布 | integrator | reviewer | `rf_audit` release (≥85 + valid review) + `rf_package` release/beta |

All roles share the 12 `rf_*` tools; a read-only role must call the write-capable ones with `write: false` or only read their artifacts.

Rules for every role:

- State your inputs and the exact files you read.
- You may run read-only commands; `verifier` and `reviewer` must not edit files.
- Report findings with file:line, evidence (command + exit code), and a concrete fix.
- Do not treat the implementer's summary as evidence.
