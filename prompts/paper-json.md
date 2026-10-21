---
name: paper-json
description: Read a WG21 mailing from the paper-mcp server and parse the JSON it returns
runvil: 0
plugins:
  - wg21-papers
models:
  writer: {}
output:
  path: report.md
  description: The parsed results of each tool call, in markdown
---

# Paper JSON

```lua
models.default("writer")
```

## Read

```lua
local function show(label, value)
    store.append("report.md", string.format("- %s: `%s`\n", label, tostring(value)))
end

local function heading(text)
    store.append("report.md", "\n## " .. text .. "\n\n")
end

-- An MCP tool call returns the server's CallToolResult as a table. The JSON
-- is the first text block; each resource_link block is returned separately.
local function call_json(tool, arguments)
    local result = tools.call(tool, arguments)
    local body = ""
    local resources = json.array()
    for _, block in ipairs(result.content) do
        if block.type == "text" and body == "" then
            body = block.text
        elseif block.type == "resource_link" then
            table.insert(resources, block.uri)
        end
    end
    local ok, value = pcall(json.decode, body)
    if not ok then
        error(string.format("%s did not return JSON: %s\n%s", tool, tostring(value), body:sub(1, 500)))
    end
    return value, resources
end

-- The server answers with `{cols, rows}` tables; this turns each row into an
-- object keyed by column name.
local function records(doc)
    local out = json.array()
    for _, row in ipairs(doc.rows) do
        local record = {}
        for i, col in ipairs(doc.cols) do
            record[col] = row[i]
        end
        table.insert(out, record)
    end
    return out
end

local mailing = tostring(args or ""):gsub("%s+", "")
if mailing == "" then
    mailing = "latest"
end
store.write("report.md", "# WG21 mailing " .. mailing .. " through paper-mcp\n")

heading("wg21-papers/list_mailings")
local mailings = records(call_json("wg21-papers/list_mailings", {}))
local total = 0
for _, m in ipairs(mailings) do
    total = total + m.papers
end
show("mailings", #mailings)
show("papers across them", total)
show("newest", json.encode(mailings[1]))
show("oldest", json.encode(mailings[#mailings]))

heading("wg21-papers/list_mailing_papers")
local listing = call_json("wg21-papers/list_mailing_papers", { mailing_id = mailing })
local papers = records(listing)
show("mailing", listing.mailing)
show("label", listing.label == "" and "(none)" or listing.label)
show("papers", listing.n)
show("columns", json.encode(listing.cols))

local by_group = {}
local by_format = {}
for _, paper in ipairs(papers) do
    for raw in tostring(paper.group):gmatch("[^,]+") do
        local group = raw:match("^%s*(.-)%s*$")
        by_group[group] = (by_group[group] or 0) + 1
    end
    local format = tostring(paper.fmt)
    by_format[format] = (by_format[format] or 0) + 1
end
show("papers per group", json.encode(by_group))
show("papers per format", json.encode(by_format))

local proposals = json.array()
for _, paper in ipairs(papers) do
    if tostring(paper.id):match("^P") and #proposals < 5 then
        table.insert(proposals, paper)
    end
end
store.append("report.md", "\nFirst proposals, as JSON Lines:\n\n```jsonl\n"
    .. json.encode_lines(proposals) .. "```\n")

heading("wg21-papers/get_paper_download_url")
local ids = {}
for _, paper in ipairs(proposals) do
    table.insert(ids, paper.id)
end
local urls, resources = call_json("wg21-papers/get_paper_download_url", { papers = table.concat(ids, ",") })
show("asked for", table.concat(ids, ", "))
show("expires", urls.expires)
for _, file in ipairs(records(urls)) do
    show(file.id .. " (" .. file.bytes .. " bytes)", file.url)
end
for _, failure in ipairs(urls.errors or {}) do
    show(failure[1], "error: " .. tostring(failure[2]))
end
show("resource links after the JSON", #resources)
```
