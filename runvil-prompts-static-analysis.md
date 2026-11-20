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
3. **Checks.** `runvil-prompt` walks each block's tree after the sections and front matter are known. It never guesses what a name or an argument is, and skips three cases:

   - **The name is the author's own variable.** A block may declare a local with the name of a built-in, and that local is a different thing.

     ```lua
     local prompt = { sectoin = function() end }
     prompt.sectoin()   -- not checked: this `prompt` is the author's local
     ```

   - **The argument is worked out at run time.** Only a constant written in the source is judged.

     ```lua
     jump('../Nowhere')        -- checked: the string is right there
     jump('../' .. var.next)   -- not checked: depends on what var.next holds
     ```

   - **The prompt defines the member itself.** Engine tables are writable, so an author can add a function to one.

     ```lua
     prompt.summary = function() return "..." end
     prompt.summary()   -- not checked: the prompt defined it
     prompt.sectoin()   -- checked: nothing defines it
     ```
4. **API table.** One table in `runvil-lua` lists each Engine global, its members, and each function's argument count. Tests keep it equal to the code:

   - **Names.** A test builds a set-up section VM, walks every Engine table in it, and compares the names with the table in both directions, as the test of `RESERVED_NAMES` does. A member added to the code and left out of the table fails, and so does the reverse.
   - **Argument counts.** The counts cannot be read from the code, since most built-ins are Rust closures that check their own arguments. A test therefore calls every function in the table with one argument too few and one too many, and requires that the real function raises exactly when the table says the count is wrong.
   - **Coverage.** The count test walks the table, so a function with no count fails the test.
5. **Result.** `Prompt::parse` returns a list of problems in place of one error. Each problem has:

   - **A group:** error, warning, or lint (see Checks).
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

   lint[unreachable-code]: this line never runs
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
| **Error** | Will fail if the line runs | The prompt fails to parse |
| **Warning** | May fail, depending on the Host | Reported; the prompt parses |
| **Lint** | Runs, but is probably a mistake | Reported; the prompt parses |

Every check runs on every parse. A caller can hide the lint group from what it shows: the command-line check of a prompt has a flag for it, `--no-lint`.

### Errors

Each of these already fails today, but only when the run reaches the line. A mistake in a branch that never runs, such as `if false then prompt.sectoin() end`, is an error too, since the code is wrong either way.

#### Syntax

| Check | Rule |
|---|---|
| Syntax error | All errors in all blocks |
| Compile error past the grammar | Assignment to a `<const>` or loop variable, `goto` into a local's scope, a missing or repeated label, `break` outside a loop, an undeclared name under `global` |

#### Names

| Check | Example | Rule |
|---|---|---|
| Misspelled member | `prompt.sectoin`, `store.wirte`, `json.encod`, `string.fromat` | A member that the table lacks. Engine tables are writable, so a member the prompt assigns is skipped |
| Unknown `sys` field | `sys.sectoin_name` | A field outside the fixed set |
| Unknown method of `messages` | `messages:usr(text)` | A method outside the fixed set |

#### String identifiers

| Check | Applies to | Rule |
|---|---|---|
| Section path, relative | `call`, `jump`, `tasks.spawn`, `tasks.fanout` | Form is `name` or `../name`; the target is a sibling or a direct child of the section the code is in |
| Section path, any form | `prompt.section`, `prompt.section_or` | `name`, `../name`, or `/a/b` names an existing section |
| Section path, from the top | `require` | Form is `/a/b` and names an existing section |
| Prompt name | `execute` | The name is listed under this prompt's `prompts:` |
| Model role | `models.use`, `models.get` | One of `default`, `strong`, `small`, `fast`, `creative` |
| Tool id | `tools.call`, `tools.get`, `tools.offer` | The `pack/name` shape only. The parser does not know the Host's Packs or their tools, and Lua may call a tool of a Pack that `uses:` leaves out |
| Store path | `store.*` | The path rules: no leading `/`, backslash, colon, or `.` and `..` segment |
| Placeholder in prose | `{{ ... }}` in prose that a block reads | Unclosed, an empty segment, `{{ prose }}`, bare `{{ var }}` or `{{ sys }}`, an unknown `sys` field |

`require` loads sections only; Lua files and Markdown includes are planned language work and out of scope.

#### Arguments

| Check | Example | Rule |
|---|---|---|
| Argument count | `log()`, `log('a', 'b')`, `jump()` | Fewer or more arguments than the function takes |
| Literal of the wrong type | `jump(3)`, `log({})` | A literal whose type the function refuses |
| Option key | `models.use('fast', { temp = 0 })`, `json.encode(v, { pretty = true })` | A key outside the function's fixed set |
| `log` text | `log('line one\nline two')` | Longer than 256 characters, or a newline or control character |

### Warnings

A Pack prelude can define a global that the parser cannot see, so these may be valid under some Host.

