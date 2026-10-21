#!/usr/bin/env python3
"""prd_tool.py: section versions, reference checks and agent planning for a PRD folder.

A PRD folder holds README.md plus one file per section (NN-name.md).
The version of a section is the number of Git commits that changed its file (v1, v2, ...).

Commands
  versions <prd_dir>                 Rewrite the Section Versions + Recent Changes tables in README.md
  check    <prd_dir> [--feedback]    Validate every reference; --feedback logs errors as blockers in §17
  scope    <prd_dir> [--write]        MVP / V1 / Later lists from every Release column; --write puts them in README.md
  trace    <prd_dir> --repo <path> [--write]
                                     Requirement status (not started / code only / code + tests) from
                                     PRD-ID/REQ-n tags in the code; --write puts it in §3.4
  preview  <prd_dir>                 Print all sections as one Markdown document for review
  plan     <prd_dir> [--max-agents N] [--write]
                                     Agents needed + longest run, from the §12 task table;
                                     --write puts the result into README.md

Reference format (section name + version + specific part):
  [§6 Requirements@v3#REQ-4](06-requirements.md)   item REQ-4 in version 3 of §6
  [§6 Requirements@v3#6.2](06-requirements.md)     subsection 6.2 in version 3 of §6
  [§6 Requirements@v3](06-requirements.md)         the whole section, version 3

Standard library only. Python 3.8+. Run from anywhere inside the Git repo.
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------- constants

SECTION_FILE = re.compile(r"^(\d{2})-[\w-]+\.md$")
HEADING = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.M)
ID_PREFIX_OWNER = {  # which section defines which kind of ID
    "G": 4, "NG": 4, "US": 5, "REQ": 6, "AC": 7, "F": 8,
    "T": 12, "Q": 16, "FB": 17, "TH": 20, "SEC": 20,
}
ID_RE = re.compile(r"\b(" + "|".join(sorted(ID_PREFIX_OWNER, key=len, reverse=True)) + r")-(\d+)\b")
REF_RE = re.compile(
    r"\[§(?P<num>\d+)\s+(?P<name>[^\]@]+?)\s*@v(?P<ver>\d+)"
    r"(?:#(?P<part>[A-Z]+-\d+|\d+(?:\.\d+)+))?\]\((?P<target>[^)]*)\)"
)
AUTO_BLOCK = "<!-- AUTO:{name} START"
FALLBACK_HOURS = {"S": 1.0, "M": 3.0}


# ---------------------------------------------------------------- git helpers

def git(*args: str, cwd: Path) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


@dataclass
class Commit:
    sha: str
    short: str
    date: str
    author: str
    subject: str


@dataclass
class Section:
    num: int
    path: Path
    name: str
    commits: list[Commit] = field(default_factory=list)  # oldest first
    dirty: bool = False

    @property
    def version(self) -> int:
        return len(self.commits)

    def content_at(self, version: int, repo: Path) -> str:
        sha = self.commits[version - 1].sha
        rel = self.path.resolve().relative_to(repo).as_posix()
        return git("show", f"{sha}:{rel}", cwd=repo)

    def current(self) -> str:
        return self.path.read_text(encoding="utf-8")


def repo_root(p: Path) -> Path:
    return Path(git("rev-parse", "--show-toplevel", cwd=p).strip()).resolve()


def clean_name(raw: str) -> str:
    return re.sub(r"\s*(\(.*?\)|\[.*?\])", "", raw).strip()


def load_sections(prd: Path) -> tuple[Path, dict[int, Section]]:
    repo = repo_root(prd)
    sections: dict[int, Section] = {}
    for f in sorted(prd.iterdir()):
        m = SECTION_FILE.match(f.name)
        if not m:
            continue
        text = f.read_text(encoding="utf-8")
        h = HEADING.search(text)
        num = int(m.group(1))
        name = clean_name(h.group(2)) if h else f.stem
        log = git("log", "--format=%H|%h|%ad|%an|%s", "--date=short", "--", str(f.resolve()), cwd=repo)
        commits = [Commit(*line.split("|", 4)) for line in log.splitlines() if line.strip()]
        commits.reverse()
        dirty = bool(git("status", "--porcelain", "--", str(f.resolve()), cwd=repo).strip())
        sections[num] = Section(num, f, name, commits, dirty)
    return repo, sections


def replace_auto_block(text: str, name: str, body: str) -> str:
    pat = re.compile(
        r"(<!-- AUTO:" + re.escape(name) + r" START[^>]*-->\n)(.*?)(\n<!-- AUTO:" + re.escape(name) + r" END -->)",
        re.S,
    )
    if not pat.search(text):
        raise SystemExit(f"AUTO block '{name}' not found")
    return pat.sub(lambda m: m.group(1) + body + m.group(3), text)


# ---------------------------------------------------------------- versions

def cmd_versions(prd: Path) -> int:
    repo, sections = load_sections(prd)
    rows = ["| Section | Version | Updated | Author | Commit | Last change |",
            "|---------|---------|---------|--------|--------|-------------|"]
    snapshot = []
    for s in sections.values():
        c = s.commits[-1] if s.commits else None
        ver = f"v{s.version}" + (" + uncommitted" if s.dirty else "")
        author = "—"
        if c:
            author = c.author + (" (auto)" if c.subject.startswith("[auto]") else "")
        rows.append(
            f"| [§{s.num} {s.name}]({s.path.name}) | {ver} | {c.date if c else '—'} | {author} | "
            f"{'`' + c.short + '`' if c else '—'} | {c.subject.replace('|', '/') if c else 'not committed'} |"
        )
        snapshot.append(f"§{s.num}v{s.version}")
    snap = " ".join(snapshot)
    snap_id = hashlib.sha1(snap.encode()).hexdigest()[:7]
    body = "\n".join(rows) + f"\n\n**Snapshot `{snap_id}`:** {snap}"

    # Recent changes across all sections
    paths = [str(s.path.resolve()) for s in sections.values()]
    log = git("log", "-n", "15", "--format=@@%h|%ad|%an|%s", "--date=short", "--name-only", "--", *paths, cwd=repo)
    by_file = {s.path.resolve().relative_to(repo).as_posix(): s.num for s in sections.values()}
    recent = ["| Date | Author | Sections | Commit | Message |", "|------|--------|----------|--------|---------|"]
    for block in log.split("@@")[1:]:
        lines = [l for l in block.splitlines() if l.strip()]
        short, date, author, subject = lines[0].split("|", 3)
        nums = sorted({by_file[l] for l in lines[1:] if l in by_file})
        recent.append(f"| {date} | {author} | {', '.join('§' + str(n) for n in nums)} | `{short}` | {subject.replace('|', '/')} |")
    if len(recent) == 2:
        recent.append("| — | — | — | — | no commits yet |")

    readme = prd / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = replace_auto_block(text, "section-versions", body)
    text = replace_auto_block(text, "recent-changes", "\n".join(recent))
    readme.write_text(text, encoding="utf-8")
    print(f"README.md updated · snapshot {snap_id}")
    return 0


# ---------------------------------------------------------------- check

def strip_non_content(text: str) -> str:
    """Drop code fences, inline code and HTML comments so examples are not checked."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def id_definitions(text: str) -> dict[str, str]:
    """IDs defined in a section: first cell of a table row, or the start of a bullet."""
    defs = {}
    for line in strip_non_content(text).splitlines():
        m = re.match(r"^\s*(?:\|\s*|-\s+)((?:[A-Z]+)-\d+)\b", line)
        if m:
            defs.setdefault(m.group(1), line.strip())
    return defs


