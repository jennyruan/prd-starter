---
name: aprd
description: Agent-ready PRD. Start, write, check, preview or hand off a PRD in the current repo using Jenny's general 21-section, one-file-per-section template. Use for /aprd, or when asked to write or update a PRD.
argument-hint: "[new <product or feature> | check | preview | trace | handoff | status] [PRD-NNN]"
---

# /aprd: Agent-Ready PRD

Arguments: `$ARGUMENTS`

The template is general and project-neutral. Copy only its **structure** into a project; never copy content from another project's PRD.

## 0. Find the starter (template source)
Look in this order and use the first that exists:
1. `~/code/prd-starter` (Jenny's local copy)
2. `$PRD_STARTER` (environment variable, if set)
3. Otherwise clone `https://github.com/jennyruan/prd-starter` into a temporary folder.

The starter holds: `docs/prd/PRD-000/` (README + 21 section files), `docs/research/RES-000-template.md`, `docs/prd/HANDOFF-TEMPLATE.md`, `tools/prd_tool.py`, `.github/workflows/prd-check.yml`, `.github/workflows/prd-current-state.yml`.

## 1. Pick the mode from the arguments
| Arguments | Do this |
|-----------|---------|
| empty or `status` | List `docs/prd/PRD-*` in this repo with title, status and the MVP / V1 / Later counts (`prd_tool.py scope`). If none exist, offer `new`. |
| `new <name>` | Section 2 |
| `check [PRD-NNN]` | Run `check`, then `versions` and `scope --write` for that PRD (or all). Fix every error; report warnings. |
| `preview [PRD-NNN]` | `python3 tools/prd_tool.py preview docs/prd/PRD-NNN > docs/prd/PRD-NNN-preview.md` and show it to Jenny. Do not commit the preview. |
| `trace [PRD-NNN]` | `python3 tools/prd_tool.py trace docs/prd/PRD-NNN --repo . --write`, then summarize Not started / Code only / Code + tests. |
| `handoff [PRD-NNN]` | Write `docs/prd/HANDOFF.md` from `HANDOFF-TEMPLATE.md`: where things stand, decisions (from §18), open questions (from §16), how to work, first steps. |
| anything else | Treat it as a request to update the named PRD (or ask which one). |

If no PRD id is given and the repo has several PRDs, ask which one.

## 2. New PRD
1. **Setup** (ask before writing files):
   - Next free id: `PRD-001` if `docs/prd/` is empty, else the next number. Feature PRDs name their parent product PRD.
   - Copy `PRD-000/` to `docs/prd/PRD-NNN/`; replace `PRD-000` with the new id in every file; set the front matter (title, type product | feature, status draft, owner, parent).
   - Copy `tools/prd_tool.py` if the repo does not have it. Ask before adding the two workflows.
   - Feature PRD: delete the sections marked "(product only)".
2. **Interview before writing.** 3-5 numbered questions per round until clear: who is affected, what happens today (verified), what should happen, why now, how we know it is done. Then: non-goals, systems touched, MVP (smallest valuable version).
3. **Read the code first.** Fill §3 Current State from evidence: paths, commits, and unmerged branches (check for prototypes). Fill §3.5 Reuse Map and the §9 entity and endpoint tables with exact code names.
4. **Draft.** Fill what is known; every unknown is `[TBD]` and a row in §16. Never guess.
5. **Research** and undecided options go in `docs/research/RES-NNN-*.md` (from `RES-000-template.md`), linked from the PRD README. The PRD keeps only decided vision and features.
6. **Commit**, then run `check`, `versions`, `scope --write`. Then `preview` so Jenny can review.
7. **Iterate** with Jenny. Each decision: a §18 Decision Log row; each answered question: §16 Answer column; commit; `check`.

## 3. Writing rules
- One fact per line. No paragraph longer than 3 lines. Tables and bullets. Plain words; standard technical terms are fine.
- IDs, only appended, never renumbered: G-, NG- (§4) · US- (§5) · REQ- (§6) · AC- (§7) · F- (§8) · T- (§12) · Q- (§16) · FB- (§17) · TH-, SEC- (§20).
- SHALL = required · SHOULD = recommended · MAY = optional · `[TBD]` = unknown: stop and ask.
- New sections go at the end with the next number; never renumber sections.
- References name section, version and part: `[§6 Requirements@v3#REQ-4](06-requirements.md)` or `#6.2`. Point at the specific part, not a whole section.
- §3 is [AUTO]: agent-maintained, committed with the prefix `[auto]`.
- Every REQ and SEC row has a Release value: MVP / V1 / Later. §21 explains the MVP cut.
- Code and tests carry tags like `PRD-001/REQ-18` and `PRD-001/AC-7`, so `trace` can compare PRD and code.
- Version vN of a section = the Nth commit that changed its file. Roll back a section by restoring its old content and committing.

## 4. The 21 sections
1 TL;DR · 2 Context (product only) · 3 Current State [AUTO] (3.1 exists today, 3.2 relevant code, 3.3 drift, 3.4 requirement status, 3.5 reuse map) · 4 Goals & Non-Goals · 5 User Stories · 6 Requirements (6.1 functional with Priority + Release, 6.2 non-functional) · 7 Acceptance Criteria (GIVEN / WHEN / THEN) · 8 UX & Flows (flows, designs, design principles, states) · 9 Technical Design (9.1 entities, 9.2 endpoints, 9.3 files) · 10 Guardrails (ALWAYS / ASK FIRST / NEVER / DO NOT TOUCH) · 11 Edge Cases · 12 Implementation Plan (tasks, dependencies, files, agent hours → `prd_tool.py plan`) · 13 Testing Plan · 14 Rollback Plan · 15 Success Metrics (product only) · 16 Open Questions (with Answer column) · 17 Feedback (versioned section refs; no approval while a blocker is open) · 18 Decision Log · 19 Glossary · 20 Security & Privacy (data classes, threats TH-, controls SEC-, consent, incidents, external review) · 21 Release Plan (MVP core, launch criteria, test users, not in MVP, future releases, go-to-market).

Feature PRD minimum: §1, 3, 4, 6, 7, 10, 11, 12, 13, 16, 20, 21.

## 5. Keep the template generic
If a project shows the structure should change, improve `PRD-000` in the starter repo first (no project content), then apply it to the project. Tell Jenny so she can commit and push the starter.
