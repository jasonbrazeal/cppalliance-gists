---
name: critique
description: Check a summary against the paper
runvil: 0
args:
 paper:
   type: string
 summary:
   type: string
---

# Critique

## Main

```lua
return models.infer("Paper:\n\n" .. untrusted(argv.paper)
 .. "\n\nList anything this summary gets wrong:\n\n" .. argv.summary)
```
