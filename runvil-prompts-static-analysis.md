# Runvil: Static Analysis of Prompts

## Goal

Before a run starts, `Prompt::parse` reports all the problems it can find from the prompt's text alone:

- syntax errors, in all blocks;
- misspelled built-ins, such as `prompt.sectoin`, `models.infr`, or `jmup(...)`;
- literal strings that name something which does not exist, such as a section, a listed prompt, or a model role;
- calls of built-in functions with the wrong arguments, where that is visible in the source: too few or too many, as in `log()` or `log('a', 'b')`, or a constant of the wrong type, as in `jump(3)`;
- code that runs but is probably a mistake, such as an unused local, code after a `jump(...)`, or a global set in one section and read in another.

## Today

- `Prompt::parse` compiles each Lua block through mlua (Lua 5.5) and returns at the first failure.
- No syntax tree exists to read. mlua is a Rust binding: it hands the source to the reference Lua compiler, written in C, and returns the compiled function. That compiler is single-pass: it writes bytecode as it reads each statement and never builds a tree in memory. The only output is the bytecode.
- A bad section path or prompt name fails only when its line runs.

## Design

1. **Parser.** A new Engine crate holds a Lua 5.5 lexer, parser, and scope pass that produce an AST (abstract syntax tree) with prompt line numbers. It is our own code, adapted from `luck_parser` (MIT, notice retained), cut down to 5.5 only. No general Lua linter is used. After a syntax error the parser recovers and parses the rest of the block, so one block reports every syntax error it has, and the other checks still run on the parts that parsed.
2. **mlua stays.** It still compiles every block, since the run needs its bytecode, and its accept or reject answer is the reference.
3. **Checks.** `runvil-prompt` walks each block's tree after the sections and front matter are known. An error is reported only when it is airtight (see "What makes an error"). Everything less certain is a warning or a lint.
4. **Language table.** One data structure in `runvil-lua` describes the Lua side of the Runvil language. It replaces `RESERVED_NAMES` and the prelude's `VISIBLE_GLOBALS` list, which become views of it, so the run and the checks read the same facts:

   - **Every name:** each Engine global, each Lua global the sandbox keeps, each one it removes, and each Lua keyword, with its kind.
   - **Every member:** the functions and fields of each Engine and Lua table, `sys` fields, and `messages` methods.
   - **Every function:** the fewest and most arguments it takes, whether it raises on extra arguments, the types it refuses for each argument, its option keys, and its call forms, such as `tasks.fanout` with or without a model first.
   - **What a Pack prelude can reach:** the globals a prelude reads, which are the tables it can add members to.

   It serves two purposes:

   - **The run:** a prelude that defines a reserved name is refused, as `RESERVED_NAMES` does today, and a prelude's environment holds the globals the table marks as visible, as `VISIBLE_GLOBALS` does today.
   - **The checks:** every name, member, argument, and stand-down rule in this design reads from it.

   Tests keep it equal to the code:

   - **Names.** A test builds a set-up section VM, walks every Engine table in it, and compares the names with the table in both directions, as the test of `RESERVED_NAMES` does. A member added to the code and left out of the table fails, and so does the reverse.
   - **Arguments.** The counts and types cannot be read from the code, since most built-ins are Rust closures that check their own arguments. A test therefore calls every function in the table with one argument too few, one too many, and each refused type, and requires that the real function raises exactly when the table says it does. Many functions ignore extra arguments, as `store.exists`, `json.decode`, `untrusted`, and `models.current` do today, and the table records that.
   - **Coverage.** The argument test walks the table, so a function with no entry fails the test.
5. **Result.** `Prompt::parse` returns a list of problems in place of one error. Each problem has:

   - **A group:** error or warning (see Checks).
   - **A check name** that says what kind of mistake it is, one per row in the tables below, such as `syntax`, `unknown-member`, `unknown-section`, `wrong-argument-count`, or `unused-local`.
   - **A location:** the prompt file, the line, and the columns of the exact name or string at fault.
   - **A message** that states what is wrong and what was expected, in full, so that a model or a person can fix it from the message alone.
   - **A suggestion** when a known name is close to the one written: the nearest built-in, member, section, or listed prompt.

   The text follows the style of the Rust compiler and of Python's newer error messages:

   ```
   error[unknown-member]: `prompt` has no function `sectoin`
     --> lint-errors.md:100:21
       |
   100 | local text = prompt.sectoin('/09 Helpers')
       |                     ^^^^^^^ did you mean `section`?

   error[unknown-section]: no section `/09 Helprs`
     --> lint-errors.md:145:22
       |
   145 | local typo = require('/09 Helprs')
       |                      ^^^^^^^^^^^^ did you mean `/09 Helpers`?

   error[wrong-argument-count]: `log` takes 1 argument, got 2
     --> lint-errors.md:112:1
       |
   112 | log("a", "b")
       | ^^^^^^^^^^^^^

   warning[unreachable-code]: this line never runs
     --> example.md:42:1
      |
   41 | jump('../Next')
      | --------------- `jump` ends the block here
   42 | log("moved on")
      | ^^^^^^^^^^^^^^^
   ```

