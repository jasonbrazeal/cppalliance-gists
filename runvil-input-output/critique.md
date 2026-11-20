---
name: critique
description: Check a summary against the paper
runvil: 0
args:
  type: object
  properties:
    paper: { type: string, description: The paper's text }
    summary: { type: string, description: The summary to check }
  required: [paper, summary]
---

## Main

```lua
return models.infer("Paper:\n\n" .. untrusted(args.paper)
 .. "\n\nList anything this summary gets wrong:\n\n" .. args.summary)
```
