# Agent-Ready PRD Starter
A general, project-neutral PRD template for any product or feature. Written for coding agents to execute and for humans to scan.

## What's inside
| Path | What it is |
|------|------------|
| `docs/prd/PRD-000/` | The empty PRD template: `README.md` + 21 section files (one file per section, so each section has its own git version history) |
| `docs/research/RES-000-template.md` | Template for research and undecided options (kept out of the PRD) |
| `docs/prd/HANDOFF-TEMPLATE.md` | Template for handing a finished PRD to a build session |
| `tools/prd_tool.py` | Checker and generators: `check`, `versions`, `scope`, `trace`, `plan` (Python 3.8+, standard library only) |
| `.github/workflows/prd-check.yml` | CI: checks references and regenerates tables on every PRD push |
| `.github/workflows/prd-current-state.yml` | Optional: an agent refreshes §3 Current State weekly and after code merges |
| `.claude/skills/aprd/SKILL.md` | The `/aprd` skill for Claude Code: new, check, preview, trace, handoff, status |

## Install the /aprd command (Claude Code, once per computer)
```
mkdir -p ~/.claude/skills
ln -s ~/code/prd-starter/.claude/skills/aprd ~/.claude/skills/aprd
```
Then in any repo, in Claude Code: `/aprd new <product>` · `/aprd check` · `/aprd preview` · `/aprd trace` · `/aprd handoff` · `/aprd` (status).
The link points at this repo, so `git pull` here updates the skill everywhere.

## Start a new PRD in any project (by hand)
1. Copy `docs/prd/PRD-000/` into the project as `docs/prd/PRD-001/` (next free number). Copy `tools/` and, if you use GitHub Actions, the two workflows.
2. In the new `README.md`, set the front matter (`id: PRD-001`, title, type, status, owner) and replace `PRD-000` with `PRD-001` everywhere in that folder.
3. Fill the sections (the 21 sections and rules are explained in `PRD-000/README.md`). Unknowns: write `[TBD]` and add them to §16.
4. Commit, then run:
   - `python3 tools/prd_tool.py check docs/prd/PRD-001`
   - `python3 tools/prd_tool.py versions docs/prd/PRD-001`
   - `python3 tools/prd_tool.py scope docs/prd/PRD-001 --write`
5. Feature PRDs: delete the sections marked "(product only)". Child PRDs: list them in the parent's README.

## Keep the template generic
- Improve the structure here, not inside a project copy; then copy the change into active projects.
- Never put project names, decisions or research in this repo.
