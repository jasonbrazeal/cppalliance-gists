---
name: lint-errors
description: One deliberate mistake per line, for testing the parse-time Lua checks
runvil: 0
prompts: [lint-errors.md]
---

Every section below holds one kind of mistake. This prompt is not meant to run.

## 01 Clean

Valid Lua with no mistakes.

```lua
local greeting = "hello"
var.greeting = greeting
log(greeting)
```

## 02 Syntax error

One syntax error.

```lua
local total = 1 +
```

## 03 Second syntax error

A second block with a syntax error.

```lua
if var.ready then
    log("ready")
else
elseif var.late then
    log("late")
end
```

## 04 Two syntax errors in one block

Two separate syntax errors in the same block.

```lua
local first = (1 + 2
local ok = true
local second = { 1, 2
```

## 05 Compile errors past the grammar

Each block is grammatical, and the Lua compiler still refuses it.

```lua
local limit <const> = 10
limit = 20
```

Assignment to a loop variable, new in Lua 5.5.

```lua
for index = 1, 3 do
    index = index + 1
end
```

A `goto` into the scope of a local.

```lua
goto done
local value = 1
::done::
log(tostring(value))
```

A `break` outside a loop.

```lua
break
```

## 06 Unknown globals

Names that nothing defines, and names the sandbox removes.

```lua
local result = models.infer("Say hi.")
log(resutl)
print(result)
local file = io.open("x")
jmup('../01 Clean')
```

## 07 Misspelled members

The global exists, and the function on it does not.

```lua
local text = prompt.sectoin('/09 Helpers')
local reply = models.infr(text)
store.wirte("out.md", reply)
return json.encod({ reply = reply })
```

## 08 Wrong argument counts

`log` takes exactly one string, and `jump` needs a target.

```lua
log()
log("a", "b")
jump()
```

## 09 Helpers

A real library section, so the valid paths below have a target.

```lua
function shout(text)
    return string.upper(text)
end
return { shout = shout }
```

### Inner

```lua
return "inner"
```

## 10 Section paths

Literal section paths, some that name a section and some that do not.

```lua
local lib = require('/09 Helpers')
local inner = prompt.section('/09 Helpers/Inner')
local worker = call('Worker')
local missing = call('Wroker')
local cousin = call('../09 Helpers/Inner')
local text = prompt.section('/09 Helpers/Outer')
local maybe = prompt.section_or('/No Such')
local typo = require('/09 Helprs')
local relative = require('../09 Helpers')
jump('../Nowhere')
```

### Worker

```lua
return "worked"
```

## 11 Execute

`prompts:` lists only `lint-errors.md`.

```lua
local same = execute('lint-errors.md', { text = "again" })
local other = execute('review.md')
```

## 12 Unknown sys fields and messages methods

```lua
log(sys.sectoin_name)
messages:usr("Say hi.")
```

## 13 Model roles and tool ids

```lua
models.use('stronk')
local handle = models.get('smal')
local page = tools.call('websearch', { query = "lua" })
local tool = tools.get('web/')
log(handle.name .. page .. tool.id)
```

## 14 Store paths

```lua
store.write('/absolute.md', "x")
local up = store.read('../outside.md')
store.write('drafts\\plan.md', "x")
local drive = store.read('C:notes.md')
log(up .. drive)
```

## 15 Placeholders in prose

An unclosed one {{ var.name and an empty one {{ }}.

A recursive one {{ prose }}, bare roots {{ var }} and {{ sys }}, and an unknown field {{ sys.bogus }}.

```lua
return models.infer(prose)
```

## 16 Argument types and options

```lua
jump(3)
log({})
models.use('fast', { temp = 0 })
local text = json.encode({}, { pretty = true })
log('line one\nline two')
log("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
log(text)
```

## 17 Unused names and values

```lua
local reply = models.infer("Say hi.")

local function first(a, b)
    return a
end

::retry::

local x = models.infer("one")
x = "two"
log(x)

local c, d = 1
local e = 1, 2
log(first(c, d) .. e)
```

## 18 Shadowing and globals

```lua
local count = 1
local count = 2
log(tostring(count))

local json = { encode = function() return "" end }
log(json.encode())

local outer = 1
do
    local outer = 2
    log(tostring(outer))
end
log(tostring(outer))

unused_total = 0

string.trim = function(s) return s end
prompt.summary = function() return "summary" end

prompt = {}
jump = nil
```

## 19 Control flow

```lua
local items = { "a", "b" }
for _, item in ipairs(items) do
    return item
end

if #items > 5 then end
do end

while #items > 0 do
    break
    log("after break")
end

do return end
log("after return")
```

The same after `jump` and `error`.

```lua
jump('../01 Clean')
log("after jump")
```

```lua
error("stop")
log("after error")
```

## 20 Global across sections

A global set in one section and read in another.

### Setter

```lua
total = 0
```

### Reader

```lua
log(tostring(total))
```

## 21 Unread placeholder

```lua
log("before the prose")
```

Prose after the last block, which no block reads: Hello, {{ var.name }}.

## 22 Missing untrusted

```lua
local page = store.read('page.md')
local summary = models.infer("Summarize:\n\n" .. page)
local data = json.decode(store.read('data.json'))
messages:user(data.text)
models.infer(store.read_numbered('notes.md'))
log(summary)
```

## 23 Turning checks off

```lua
local kept = models.infer("x")  -- runvil: allow unused-local
local a, b = 1  -- runvil: allow unbalanced-assignment, unused-local
local json = { encode = function() return "" end }  -- runvil: allow shadowed-name
log(json.encode())
log()  -- runvil: allow wrong-argument-count
local plain = 1  -- runvil: allow not-a-check
log(tostring(plain))
```

## 24 Lookalikes

Valid code that resembles the mistakes above.

```lua
-- A comment that says require('/No Such Library') and prompt.sectoin().
local note = "call('Nowhere') and jump('../Nowhere') inside a string"

-- A path computed at run time cannot be checked.
local target = var.next or '10 Section paths'
local body = prompt.section('/' .. target)

-- A local that shadows an Engine global is not that global.
local prompt = { sectoin = function() return "mine" end }  -- runvil: allow shadowed-name
local mine = prompt.sectoin()
log(mine)

-- A global this block defines, and one the required library defines.
counter = 1
counter = counter + 1
require('/09 Helpers')
local loud = shout(note)

-- The documented pattern for default values of globals.
setmetatable(_G, { __index = function() return 0 end })
local fallback = anything_at_all + 1
log(tostring(fallback))

-- A guarded call of a function that may be missing.
local ok, err = pcall(function() return models.infer(body) end)
return ok and loud or tostring(err)
```