## Checks

Each check belongs to one group:

| Group | Meaning | Effect |
|---|---|---|
| **Error** | Fails every time it runs | The prompt fails to parse |
| **Warning** | Probably a mistake, or fails only under some Hosts | Reported; the prompt parses |

Every check runs on every parse. A caller chooses which warnings to show, by check name.

### What makes an error

An error is an operation that fails every time it runs, whatever the Host, its Packs, the arguments the run gets, the section that calls the code, and the state of the run. Code that may never run, such as `if false then prompt.sectoin() end`, and a failure that a `pcall` around it would catch, still count, since the code is wrong either way. Anything short of that is never an error.

Each error check stands down when one of these could make the code valid. It then reports nothing, or a warning where the table below says so.

| Stand-down rule | Example | Effect |
|---|---|---|
| The name is the author's own local | `local prompt = { sectoin = f }` then `prompt.sectoin()` | Not checked |
| The value is worked out at run time | `jump('../' .. var.next)` | Not checked |
| The prompt rebinds the built-in | `sys = {...}`, `_G.jump = f`, anywhere in the prompt | Not checked. A write to `_G` with a computed key turns off every check on built-in names in the prompt |
| The prompt can add members to the table | `prompt.summary = f`, `prompt[k] = f`, `setmetatable(prompt, mt)`, or the table passed to a function or stored in a variable | Member checks on that table are off. A named member write turns off only that member |
| A Pack prelude can reach the table | `string`, `table`, `math`, `utf8`, `tools`, `store`, `json` | When the prompt declares any Pack under `uses:`, every check on these tables' members, arguments, and values is a warning. With no Pack declared, no prelude runs, and they stay errors |
| A Pack prelude can define the global | `jmup('x')`, `print(x)` | When the prompt declares any Pack, an unknown global is a warning. With none, calling or indexing it is an error |
| The code runs from another section | A relative `call('Worker')` in a section that `require` loads | The path must fail from the section's own place and from every section that requires it. A `require` with a computed path turns relative path checks into warnings in the whole prompt |
| The section's globals can come from elsewhere | `setmetatable(_G, { __index = ... })` | Unknown-global checks are off in that section and in the sections that `require` it |

The test prompt proves both sides: every error case fails when it runs, and every stand-down case runs clean (see Testing).

### Errors

#### Syntax

| Check | Rule |
|---|---|
| Syntax error | Any block that mlua rejects. Our parser reports every error it finds in that block, and mlua's answer decides whether the block is invalid |
| Compile error past the grammar | Assignment to a `<const>` or loop variable, `goto` into a local's scope, a missing or repeated label, `break` outside a loop, an undeclared name under `global` |

#### Names

Reading a missing member or an undefined global gives nil and does not fail, so only a call or a further index is an error. A plain read is a warning.

| Check | Example | Rule |
|---|---|---|
| Missing member, called or indexed | `prompt.sectoin(p)`, `models.infr(p)`, `store.wirte(p, t)` | A member that the table lacks |
| Unknown global, called or indexed | `jmup('../A')`, `print(x)` | A name that no block of the section, and no section it requires, assigns, and that is no Engine or Lua global. A global the sandbox removes counts as unknown |
| Unknown `sys` field | `sys.sectoin_name` | A field outside the full set, including the ones present only sometimes, `index` and `model`. Any read fails |
| Unknown method of `messages` | `messages:usr(text)` | A method outside the fixed set. The list's metatable is locked, so no code can add one |

#### String identifiers

