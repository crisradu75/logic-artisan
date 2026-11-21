# An HTML document is shown as its author designed it

Its own styling and layout are the point — for a designed document they are part
of what the reader is being asked to judge — so the page carries it in a frame
rather than re-rendering its words. Three conditions are reported and are worth
knowing before you pass one through, because each is a state the reader cannot see:

- **It has to be SERVED.** A page opened from disk gives both documents opaque
  origins, so the layer cannot reach the document and the page renders empty. The
  page detects this and says so, but the fix is to run the server and open
  the URL it prints.
- **A document already using `data-blk`, `data-line` or `data-sec` is refused.** A
  repeated attribute resolves to the author's value, so every annotation in that
  element would anchor to whatever it named, invisibly. Report the refusal, and say
  what would clear it: those three names are the skill's own, so the document has to
  stop using them before it can be annotated. Do not work around it.
- **A document with relative asset references warns and still renders.** Its images
  or stylesheets will not resolve from the page directory. The reader can see that
  for themselves, which is why this warns rather than refusing.