def subsection(text: str, part: str) -> str | None:
    m = re.search(r"^(#{3,6})\s+" + re.escape(part) + r"\b.*$", text, re.M)
    if not m:
        return None
    level = len(m.group(1))
    rest = text[m.end():]
    end = re.search(r"^#{2," + str(level) + r"}\s", rest, re.M)
    return (m.group(0) + rest[: end.start() if end else len(rest)]).strip()


def part_text(text: str, part: str | None) -> str | None:
    if part is None:
        return text.strip()
    if ID_RE.fullmatch(part):
        return id_definitions(text).get(part)
    return subsection(text, part)


@dataclass
class Issue:
    level: str  # ERROR / WARN
    where: str
    ref: str
    msg: str


def cmd_check(prd: Path, feedback: bool) -> int:
    repo, sections = load_sections(prd)
    issues: list[Issue] = []

    # 1. duplicate / misplaced ID definitions
    current_ids: dict[str, int] = {}
    for s in sections.values():
        for i in id_definitions(s.current()):
            owner = ID_PREFIX_OWNER.get(i.split("-")[0])
            if owner is None or owner != s.num:
                continue
            if i in current_ids:
                issues.append(Issue("ERROR", s.path.name, i, f"defined twice (also in §{current_ids[i]})"))
            current_ids[i] = s.num

    for s in sections.values():
        text = strip_non_content(s.current())

        # 2. versioned references
        for m in REF_RE.finditer(text):
            ref = m.group(0).split("](")[0] + "]"
            num, ver, part = int(m.group("num")), int(m.group("ver")), m.group("part")
            tgt = sections.get(num)
            if tgt is None:
                issues.append(Issue("ERROR", s.path.name, ref, f"§{num} does not exist"))
                continue
            if m.group("name").strip().lower() != tgt.name.lower():
                issues.append(Issue("WARN", s.path.name, ref, f"section name should be '{tgt.name}'"))
            if m.group("target") and m.group("target").split("#")[0] != tgt.path.name:
                issues.append(Issue("WARN", s.path.name, ref, f"link should point to {tgt.path.name}"))
            if ver < 1 or ver > tgt.version:
                issues.append(Issue("ERROR", s.path.name, ref,
                                    f"§{num} has no v{ver} (latest committed is v{tgt.version})"))
                continue
            old = part_text(tgt.content_at(ver, repo), part)
            if old is None:
                issues.append(Issue("ERROR", s.path.name, ref, f"'{part}' does not exist in §{num} v{ver}"))
                continue
            now = part_text(tgt.current(), part)
            if now is None:
                issues.append(Issue("ERROR", s.path.name, ref,
                                    f"'{part or 'section'}' was removed after v{ver}: dangling reference"))
            elif now != old:
                issues.append(Issue("WARN", s.path.name, ref,
                                    f"'{part or 'section'}' changed since v{ver} (now v{tgt.version}{'+' if tgt.dirty else ''}): re-review"))

        # 3. bare ID mentions must point to something that exists now
        bare = REF_RE.sub("", text)
        for m in ID_RE.finditer(bare):
            i = m.group(0)
            if i not in current_ids:
                issues.append(Issue("ERROR", s.path.name, i,
                                    f"{i} is not defined in §{ID_PREFIX_OWNER[m.group(1)]}: dangling ID"))

    # de-duplicate
    seen, unique = set(), []
    for x in issues:
        k = (x.level, x.where, x.ref, x.msg)
        if k not in seen:
            seen.add(k)
            unique.append(x)

    errors = [x for x in unique if x.level == "ERROR"]
    for x in unique:
        print(f"{x.level:5}  {x.where:28}  {x.ref:40}  {x.msg}")
    print(f"\n{len(errors)} error(s), {len(unique) - len(errors)} warning(s)")

    if feedback and errors:
        log_blockers(prd, sections, errors)
    return 1 if errors else 0