| Check | Applies to | Rule |
|---|---|---|
| Section path, relative | `call`, `jump`, `tasks.spawn`, `tasks.fanout` | Form is `name` or `../name`; the target is a sibling or a direct child of the section the code runs in |
| Section path, any form | `prompt.section`, `prompt.section_or` | `name`, `../name`, or `/a/b` names an existing section. `prompt.section_or` returns nil for a miss, so only a malformed path is an error there |
| Section path, from the top | `require` | Form is `/a/b` and names an existing section |
| Block selector | `prompt.section(path, selector, n)` | The selector matches a block of the section the path names, and `n` is within the matches |
| Prompt name | `execute` | The name is listed under this prompt's `prompts:` |
| Arguments of `execute` | `execute('review.md', { ... })` | A literal table or string matches the executed prompt's `args:` declaration: no undeclared field in a closed object, no literal of the wrong type, no missing required field |
| Argument field in prose | `{{ args.qurey }}` in prose that a block reads | The field exists in this prompt's `args:` declaration, or the object is open |
| Model role | `models.use` | One of `default`, `strong`, `small`, `fast`, `creative`. `models.get` also takes raw model ids, so it is not checked |
| Tool id | `tools.call`, `tools.offer` | `tools.call` takes the `pack/name` shape; `tools.offer` takes that shape or a Pack id. `tools.get` returns nil for any miss, so it is a warning |
| Store path | `store.*` | The path rules: no leading `/`, backslash, colon, or `.` and `..` segment |
| Placeholder in prose | `{{ ... }}` in prose that a block reads | Unclosed, an empty segment, `{{ prose }}`, bare `{{ var }}` or `{{ sys }}`, an unknown `sys` field |

`require` loads sections only; Lua files and Markdown includes are planned language work and out of scope.

#### Arguments

| Check | Example | Rule |
|---|---|---|
| Argument count | `log()`, `jump()`, `log('a', 'b')` | Fewer arguments than the function takes, or more where the function raises on extra arguments |
| Literal of the wrong type | `jump(3)`, `log({})`, `log(nil)` | A literal whose type the function refuses |
| Literal value | `models.use('fast', { temperature = 5 })`, `tasks.fanout('Worker', {})`, `store.read(p, 0, 1)`, `json.decode('{')` | A literal outside the range or format the function accepts |
| Option key | `models.use('fast', { temp = 0 })`, `json.encode(v, { pretty = true })` | A key outside the function's fixed set |
| `log` text | `log('line one\nline two')` | Longer than 256 characters, or a newline or control character |
| Call outside its context | `messages:replace(...)` at the top level of a block | A function that works only inside a compactor or outside an adhoc handler, called where it never can. A section that `require` loads is checked from every section that requires it |

Each check reads a function's forms from the language table, so a call such as `tasks.fanout(model, worker, collection)`, whose optional first argument shifts the others, is read correctly.

### Warnings

A warning's message says why it is not an error, such as "unless a Pack prelude defines `jmup`".

#### Errors that may not apply

| Check | Example | Rule |
|---|---|---|
| Error that a Pack prelude could avoid | `string.trim(s)`, `jmup(x)` | An error check on a table or global that a prelude can reach, when the prompt declares a Pack |
| Relative path when a computed `require` exists | `call('Worker')` | A relative path check that a library loaded by a computed path could make valid |

#### Unused names and values

| Check | Example | Rule |
|---|---|---|
| Unused local | `local reply = models.infer(p)` and `reply` is never read | A local, local function, or loop variable that is never read. A name that starts with `_` is skipped |
| Unused argument | `function(a, b) return a end` | A parameter that is never read. A name that starts with `_` is skipped |
| Unused label | `::retry::` with no `goto retry` | A label that no `goto` names |
| Overwritten value | `local x = f()` then `x = 2` before any read | A value that is replaced before it is read |
| Unbalanced assignment | `local a, b = 1`, `a = 1, 2` | The number of names and values differ, and the last value is not a call or `...` |
| Extra arguments | `store.exists(p, true)` | More arguments than a function takes, where it ignores the extra ones |

#### Names

| Check | Example | Rule |
|---|---|---|
| Read of a missing member | `if prompt.sectoin then` | A member that the table lacks, read without a call or index. It is always nil |
| Read of an undefined global | `log(tostring(resutl))` | A global that nothing assigns, read without a call or index. It is always nil |
| Unknown argument field | `args.qurey` | A field outside this prompt's closed `args:` declaration. It is always nil |
| Tool id that `tools.get` never finds | `tools.get('web/')` | A malformed tool id. `tools.get` returns nil |

#### Shadowing and globals

| Check | Example | Rule |
|---|---|---|
| Redefined local | `local x` twice in one scope | A local declared again in the same scope |
| Shadowed name | `local prompt = ...`, an inner `local x` under an outer `x` | A local that hides an outer local or a built-in |
| Unread global | `counter = 1` and nothing reads `counter` | A global the prompt assigns and no block reads |
| Changed built-in table | `string.trim = ...`, `prompt.summary = ...` | A write to a member of a Lua or Engine table |
| Rebound built-in | `prompt = {}`, `jump = nil` | An assignment to an Engine or Lua global |

#### Control flow

