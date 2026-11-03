---
name: hello
description: Say hello, and tour the Lua json global
runvil: 0
args:
  name:
    type: string
    optional: true
    description: Who to greet. Extra JSON fields, such as an ids list holding nulls, are kept in argv
models:
  writer: {}
output:
  path: report.md
  description: Every json result, followed by the greeting
---

# Hello World

```lua
models.default("writer")

-- Plain text arguments leave argv nil, so repair it here, while argv is
-- still writable. json.decode gives the nested null; json.array keeps tags a
-- list once argv is frozen.
if not argv then
    argv = { name = args ~= "" and args or nil }
end
argv.name = argv.name or "world"
argv.ids = argv.ids or json.decode("[1, null, 3]")
argv.tags = argv.tags or json.array()
store.write("report.md", "# Hello, json\n")
```

A minimal test prompt that also exercises every member of the `json` global.

## Encode

```lua
local function show(label, value)
    store.append("report.md", string.format("- %s: `%s`\n", label, tostring(value)))
end
local function heading(text)
    store.append("report.md", "\n## " .. text .. "\n\n")
end
local function caught(f, ...)
    local ok, err = pcall(f, ...)
    if ok then return "no error" end
    return string.format("[%s] %s", tostring(err.kind), tostring(err))
end

heading("json.encode")
show("keys are sorted and output is compact", json.encode({ b = 2, a = 1, list = { 1, 2, 3 } }))
show("a plain empty table is an object", json.encode({}))
show("json.array() stays a list when empty", json.encode(json.array()))
show("json.array(t) marks t in place", json.encode({ items = json.array({}) }))
show("json.null writes null", json.encode({ x = json.null }))
show("strings are escaped", json.encode({ s = 'quote " tab \t newline \n' }))
show("integers and floats", json.encode({ int = 42, float = 2.5 }))

heading("strict errors name the path")
show("a function", caught(json.encode, { items = { 1, 2, function() end } }))
show("a non-finite number", caught(json.encode, { n = 0 / 0 }))
local loop = {}
loop.self = loop
show("a cycle", caught(json.encode, loop))
show("mixed keys", caught(json.encode, { 1, 2, x = 3 }))

heading("debug mode never fails")
show("placeholders", json.encode({
    f = function() end,
    nan = 0 / 0,
    inf = math.huge,
    loop = loop,
}, { debug = true }))
show("only debug is an option", caught(json.encode, {}, { pretty = true }))

heading("json.encode_lines")
show("one JSON value per line", json.encode_lines({ { id = 1 }, { id = 2, tags = json.array() }, "three" }))
show("errors name the item", caught(json.encode_lines, { { name = "ok" }, { name = function() end } }))
```

## Decode

```lua
local function show(label, value)
    store.append("report.md", string.format("- %s: `%s`\n", label, tostring(value)))
end
local function heading(text)
    store.append("report.md", "\n## " .. text .. "\n\n")
end
local function caught(f, ...)
    local ok, err = pcall(f, ...)
    if ok then return "no error" end
    return string.format("[%s] %s", tostring(err.kind), tostring(err))
end

heading("json.decode")
local doc = json.decode('{"n": 42, "big": 1e3, "pi": 3.14, "none": null, "empty": [], "list": [1, 2]}')
show("i64 integers become Lua integers", math.type(doc.n))
show("every other number is a float", math.type(doc.big) .. ", " .. math.type(doc.pi))
show("null decodes to json.null", tostring(doc.none == json.null))
show("json.null is truthy", doc.none and "truthy" or "falsy")
show("decoded lists keep their mark", json.encode(doc.empty))
show("decoded tables are writable", (function()
    doc.list[#doc.list + 1] = 3
    return json.encode(doc.list)
end)())
show("a round trip", json.encode(doc))
show("a parse error", caught(json.decode, '{"a": 1,'))
show("one document only", caught(json.decode, "1 2"))

heading("json.decode_lines")
local values = json.decode_lines('1 "two"\n{"three": 3}\n\n[4]')
show("any whitespace separates values", #values .. " values")
show("they come back as a list", json.encode(values))
show("an empty stream is an empty list", json.encode(json.decode_lines("  \n ")))
```

## Arguments

```lua
local function show(label, value)
    store.append("report.md", string.format("- %s: `%s`\n", label, tostring(value)))
end
local function heading(text)
    store.append("report.md", "\n## " .. text .. "\n\n")
end
local function caught(f, ...)
    local ok, err = pcall(f, ...)
    if ok then return "no error" end
    return string.format("[%s] %s", tostring(err.kind), tostring(err))
end

heading("frozen argv")
show("json.encode(argv) returns the stored data", json.encode(argv))
show("a nested null reads as json.null", tostring(argv.ids[2] == json.null))
show("so # still counts it", #argv.ids)
show("argv is frozen outside the H1 pass", caught(function() argv.name = "changed" end))
```

## Greet

```lua
var.person = { name = argv.name, languages = { "English", "Spanish", "French" } }
var.extras = json.array()
```

Here is a person, as JSON: {{ var.person }}

This list is empty and renders as a JSON list: {{ var.extras }}

Greet the person in each of their languages. Reply with only a JSON object of
the form `{"greetings": [{"language": "...", "text": "..."}]}`, with no code
fence and no other text.

```lua
local function show(label, value)
    store.append("report.md", string.format("- %s: `%s`\n", label, tostring(value)))
end
local function heading(text)
    store.append("report.md", "\n## " .. text .. "\n\n")
end
local function caught(f, ...)
    local ok, err = pcall(f, ...)
    if ok then return "no error" end
    return string.format("[%s] %s", tostring(err.kind), tostring(err))
end

local reply = models.infer(prose)
local body = reply:match("^%s*```%w*%s*(.-)%s*```%s*$") or reply
heading("greeting")
local ok, parsed = pcall(json.decode, body)
if ok and type(parsed) == "table" and type(parsed.greetings) == "table" then
    show("greetings", #parsed.greetings)
    for _, greeting in ipairs(parsed.greetings) do
        show(tostring(greeting.language), tostring(greeting.text))
    end
    show("re-encoded as JSON Lines", json.encode_lines(parsed.greetings))
else
    show("the reply was not the requested JSON", caught(json.decode, body))
    store.append("report.md", "\n" .. reply .. "\n")
end
```