def log_blockers(prd: Path, sections: dict[int, Section], errors: list[Issue]) -> None:
    fb = sections.get(17)
    if fb is None:
        return
    text = fb.current()
    ids = [int(n) for n in re.findall(r"\|\s*FB-(\d+)\s*\|", text)]
    nxt = max(ids, default=0) + 1
    added = 0
    for e in errors:
        comment = f"{e.where}: {e.ref}: {e.msg}".replace("|", "/")
        if comment in text:
            continue
        src = next((s for s in sections.values() if s.path.name == e.where), None)
        where = f"[§{src.num} {src.name}@v{src.version}]({src.path.name})" if src and src.version else e.where
        text = text.rstrip("\n") + (
            f"\n| FB-{nxt} | agent: prd_tool check | {where} | blocker | {comment} | open | |"
        )
        nxt += 1
        added += 1
    fb.path.write_text(text + "\n", encoding="utf-8")
    print(f"logged {added} new blocker(s) in {fb.path.name}")


# ---------------------------------------------------------------- plan

@dataclass
class Task:
    id: str
    name: str
    deps: list[str]
    files: set[str]
    hours: float


def parse_plan(text: str) -> list[Task]:
    rows = [l for l in strip_comments_only(text).splitlines() if l.strip().startswith("|")]
    if not rows:
        raise SystemExit("no task table found in §12")
    header = [c.strip().lower() for c in rows[0].strip("|").split("|")]

    def col(name: str) -> int:
        for i, h in enumerate(header):
            if h.startswith(name):
                return i
        raise SystemExit(f"§12 table is missing the '{name}' column")

    ci, cn, cd, cf, ch = col("id"), col("task"), col("depends"), col("files"), col("agent hrs")
    tasks = []
    for r in rows[2:]:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if len(cells) < len(header) or not re.fullmatch(r"T-\d+", cells[ci]):
            continue
        raw_h = cells[ch]
        if not raw_h:
            raise SystemExit(f"{cells[ci]}: 'Agent hrs' is empty")
        if raw_h.upper() in FALLBACK_HOURS:
            hours = FALLBACK_HOURS[raw_h.upper()]
        elif raw_h.upper() == "L":
            raise SystemExit(f"{cells[ci]}: size L must be split into smaller tasks")
        else:
            hours = float(raw_h)
        deps = re.findall(r"T-\d+", cells[cd])
        files = {f.strip().strip("`") for f in re.split(r"[,;]", cells[cf]) if f.strip().strip("`")}
        tasks.append(Task(cells[ci], cells[cn], deps, files, hours))
    if not tasks:
        raise SystemExit("§12 has no filled-in tasks")
    return tasks


