---
name: summarize
description: Summarize a paper with its metadata, then critique the summary
runvil: 0
uses: [mcp]
args:
  paper:
    type: string
  paper_id:
    type: string
---

# Summarize

## Main

```lua
local meta = json.decode(tools.call("mcp/call_dynamic_tool", {
  namespace = "wg21-papers",
  toolName = "get_metadata",
  arguments = { paper = argv.paper_id },
}))

local summary = models.infer(meta.title .. "\n\nSummarize:\n\n" .. untrusted(argv.paper))
local critique = execute("critique.md", { paper = argv.paper, summary = summary })
return summary .. "\n\n---\n\n" .. critique
```