| Check | Example | Rule |
|---|---|---|
| Unreachable code | A line after `do return end`, `break`, `goto`, `error(...)`, or `jump(...)` | A statement that can never run |
| Empty block | `if ok then end`, `do end` | A block with no statements inside a Lua block. An empty `lua` fence is valid and not reported |
| Loop that runs once | A loop whose body always ends in `return` or `break` | The loop can never reach a second pass |

#### Runvil

| Check | Example | Rule |
|---|---|---|
| Global across sections | `/A` sets `total = 0`, `/B` reads `total` | A global read in a section that never sets it, set in another section, and not loaded with `require`. Each section runs in a fresh VM, so it reads nil. Reported once, in place of the read of an undefined global |
| Unread placeholder | `{{ var.name }}` in prose that no block reads | The placeholder is never filled. Commentary without placeholders is valid and not reported. A block that calls a function from a required section may read `prose` through it, so such a block counts as reading it |
| Missing `untrusted` | `models.infer(store.read('page.md'))` | Text from `store.read`, `store.read_numbered`, or `json.decode` reaches `models.infer` or a `messages` builder, directly or through a local, without `untrusted(...)` |

Style, such as line length and whitespace, is out of scope.

### Turning a check off

A comment turns off one or more warnings by name:

```lua
local _ = models.infer(p)  -- runvil: allow unused-local
```

- **At the end of a line of Lua:** the checks are off for that line.
- **On a line of its own in a Lua block:** the checks are off for the whole prompt. This is also how a warning about prose, such as `unread-placeholder`, is turned off.
- **Several names** are separated by commas: `-- runvil: allow unused-local, shadowed-name`.
- **Errors cannot be turned off.** A comment that names an error, or a name that is no check, is a warning, `unknown-allow`.

### Prompts that a prompt lists

A prompt names the prompts it may run with `execute` under `prompts:` in its front matter, and `Prompt::parse` already finds and parses each of them, and the prompts those list in turn. Each of these prompts is checked the same way as the one being parsed, once, however many prompts list it. Its problems name its own file. An error in any of them fails the parse, as a parse failure in one does today.

## What parse time cannot prove

- Anything computed: a path built with `..`, a name read from `var` or `args`.
- What a Pack prelude defines, since the parser does not know the Host's Packs.
- Failures that depend on the run: a store file that is absent, a tool that fails, a model reply, `args` that the caller passes.

## Testing

- **Agreement with Lua 5.5.** One test gives the same source to mlua and to our parser and requires the same accept or reject answer. Inputs: the official Lua 5.5 test suite, a hand-written list of invalid code (one case per non-grammar error, plus the 200-local, 255-upvalue, register, and nesting limits), scrambled real code from a fixed seed, and every block of the fixture prompts. `luck_parser` is a second reference, as a dev-dependency only.
- **Mismatch at parse time.** If mlua accepts a block that our parser rejects, mlua's answer stands: the block parses, our checks skip it, and a warning reports the mismatch. A bug in our parser therefore never stops a valid prompt.
- **Checks.** `prompts_runvil/lint-errors.md` in this repository has one section per check, errors and warnings alike, and a section of valid lookalikes that must report nothing.
- **Errors are real.** Each error case also runs through the Engine, and must fail at the line the check names. A check whose case runs without failing is wrong.
- **Stand-down rules hold.** Each stand-down rule has a case that would be an error without the rule, and that case must run clean through the Engine.
- **Turning checks off.** Tests cover a comment at the end of a line, several names in one comment, and a comment that names an error or no check. A comment on its own line turns a check off for the whole prompt, so it is tested in a prompt of its own.

## How this fits into the existing code

Nothing that runs a prompt changes. The work touches:

- **New code:** a Lua parser crate and the checks, in `runvil-harness/crates/runvil-internal/`.
- **Updated parsing code:** `runvil-harness/crates/runvil-internal/prompt/`, which collects problems instead of stopping at the first one. Section path resolution and placeholder parsing move from `runvil-harness/crates/runvil-internal/runtime/` into `runvil-harness/crates/runvil-internal/prompt/`, so the checks and the run share one implementation.
- **The language table**, which replaces `RESERVED_NAMES` and the prelude's `VISIBLE_GLOBALS`: `runvil-harness/crates/runvil-internal/lua/`.
- **Callers of the parse:** `Host::parse` in `runvil-harness/crates/harness-internal/runner/`, the `runvil` facade's exports, and Workshop's prompt routes in `runvil-workshop/crates/workshop/`.
- **Docs:** `runvil-harness/decisions/` and the language guide in `runvil-docs/src/language/`.