| Check | Example | Rule |
|---|---|---|
| Unknown global | `jmup('../A')`, `resutl` | A name that is no local, no Engine or Lua global, and never assigned in the block or in a section it requires |
| Removed global | `print(x)`, `io.open(p)` | A standard Lua name that the sandbox removes or never loads |

### Lint

#### Unused names and values

| Check | Example | Rule |
|---|---|---|
| Unused local | `local reply = models.infer(p)` and `reply` is never read | A local, local function, or loop variable that is never read. A name that starts with `_` is skipped |
| Unused argument | `function(a, b) return a end` | A parameter that is never read. A name that starts with `_` is skipped |
| Unused label | `::retry::` with no `goto retry` | A label that no `goto` names |
| Overwritten value | `local x = f()` then `x = 2` before any read | A value that is replaced before it is read |
| Unbalanced assignment | `local a, b = 1`, `a = 1, 2` | The number of names and values differ, and the last value is not a call or `...` |

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
| Unreachable code | A line after `return`, `break`, `goto`, `error(...)`, or `jump(...)` | A statement that can never run |
| Empty block | `if ok then end`, `do end` | A block with no statements inside a Lua block. An empty `lua` fence is valid and not reported |
| Loop that runs once | A loop whose body always ends in `return` or `break` | The loop can never reach a second pass |

#### Runvil

| Check | Example | Rule |
|---|---|---|
| Global across sections | `/A` sets `total = 0`, `/B` reads `total` | A global read in a section that never sets it, set in another section, and not loaded with `require`. Each section runs in a fresh VM, so it reads nil |
| Unread placeholder | `{{ var.name }}` in prose that no block reads | The placeholder is never filled. Commentary without placeholders is valid and not reported |
| Missing `untrusted` | `models.infer(store.read('page.md'))` | Text from `store.read`, `store.read_numbered`, or `json.decode` reaches `models.infer` or a `messages` builder, directly or through a local, without `untrusted(...)` |

Style, such as line length and whitespace, is out of scope.

### Turning a check off

A comment turns off one or more warnings or lints by name:

```lua
local _ = models.infer(p)  -- runvil: allow unused-local
```

- **At the end of a line of Lua:** the checks are off for that line.
- **On a line of its own in a Lua block:** the checks are off for the whole prompt. This is also how a lint about prose, such as `unread-placeholder`, is turned off.
- **Several names** are separated by commas: `-- runvil: allow unused-local, shadowed-name`.
- **Errors cannot be turned off.** A comment that names an error, or a name that is no check, is a warning, `unknown-allow`.

## What parse time cannot prove

- Anything computed: a path built with `..`, a name read from `var` or `args`.
- A global that a Pack prelude defines, since the parser does not know the Host's Packs. Unknown-global checks therefore name a problem that may be valid under some Host.
- A section that calls `setmetatable(_G, ...)`, which gives every unknown global a value. Unknown-global checks are off in that section and in the sections that `require` it, since each section runs in its own VM.
- Failures that depend on the run: a store file that is absent, a tool that fails, a model reply, `args` that the caller passes.

## Testing

- **Agreement with Lua 5.5.** One test gives the same source to mlua and to our parser and requires the same accept or reject answer. Inputs: the official Lua 5.5 test suite, a hand-written list of invalid code (one case per non-grammar error, plus the 200-local, 255-upvalue, register, and nesting limits), scrambled real code from a fixed seed, and every block of the fixture prompts. `luck_parser` is a second reference, as a dev-dependency only.
- **Mismatch at parse time.** If mlua and our parser disagree on a block, the parse reports an `Internal` failure naming the block.
- **Checks.** `prompts_runvil/lint-errors.md` in this repository has one section per check, errors, warnings, and lints alike, and a section of valid lookalikes that must report nothing.
- **Turning checks off.** Tests cover a comment at the end of a line, several names in one comment, a comment that names an error or no check, and `--no-lint`. A comment on its own line turns a check off for the whole prompt, so it is tested in a prompt of its own.

## How this fits into the existing code

Nothing that runs a prompt changes. The work touches:

- **New code:** a Lua parser crate and the checks, in `runvil-harness/crates/runvil-internal/`.
- **Updated parsing code:** `runvil-harness/crates/runvil-internal/prompt/`, which collects problems instead of stopping at the first one. Section path resolution and placeholder parsing move from `runvil-harness/crates/runvil-internal/runtime/` into `runvil-harness/crates/runvil-internal/prompt/`, so the checks and the run share one implementation.
- **The API table** of the Engine's built-in globals, their members, and argument counts: `runvil-harness/crates/runvil-internal/lua/`, beside `RESERVED_NAMES`.
- **Callers of the parse:** `Host::parse` in `runvil-harness/crates/harness-internal/runner/`, the `runvil` facade's exports, and Workshop's prompt routes in `runvil-workshop/crates/workshop/`.
- **Docs:** `runvil-harness/decisions/` and the language guide in `runvil-docs/src/language/`.
