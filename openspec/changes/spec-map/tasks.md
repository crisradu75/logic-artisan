# Tasks

## 1. The declaration and the check

- [x] 1.1 `check_spec_proof.py` reads the `## Spec map` bullets: none declared yields nothing; a heading with no bullet, a second heading or a non-bullet line exits 2 naming the line. Test carries `requirement: spec-map / A repo declares its spec map as a fact`.
- [x] 1.2 An unlinked spec (live, or added by an open change) and a link to no spec each print `PROBLEM spec-map` and exit 1; a link is a Markdown link outside code fences that resolves to `openspec/specs/<name>` or its `spec.md`. Test carries `requirement: spec-proof / A checker reports specs a declared map leaves out and links that point nowhere`.
- [x] 1.3 A declared path matching no file prints `PROBLEM spec-map`; with no map file at all the unlinked-spec lines are not repeated. Same marker as 1.2.
- [x] 1.4 With no declaration the run prints no line about a map and its exit code is unchanged. Done when a test on a tree with two unlinked specs and no declaration sees exit 0 and no map text.

## 2. Setup and this repo

- [x] 2.1 `cla-setup/SKILL.md` lists the "Spec map" fact and offers the three-layer scaffold for a repo with `openspec/`: asks first, writes only on yes at the chosen path, records it in the facts file. Test carries `requirement: spec-map / Setup offers a three-layer spec map scaffold` and checks the filled scaffold passes the checker.
- [x] 2.2 Write `openspec/spec-map.md` linking every spec from a workflow step; declare it under `## Spec map` and in "Doc-sweep paths". Done when `check_spec_proof.py` prints no `PROBLEM spec-map` line on this repo.
- [x] 2.3 The `check_spec_proof.py` row in DEVELOPER-GUIDE section 11 names the map rule. Done when `check_no_project_tokens.py` passes.

## 3. Proof and gates

- [ ] 3.1 Run `pytest plugin-tests -q -n auto --dist loadfile` and `openspec validate --specs --strict` once each on the final commit.
- [x] 3.2 docs and spec map: `cla.io/project-facts.md`, `DEVELOPER-GUIDE.md` section 11 row, `cla-setup/SKILL.md`, `openspec/spec-map.md`; none affected: root `CLAUDE.md`, `README.md`, plugin readme (none describes the checker's rules or the facts headings).
