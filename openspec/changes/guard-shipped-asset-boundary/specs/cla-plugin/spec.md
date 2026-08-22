## ADDED Requirements

### Requirement: Release-time shipped-asset scan

The workflow that publishes this plugin SHALL verify the **Shipped-asset boundary** mechanically
before cutting a tag, as a precondition alongside the others it already enforces (on the default
branch, working tree clean, up to date with the remote, test gate green, work reviewed and merged).
The scan SHALL be performed at release time rather than in the repo's test suite, because that is
where the consequence lands: a tag is what a consumer fetches, and a published tag is never moved.

**Structural allowlist, not a denylist.** The scan SHALL enumerate every file that would be
published and SHALL fail any file that does not match a **declared shape** on a fixed allowlist,
naming that file. It SHALL NOT be expressed as a list of forbidden shapes. A denylist detects only
the shapes its author anticipated, and every asset class the boundary was written about — the
aggregating test runner, the mutation runner, the source-repo-only markers, the source-drift
checker, and the publication workflow's own skill file — has a shape that no reasonable denylist of
test artifacts would name.

**Enumeration source.** The scan SHALL enumerate the published set as the repository's **tracked**
files under the plugin directory, because the plugin is published from the repository and tracked
files are exactly the files that ship. It SHALL NOT enumerate the working directory, which contains
untracked build and cache artifacts that never reach a consumer.

**The allowlist grows only with a stated reason.** Each allowlist entry SHALL carry a recorded
reason for the shape it admits, and the entry count SHALL be capped by a companion check at its size
when the convention landed, so the list can shrink freely but can grow only in a change that raises
the cap deliberately. A pattern added without a reason, or a cap raised silently, converts the
allowlist into a formality.

**Refusal, not warning.** When the scan finds a file matching no declared shape, the publication
workflow SHALL refuse to proceed and SHALL name every offending file in one run rather than stopping
at the first. It SHALL NOT offer to continue, and the offending file SHALL NOT be removed as part of
the release.

**A scan that inspected nothing is a failure.** The scan SHALL report how many files it examined,
and SHALL exit with a distinct "could not run" status — separable from both "clean" and "violations
found" — when the enumeration is empty or the enumeration command fails. An empty enumeration
reported as zero violations is indistinguishable from a clean tree and would certify the tree it
never read.

**The enforcement window is release-time only, and that is a stated tradeoff.** Drift introduced
between two releases SHALL NOT be expected to surface before the next release. This is accepted in
exchange for the check firing at the one deliberate gate the repo already has, rather than adding a
guard to the suite.

**The scan is not a shipped asset.** The scan SHALL live outside the plugin directory, with the
repo-local publication workflow it serves. Placing the check against shipping unusable assets inside
an asset a consumer cannot use would make it the first thing the check should have caught.

#### Scenario: An undeclared file shape blocks the release

- **WHEN** the publication workflow runs its preconditions and a tracked file under the plugin directory matches no declared shape on the allowlist
- **THEN** the workflow refuses to proceed and names that file by its repo-relative path
- **AND** no version bump is written and no tag is cut

#### Scenario: Every offending file is named in one run

- **WHEN** more than one tracked file under the plugin directory matches no declared shape
- **THEN** all of them are reported in that single run
- **AND** the scan does not stop at the first one

#### Scenario: The scan refuses to certify an empty enumeration

- **WHEN** the scan's enumeration of the published set yields no files, or the enumeration command fails
- **THEN** the scan reports a "could not run" status distinct from both a clean result and a violations result
- **AND** it does not report zero violations

#### Scenario: A clean scan states what it examined

- **WHEN** every enumerated file matches a declared shape
- **THEN** the scan reports the number of files examined and the number of patterns applied
- **AND** the publication workflow proceeds to its remaining preconditions

#### Scenario: The allowlist is enumerated with a reason per entry

- **WHEN** the allowlist is inspected
- **THEN** each entry records the reason the shape it admits is a consumer-usable asset
- **AND** a companion check caps the number of entries, so an entry can be added only by raising the cap in the same change

#### Scenario: The scan enumerates tracked files, not the working directory

- **WHEN** the plugin directory contains untracked cache or build artifacts
- **THEN** the scan does not report them, because they are not part of what is published
- **AND** a tracked file of an undeclared shape is still reported

#### Scenario: The scan lives outside the published tree

- **WHEN** the contents of the plugin directory are enumerated
- **THEN** the scan itself is not among them
- **AND** it resolves from the repo-local publication workflow's own directory

## MODIFIED Requirements

### Requirement: Shipped-asset boundary

The plugin directory `.claude/plugins/cla/` SHALL contain **only assets a consuming repo can use** —
skills it can invoke, agents and hooks that fire in its sessions, output styles it renders, scripts
those skills call, and the manifest and README that describe them. This is a structural obligation
rather than a convention, because the `cla` plugin is distributed as a `git-subdir` marketplace
entry, whose source descriptor supports `url`, `path`, `ref` and `sha` and **no exclusion field**:
everything under `path` ships, so what lives there is the only lever.

