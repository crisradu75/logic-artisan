# `cla.io/terminology.md` — what it holds and its entry format

Read by `shape-decision`, which writes entries, and `cla-setup`, which reconciles them.

`cla.io/terminology.md` holds this repo's **internal naming**: one-sentence definitions of concepts
specific to its own code or product, each naming the aliases to avoid. It holds no mechanical facts
(those are in `cla.io/project-facts.md`) and no external, regulatory or business glossary; a repo's
own glossary of that kind is never read or changed.

Entry format:

```
**Term**: one-sentence definition — what it IS, not what it does.
_Avoid_: rejected-alias-1, rejected-alias-2
```

- **Written inline**, in the session where the term is settled, by the skill that settled it.
- **Created lazily** by the first skill that needs it; nothing scaffolds it.
- **Absent is never an error**: a skill reading it uses the file's term when present and its own
  judgement otherwise.