def strip_comments_only(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    # ignore the generated agent-plan block
    return text.split("### 12.1")[0]


def bottom_levels(tasks: dict[str, Task]) -> dict[str, float]:
    """Longest remaining path (hours) from the start of each task to the end of the project."""
    children: dict[str, list[str]] = {t: [] for t in tasks}
    for t in tasks.values():
        for d in t.deps:
            children[d].append(t.id)
    memo: dict[str, float] = {}

    def bl(t: str) -> float:
        if t not in memo:
            memo[t] = tasks[t].hours + max((bl(c) for c in children[t]), default=0.0)
        return memo[t]

    for t in tasks:
        bl(t)
    return memo


def validate_dag(tasks: dict[str, Task]) -> None:
    for t in tasks.values():
        for d in t.deps:
            if d not in tasks:
                raise SystemExit(f"{t.id} depends on unknown task {d}")
    state: dict[str, int] = {}

    def visit(t: str, path: list[str]) -> None:
        if state.get(t) == 1:
            raise SystemExit("dependency cycle: " + " → ".join(path + [t]))
        if state.get(t) == 2:
            return
        state[t] = 1
        for d in tasks[t].deps:
            visit(d, path + [t])
        state[t] = 2

    for t in tasks:
        visit(t, [])


def simulate(tasks: dict[str, Task], agents: int, prio: dict[str, float]):
    """List scheduling: highest remaining-path first; tasks sharing a file never overlap."""
    remaining_deps = {t: set(tasks[t].deps) for t in tasks}
    done: set[str] = set()
    running: list[tuple[float, str, int]] = []  # (finish, task, lane)
    free_lanes = list(range(1, agents + 1))
    locked: set[str] = set()
    schedule: list[tuple[str, int, float, float]] = []
    t_now, peak = 0.0, 0
    while len(done) < len(tasks):
        ready = sorted(
            (t for t in tasks if t not in done and not remaining_deps[t]
             and all(t != r[1] for r in running) and t not in {s[0] for s in schedule}),
            key=lambda t: (-prio[t], t),
        )
        for t in ready:
            if not free_lanes:
                break
            if tasks[t].files & locked:
                continue
            lane = free_lanes.pop(0)
            locked |= tasks[t].files
            heapq.heappush(running, (t_now + tasks[t].hours, t, lane))
            schedule.append((t, lane, t_now, t_now + tasks[t].hours))
        peak = max(peak, len(running))
        if not running:
            raise SystemExit("scheduler stuck: check dependencies")
        finish, t, lane = heapq.heappop(running)
        finished = [(finish, t, lane)]
        while running and running[0][0] == finish:
            finished.append(heapq.heappop(running))
        t_now = finish
        for _, t, lane in finished:
            done.add(t)
            locked -= tasks[t].files
            free_lanes.append(lane)
            free_lanes.sort()
            for o in tasks:
                remaining_deps[o].discard(t)
    return t_now, peak, schedule


def fmt_h(h: float) -> str:
    return f"{h:g} h"


def cmd_plan(prd: Path, max_agents: int | None, write: bool) -> int:
    f = next((p for p in prd.iterdir() if p.name.startswith("12-")), None)
    if f is None:
        raise SystemExit("no 12-*.md file found")
    task_list = parse_plan(f.read_text(encoding="utf-8"))
    tasks = {t.id: t for t in task_list}
    validate_dag(tasks)
    prio = bottom_levels(tasks)

    # critical path (dependency-only lower bound)
    start = max(prio, key=prio.get)
    chain, cur = [start], start
    children = {t: [o for o in tasks if t in tasks[o].deps] for t in tasks}
    while children[cur]:
        cur = max(children[cur], key=lambda c: prio[c])
        chain.append(cur)
    critical = prio[start]

    n = len(tasks)
    best_time, best_k, best_sched = None, None, None
    curve = []
    for k in range(1, n + 1):
        mk, peak, sched = simulate(tasks, k, prio)
        curve.append((k, mk))
        if best_time is None or mk < best_time - 1e-9:
            best_time, best_k, best_sched = mk, k, sched
    total = sum(t.hours for t in tasks.values())
    longest_task = max(tasks.values(), key=lambda t: t.hours)

    lines = [
        f"- **Agents needed:** {best_k} running at the same time (more agents do not finish sooner)",
        f"- **Longest run (wall clock):** {fmt_h(best_time)} with {best_k} agents",
        f"- **Critical path:** {' → '.join(chain)} = {fmt_h(critical)} (no number of agents can beat this)",
        f"- **Longest single task:** {longest_task.id} = {fmt_h(longest_task.hours)}",
        f"- **Total compute:** {total:g} agent-hours (cost, not wall clock)",
    ]
    if best_time > critical + 1e-9:
        lines.append(f"- **Note:** file conflicts add {fmt_h(round(best_time - critical, 2))} on top of the critical path")
    if max_agents:
        mk, _, sched_cap = simulate(tasks, max_agents, prio)
        lines.append(f"- **With your cap of {max_agents} agent(s):** longest run = {fmt_h(mk)}")
        if max_agents < best_k:
            best_sched = sched_cap
    lines += ["", "| Agents | Longest run |", "|--------|-------------|"]
    lines += [f"| {k} | {fmt_h(mk)} |" for k, mk in curve if k <= best_k + 1]
    lines += ["", "| Agent | Task | Start | End |", "|-------|------|-------|-----|"]
    for t, lane, s, e in sorted(best_sched, key=lambda x: (x[1], x[2])):
        lines.append(f"| A{lane} | {t} {tasks[t].name} | {s:g} h | {e:g} h |")

    out = "\n".join(lines)
    print(out)
    if write:  # written to README so §12's version only changes when a human edits the tasks
        readme = prd / "README.md"
        readme.write_text(replace_auto_block(readme.read_text(encoding="utf-8"), "agent-plan", out), encoding="utf-8")
        print("\nAgent Plan updated in README.md")
    return 0


# ---------------------------------------------------------------- scope

RELEASES = ["MVP", "V1", "Later"]


def release_rows(text: str) -> list[tuple[str, str, str]]:
    """(id, text, release) from every table that has a Release column."""
    rows, header = [], None
    for line in strip_non_content(text).splitlines():
        if not line.strip().startswith("|"):
            header = None
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if set(line.replace("|", "").strip()) <= set("-: "):
            continue
        rel = next((i for i, h in enumerate(header) if h.startswith("release")), None)
        if rel is None or rel >= len(cells) or not ID_RE.fullmatch(cells[0]):
            continue
        rows.append((cells[0], cells[1], cells[rel]))
    return rows


def cmd_scope(prd: Path, write: bool) -> int:
    _, sections = load_sections(prd)
    rows = []
    for s in sections.values():
        if s.num == 3:  # §3 holds generated status tables, not requirements
            continue
        rows += [(i, t, r, s.num) for i, t, r in release_rows(s.current())]
    unknown = [r for r in rows if r[2] not in RELEASES]
    lines = []
    for rel in RELEASES:
        group = [r for r in rows if r[2] == rel]
        lines += [f"### {rel} ({len(group)})", "| ID | What | Section |", "|----|------|---------|"]
        lines += [f"| {i} | {t} | §{n} |" for i, t, _, n in group] or ["| — | — | — |"]
        lines.append("")
    if unknown:
        lines.append("**Missing or invalid Release:** " + ", ".join(r[0] for r in unknown))
    out = "\n".join(lines).rstrip()
    print(out)
    if write:
        readme = prd / "README.md"
        readme.write_text(replace_auto_block(readme.read_text(encoding="utf-8"), "release-scope", out), encoding="utf-8")
        print("\nRelease Scope updated in README.md")
    return 1 if unknown else 0


# ---------------------------------------------------------------- trace

SKIP_DIRS = {".git", "node_modules", "cdk.out", "gen", "build", "dist", ".next", "vendor", ".claude", ".gstack"}
TEXT_EXT = {".go", ".ts", ".tsx", ".js", ".jsx", ".dart", ".py", ".proto", ".yaml", ".yml", ".sql", ".kt", ".swift", ".md"}
TEST_RE = re.compile(r"(_test\.go$|\.test\.[jt]sx?$|\.spec\.[jt]sx?$|_test\.dart$|(^|/)tests?/|(^|/)e2e/|test_[^/]*\.py$)")


def prd_items(prd: Path) -> tuple[str, dict[str, tuple[str, str, str]], dict[str, str]]:
    """PRD id, {REQ/SEC id: (text, release, section)}, {AC id: REQ id}."""
    text = (prd / "README.md").read_text(encoding="utf-8")
    m = re.search(r"^id:\s*(\S+)", text, re.M)
    prd_id = m.group(1) if m else prd.name
    _, sections = load_sections(prd)
    items, ac_map = {}, {}
    for s in sections.values():
        if s.num == 3:  # skip the generated status table itself
            continue
        for i, t, r in release_rows(s.current()):
            items[i] = (t, r, f"§{s.num}")
        if s.num == 7:
            for line in strip_non_content(s.current()).splitlines():
                c = [x.strip() for x in line.strip().strip("|").split("|")]
                if len(c) > 1 and re.fullmatch(r"AC-\d+", c[0]):
                    req = re.search(r"(REQ|SEC)-\d+", c[1])
                    if req:
                        ac_map[c[0]] = req.group(0)
    return prd_id, items, ac_map


def cmd_trace(prd: Path, repo: Path, write: bool) -> int:
    prd_id, items, ac_map = prd_items(prd)
    tag = re.compile(re.escape(prd_id) + r"/((?:REQ|SEC|AC)-\d+)\b")
    code: dict[str, set[str]] = {}
    tests: dict[str, set[str]] = {}
    for f in repo.rglob("*"):
        if not f.is_file() or f.suffix not in TEXT_EXT or any(part in SKIP_DIRS for part in f.parts):
            continue
        rel = f.relative_to(repo).as_posix()
        if rel.startswith("docs/prd/"):
            continue
        try:
            body = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in tag.finditer(body):
            i = m.group(1)
            target = ac_map.get(i, i) if i.startswith("AC-") else i
            (tests if TEST_RE.search(rel) or i.startswith("AC-") else code).setdefault(target, set()).add(rel)
    rows = ["| ID | Release | Status | Code | Tests |", "|----|---------|--------|------|-------|"]
    counts = {"Not started": 0, "Code only": 0, "Code + tests": 0}
    order = {"MVP": 0, "V1": 1, "Later": 2}
    for i, (t, rel, sec) in sorted(items.items(), key=lambda kv: (order.get(kv[1][1], 9), kv[0].split("-")[0], int(kv[0].split("-")[1]))):
        c, ts = sorted(code.get(i, [])), sorted(tests.get(i, []))
        status = "Code + tests" if c and ts else "Code only" if c else "Not started"
        counts[status] += 1
        show = lambda xs: ", ".join(f"`{x}`" for x in xs[:3]) + (f" +{len(xs) - 3}" if len(xs) > 3 else "") if xs else "—"
        rows.append(f"| {i} | {rel} | {status} | {show(c)} | {show(ts)} |")
    head = f"Tag code and tests with `{prd_id}/REQ-n` (or `/SEC-n`, `/AC-n`) in a comment or test name. " \
           f"Totals: " + " · ".join(f"{k} {v}" for k, v in counts.items())
    out = head + "\n\n" + "\n".join(rows)
    print(out)
    if write:
        f = next(p for p in prd.iterdir() if p.name.startswith("03-"))
        f.write_text(replace_auto_block(f.read_text(encoding="utf-8"), "req-status", out), encoding="utf-8")
        print(f"\nRequirement Status updated in {f.name}")
    return 0


# ---------------------------------------------------------------- preview

def cmd_preview(prd: Path) -> int:
    """Print every section in order as one Markdown document, for human review."""
    readme = (prd / "README.md").read_text(encoding="utf-8")
    title = next((l.lstrip("# ").strip() for l in readme.splitlines() if l.startswith("# ")), prd.name)
    out = [f"# {title} (preview)", "", "> Preview only. The real PRD is one file per section in this folder.", ""]
    m = re.search(r"<!-- AUTO:release-scope START[^>]*-->\n(.*?)\n<!-- AUTO:release-scope END -->", readme, re.S)
    if m:
        out += ["## Release Scope (generated)", "", m.group(1), ""]
    for f in sorted(p for p in prd.iterdir() if SECTION_FILE.match(p.name)):
        out += [f"<sub>File: `{f.name}`</sub>", "", f.read_text(encoding="utf-8").rstrip(), ""]
    print("\n".join(out))
    return 0


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("versions"); v.add_argument("prd", type=Path)
    c = sub.add_parser("check"); c.add_argument("prd", type=Path); c.add_argument("--feedback", action="store_true")
    r = sub.add_parser("scope"); r.add_argument("prd", type=Path); r.add_argument("--write", action="store_true")
    t = sub.add_parser("trace"); t.add_argument("prd", type=Path); t.add_argument("--repo", type=Path, required=True); t.add_argument("--write", action="store_true")
    v2 = sub.add_parser("preview"); v2.add_argument("prd", type=Path)
    p = sub.add_parser("plan"); p.add_argument("prd", type=Path)
    p.add_argument("--max-agents", type=int); p.add_argument("--write", action="store_true")
    a = ap.parse_args()
    prd = a.prd.resolve()
    if a.cmd == "versions":
        return cmd_versions(prd)
    if a.cmd == "check":
        return cmd_check(prd, a.feedback)
    if a.cmd == "scope":
        return cmd_scope(prd, a.write)
    if a.cmd == "preview":
        return cmd_preview(prd)
    if a.cmd == "trace":
        return cmd_trace(prd, a.repo.resolve(), a.write)
    return cmd_plan(prd, a.max_agents, a.write)


if __name__ == "__main__":
    sys.exit(main())