**What is excluded, and where it lives.** The plugin's own validation machinery — every test
directory, every mutation corpus, every pytest configuration, the mutation runner, and the checks
that assert facts about this repo's own source — SHALL live **outside** the plugin directory, at
`<repo>/plugin-tests/` in the canonical source repo. It SHALL be organised as a **single pytest
scope** with one `pyproject.toml`, and the repo's verification gate SHALL be a bare `pytest`
invocation over that scope; the plugin SHALL NOT ship an aggregating test runner, because a single
scope has nothing to aggregate. A separately-configured Node test suite MAY live in the same dev
tree and be run by its own command.

**Source-repo-only marking is by construction, not by declaration.** Because the dev tree is never
published, every asset in it is source-repo-only inherently. The plugin SHALL NOT carry per-directory
marker files declaring an asset source-repo-only, nor a guard that checks such markers, nor
skip logic in a runner that reads them — a mechanism whose whole subject is "which shipped assets do
not really ship" has no subject once nothing dev-only ships.

**A workflow about the plugin's own distribution is not a plugin workflow.** A skill whose subject is
publishing this plugin — editing the marketplace catalog at the source repo's root, editing that
repo's own release line, or cutting this plugin's release tags — operates on assets a consuming repo
does not own and cannot act on. Such a skill SHALL be a repo-local skill under
`<repo>/.claude/skills/<name>/` rather than a plugin skill, and SHALL resolve its paths repo-relative
rather than through `${CLAUDE_PLUGIN_ROOT}`.

**Dangling references are part of the boundary.** When an asset moves out of or is deleted from the
plugin, every shipped file that names it — a skill instruction, a precondition, a scanner's root
list — SHALL be re-pointed or pruned in the same change. A scanner that silently skips a root that no
longer exists SHALL have that root removed from its list rather than left to shrink the scan without
signal.

**How the boundary is enforced.** This boundary SHALL be verified mechanically at release time, by
the **Release-time shipped-asset scan** required of the publication workflow — not by a guard in the
repo's test suite. Enforcement at the publication gate is chosen because that is where the
consequence becomes irreversible: a published tag is what a consumer has already fetched and is never
moved, so the check belongs at the last point before that. The accepted cost is that drift
introduced between releases is not detected until the next one; the boundary is therefore a rule the
repo is expected to hold to while editing, with the scan as the backstop rather than the enforcement
of first resort.

**Documentation is inside the boundary, not adjacent to it.** A statement in this repo's own
documentation about what reaches a consuming repo — which assets ship, which checks fire downstream,
what a consumer can invoke — SHALL be true of the published tree. Such a statement SHALL NOT be
carried in a softened or narrowed form once it is false; it SHALL be deleted or replaced with what
is true. A false claim about the consumer's tree is the same defect class as a mis-shipped asset,
because both mislead about what the consumer received, and neither is visible from inside this repo.

#### Scenario: The published tree carries no validation machinery

- **WHEN** the contents of `.claude/plugins/cla/` are enumerated
- **THEN** no test directory, mutation corpus, `pyproject.toml`, or mutation runner is present
- **AND** every remaining file is an asset a consuming repo can invoke, read, or have fire on its behalf

#### Scenario: The dev tree is one scope with a bare gate

- **WHEN** the repo's test suite is run
- **THEN** it is invoked as a bare `pytest` over `<repo>/plugin-tests/`, needing no aggregating runner
- **AND** the dev tree carries exactly one `pyproject.toml`

#### Scenario: No source-repo-only marker mechanism survives

- **WHEN** the plugin and the dev tree are inspected
- **THEN** no per-directory source-repo-only marker file exists
- **AND** no guard asserts the presence or contents of such markers, and no runner skips a scope based on one

#### Scenario: The release workflow is repo-local

- **WHEN** the workflow that publishes this plugin is invoked
- **THEN** it resolves as a repo-local skill under `<repo>/.claude/skills/`, not under the plugin namespace
- **AND** it references its own files by repo-relative paths rather than `${CLAUDE_PLUGIN_ROOT}`

#### Scenario: A scan root removed from the tree is removed from the scanner

- **WHEN** a directory named in a shipped scanner's root list is moved out of the plugin
- **THEN** that entry is removed from the scanner's root list in the same change
- **AND** the scanner does not silently skip it and report a smaller scan as a clean result

#### Scenario: The boundary is checked at the publication gate

- **WHEN** a release of the plugin is prepared
- **THEN** the boundary is verified by the release-time shipped-asset scan before any tag is cut
- **AND** the repo's test suite does not carry a second guard duplicating that check

#### Scenario: A false claim about the consumer's tree is deleted, not reworded

- **WHEN** a statement in this repo's documentation asserts that some asset ships to, or fires in, a consuming repo, and the asset no longer does
- **THEN** the statement is removed rather than narrowed or qualified
- **AND** any surrounding text that remains true is preserved unchanged
