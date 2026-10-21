# Build Handoff: <product> (start here)
- Written: YYYY-MM-DD · by: · for: the next coding-agent session in this repo
- Read this file first, then follow it step by step. Ask the owner whenever a step says ASK.

## 1. Where things stand
- PRDs:
- Research:
- Code (branches, prototypes):

## 2. Key decisions already made (details: each PRD's §18 Decision Log)
-

## 3. Still open (ASK before building the part that depends on it)
-

## 4. How to work
- Follow the repo's agent rules (e.g. CLAUDE.md).
- Write a feature plan first for large changes; get approval before coding.
- Tag code and tests with requirement IDs (`PRD-001/REQ-n`, `PRD-001/AC-n`); run `python3 tools/prd_tool.py trace docs/prd/PRD-001 --repo . --write`.
- Never touch production; never guess a `[TBD]`.
- Keep the PRD current: update the section, add a Decision Log row, run `check`.

## 5. First steps, in order
1.
