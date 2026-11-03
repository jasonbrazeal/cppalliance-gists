---
name: paper-json
description: Read a WG21 mailing from the paper-mcp server and parse the JSON it returns
runvil: 0
uses:
  - mcp
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

-- The mcp Pack connects to its servers in the background, so a run that
-- calls a tool at once finds wg21-papers still loading. This polls the
-- server's status until it is ready, and fails with its reason on error.
local function wait_for_papers()
    for _ = 1, 20000 do
        local entry = json.decode(tools.call("mcp/get_dynamic_tools", { namespace = "wg21-papers" }))
        if entry.status == "ready" then
            return
        elseif entry.status == "error" then
            error("the wg21-papers MCP server failed to start: " .. tostring(entry.reason))
        end
    end
    error("the wg21-papers MCP server did not become ready")
end

-- The mcp Pack answers a script's call with the server's text: its text
-- blocks joined by blank lines, and each resource link as a
-- `[resource: <uri>]` line. The JSON is what remains once the links are
-- taken out.
local function call_json(tool, arguments)
    local request = { namespace = "wg21-papers", toolName = tool }
    if next(arguments) ~= nil then
        request.arguments = arguments
    end
    local text = tools.call("mcp/call_dynamic_tool", request)
    local resources = json.array()
    for uri in text:gmatch("%[resource: ([^%]]+)%]") do
        table.insert(resources, uri)
    end
    local body = text:gsub("%[resource: [^%]]+%]", ""):match("^%s*(.-)%s*$")
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

wait_for_papers()

local mailing = tostring(args or ""):gsub("%s+", "")
if mailing == "" then
    mailing = "latest"
end
store.write("report.md", "# WG21 mailing " .. mailing .. " through paper-mcp\n")

heading("wg21-papers/list_mailings")
local mailings = records(call_json("list_mailings", {}))
local total = 0
for _, m in ipairs(mailings) do
    total = total + m.papers
end
show("mailings", #mailings)
show("papers across them", total)
show("newest", json.encode(mailings[1]))
show("oldest", json.encode(mailings[#mailings]))

heading("wg21-papers/list_mailing_papers")
local listing = call_json("list_mailing_papers", { mailing_id = mailing })
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
local urls, resources = call_json("get_paper_download_url", { papers = table.concat(ids, ",") })
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
