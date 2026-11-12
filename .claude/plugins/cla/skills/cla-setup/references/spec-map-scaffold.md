Detail for "The spec map scaffold" in `SKILL.md`. Moved verbatim from `SKILL.md`.

### The spec map scaffold

A repo with many specs can keep one file that bridges its levels: **capabilities** (what the product
offers), then the **workflows** that deliver them (a user's journey, as ordered steps), then the
**specs** each workflow step links. It holds links only: no configurable value and no restated rule.
This skill offers a default scaffold and never imposes one.

- **When to offer.** `openspec/specs/` exists and the facts file has no `## Spec map` section.
  Offer once per run, with the recommended path `openspec/spec-map.md`. The user may name any
  other path inside the repo, never under the plugin tree; a path that already exists is never overwritten, so ask for another.
- **On yes.** Write the scaffold below at the chosen path with `Write`, with one bullet under
  "Specs not yet placed" per spec under `openspec/specs/` and per spec an open change adds (each link to `openspec/specs/<name>/spec.md`, relative to the map's folder), and add the path
  under a `## Spec map` heading in the facts file. The map then passes `check_spec_proof.py` at
  once, and the user moves each spec into the workflow step it governs.
- **On no.** Write no map and no heading. Say that the checker then reports nothing about a map.
- **Declaring a map has a cost.** From then on `check_spec_proof.py` fails on a spec (live, or added by a change in progress) no map
  file links and on a link to a spec that does not exist. Say so when offering.

````markdown
# Spec map

Links only: a rule lives in its spec, a value in its config.

## Capabilities

- **<Capability, one line>.** Delivered by <workflow name>.

## Workflows

### <Workflow name>

1. <Step>: link the spec this step governs, moved from "Specs not yet placed".

## Specs not yet placed

- [<spec name>](<path to openspec/specs/<spec name>/spec.md, relative to this file>)
````
