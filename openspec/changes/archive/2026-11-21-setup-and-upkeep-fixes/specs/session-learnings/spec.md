## MODIFIED Requirements

### Requirement: One prompt before anything is written

`/cla:codify-learnings` SHALL show each proposed fix's exact before and after text, then ask once which fixes to apply, all, none or chosen ones, SHALL write nothing, memory included, before the answer, and SHALL treat an empty answer as no consent, asking once more and taking a second empty answer as none.

#### Scenario: An empty answer twice

- **WHEN** the user answers the prompt with nothing, twice
- **THEN** no fix is applied and each is logged as rejected

#### Scenario: The text is shown first

- **WHEN** fixes are proposed
- **THEN** each one's exact before and after text appears above the prompt

### Requirement: A plugin fix goes upstream when the plugin is read-only

`/cla:codify-learnings` SHALL check whether the plugin is writable from the repo, and when it is not SHALL send a fix to a plugin file, including a shipped skill's bundled script, to `/cla:report-upstream` instead of editing the installed copy or a local overlay.

#### Scenario: An installed plugin

- **WHEN** the plugin is an installed copy outside the repo and a fix targets one of its skills
- **THEN** the fix's line names `/cla:report-upstream` as its target and the installed copy is not edited

#### Scenario: A bundled script

- **WHEN** a fix would change a shipped skill's bundled script and the plugin is read-only here
- **THEN** the fix is routed to `/cla:report-upstream`, not dropped and not edited
