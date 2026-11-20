---
name: summarize
description: Summarize a paper with its metadata, then critique the summary
runvil: 0
uses: [mcp]
prompts: [critique.md]
args:
  type: object
  properties:
    paper: { type: string, description: The paper's text }
    paper_id: { type: string, description: "The paper's id, such as P3045R9" }
  required: [paper, paper_id]
---

## Main

```lua
local meta = json.decode(tools.call("mcp/call_dynamic_tool", {
  namespace = "wg21-papers",
  toolName = "get_metadata",
  arguments = { paper = args.paper_id },
}))

local summary = models.infer(meta.title .. "\n\nSummarize:\n\n" .. untrusted(args.paper))
local critique = execute("critique.md", { paper = args.paper, summary = summary })
return summary .. "\n\n---\n\n" .. critique
```
