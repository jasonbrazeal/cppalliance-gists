---
name: paper-json
description: Tour every tool of the Rust paper-mcp server for one WG21 paper and parse the JSON each returns
runvil: 0
uses:
  - mcp
output:
  path: report.md
  description: The parsed results of each tool call, in markdown
---

# Paper JSON

Pass a paper id with `--args`, such as `--args P2728R14`; the default is
`P3045R9`. The paper must be indexed in the server's Qdrant.

## Read

```lua
local NAMESPACE = "wg21-papers"

local function show(label, value)
    store.append("report.md", string.format("- %s: `%s`\n", label, tostring(value)))
end

local function heading(text)
    store.append("report.md", "\n## " .. text .. "\n\n")
end

-- The mcp Pack connects to its servers in the background, so a run that
-- calls a tool at once finds the server still loading. This polls its
-- status until it is ready, and fails with its reason on error.
local function wait_for_server()
    for _ = 1, 20000 do
        local entry = json.decode(tools.call("mcp/get_dynamic_tools", { namespace = NAMESPACE }))
        if entry.status == "ready" then
            return entry
        elseif entry.status == "error" then
            error("the " .. NAMESPACE .. " MCP server failed to start: " .. tostring(entry.reason))
        end
    end
    error("the " .. NAMESPACE .. " MCP server did not become ready")
end

-- The mcp Pack answers a script's call with the server's text, which for
-- every paper-mcp tool is one JSON object.
local function call_json(tool, arguments)
    local text = tools.call("mcp/call_dynamic_tool",
        { namespace = NAMESPACE, toolName = tool, arguments = arguments })
    local ok, value = pcall(json.decode, text)
    if not ok then
        error(string.format("%s did not return JSON: %s\n%s", tool, tostring(value), text:sub(1, 500)))
    end
    return value
end

local function first_line(text)
    return (tostring(text):match("^%s*([^\n]*)") or ""):sub(1, 120)
end

local paper = tostring(args or ""):gsub("%s+", "")
if paper == "" then
    paper = "P3045R9"
end
store.write("report.md", "# " .. paper .. " through the Rust paper-mcp server\n")

heading("The server's tools")
local listing = wait_for_server()
local names = {}
for _, tool in ipairs(listing.tools) do
    table.insert(names, tool.tool)
end
show("tools", table.concat(names, ", "))

heading("get_metadata")
local meta = call_json("get_metadata", { paper = paper })
show("paper_id", meta.paper_id)
show("title", meta.title)
show("authors", table.concat(meta.authors, "; "))
show("group", meta.group)
show("document_date", meta.document_date)
show("mailing_date", meta.mailing_date)
show("previous_version", meta.previous_version == "" and "(none)" or meta.previous_version)
show("has_markdown", meta.has_markdown)
show("total_lines", meta.total_lines)
show("total_sections", meta.total_sections)

heading("list_revisions")
local number = paper:match("^[PDpd]%d+") or paper
local chain = call_json("list_revisions", { paper = number })
for _, revision in ipairs(chain.revisions) do
    show(revision.paper_id, string.format("dated %s, indexed %s",
        revision.document_date == "" and "unknown" or revision.document_date,
        tostring(revision.indexed)))
end

heading("get_outline")
local outline = call_json("get_outline", { paper = paper })
show("headings", #outline.headings)
local top = json.array()
for _, h in ipairs(outline.headings) do
    if h.level == 2 and #top < 8 then
        table.insert(top, { line = h.line, section = h.section_index, text = h.text })
    end
end
store.append("report.md", "\nThe first top-level headings, as JSON Lines:\n\n```jsonl\n"
    .. json.encode_lines(top) .. "```\n")

heading("get_sections")
local sections = call_json("get_sections", { paper = paper, first = 2, last = 3 })
for _, section in ipairs(sections.sections) do
    show(string.format("section %d, lines %d-%d", section.section_index,
        section.first_line, section.last_line), section.heading)
    show("  characters", #section.text)
end

heading("get_lines")
local lines = call_json("get_lines", { paper = paper, first = -3 })
show("range", string.format("%d-%d of %d", lines.first, lines.last, lines.total_lines))
store.append("report.md", "\n```text\n" .. lines.text .. "\n```\n")

heading("get_citations")
local citations = call_json("get_citations", { paper = paper, direction = "both" })
show("citations_extracted", citations.citations_extracted)
local cites = citations.cites or {}
show("cites", #cites)
show("cited_by", #(citations.cited_by or {}))
for i = 1, math.min(5, #cites) do
    show("  " .. cites[i].paper_id, cites[i].count .. " mentions")
end

heading("search")
local query = meta.title
for _, kind in ipairs({ "fulltext", "vector", "hybrid" }) do
    local found = call_json("search", { query = query, type = kind, papers = { paper }, limit = 3 })
    show(kind .. " hits for \"" .. query .. "\"", #found.results)
    for _, hit in ipairs(found.results) do
        show(string.format("  lines %d-%d (%.2f)", hit.first_line, hit.last_line, hit.score),
            hit.heading_path ~= "" and hit.heading_path or first_line(hit.text))
    end
end

local page = call_json("search", { query = query, type = "hybrid", limit = 2 })
show("across every paper, page 1", #page.results)
if page.nextCursor then
    local next_page = call_json("search", { query = query, type = "hybrid", limit = 2, cursor = page.nextCursor })
    show("page 2, through nextCursor", #next_page.results)
end

heading("search_metadata")
local related = call_json("search_metadata", { query = meta.title, limit = 5 })
for _, result in ipairs(related.results) do
    show(result.paper_id, string.format("%s (%.2f)", result.title, result.score))
end
local recent = call_json("search_metadata", { author = meta.authors[1], limit = 5 })
show("newest papers by " .. meta.authors[1], #recent.results)
for _, result in ipairs(recent.results) do
    show("  " .. result.paper_id, result.document_date .. "  " .. result.title)
end

return "Done."
```
