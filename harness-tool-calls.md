# Tool Call Results in Popular Coding Agent Harnesses

A survey of what tool call results look like in **pi** (pi.dev), **Claude Code**, and **Cursor**. It covers the in-memory data model, the wire format sent to the LLM, the per-tool text, error handling, truncation, and how the UI view differs from what the model receives.

## Methodology

Each harness was researched by a separate agent working from the installed code rather than the docs.

| Harness | Version | Source of truth | Empirical verification |
|---|---|---|---|
| pi | `@earendil-works/pi-coding-agent` (global npm install) | Shipped JS in `dist/`, plus the bundled `pi-ai` and `pi-agent-core` packages | `pi -p` run with an extension that dumped every provider request body; direct calls to the built-in tools and the argument validator |
| Claude Code | v2.1.285, `bin/claude.exe` (Bun-compiled binary) | ~1,450 `// @bun` source chunks (~39 MB) extracted from the binary and read | `claude -p --model haiku` run through a local logging proxy that captured the exact `/v1/messages` bodies; stream-json output; transcripts |
| Cursor | IDE 3.22.12 + `cursor-agent` CLI 2026.10.18 | Bundled extension JS (`cursor-agent-exec`, `cursor-agent-host`, `cursor-local-agent-runtime`, workbench) and the compact protobuf descriptors embedded in it (no `.proto` files ship) | `~/.cursor/projects/*/agent-transcripts` and `agent-tools/*.txt` spill files |

Each claim carries a confidence tag: **[code]** means read in the code, **[emp]** means observed at runtime, and **[inf]** means inferred.

The main caveat is Cursor. In its default mode the agent loop runs on Cursor's servers: the client executes each tool and sends back a typed protobuf, and the server builds the prompt. The text formats given for Cursor come from the `render()` functions in the client's copy of the `@anysphere/agent` package. That package also renders prompts locally in "Private Inference" mode, so the server almost certainly uses the same code, but this cannot be verified from the client.

---

## 1. Executive Comparison

| Dimension | pi | Claude Code | Cursor |
|---|---|---|---|
| **Internal result type** | `{content: (Text\|Image)[], details, isError?, structuredContent?, terminate?}` | `data` (typed, per tool) plus a `tool_result` block built by `mapToolResultToToolResultBlockParam` | Typed protobuf per tool (`agent.v1.*Result`) with a `oneof` of success, error, rejected, etc.; `render()` turns it into text |
| **Model-facing content** | Text and image blocks only; `details` never reaches the model | A string for most tools, a block array for images, PDFs and notebooks | Text and image parts only, in MCP `CallToolResult` shape `{content:[…], isError}` |
| **Separate UI payload** | Yes, `details` (diffs, truncation info) | Yes, `toolUseResult` / `tool_use_result` (structured patches, raw content) | Yes, the full protobuf (diffs, before/after file contents, raw stdout/stderr) |
| **Multi-provider** | Yes: Anthropic, OpenAI Chat, OpenAI Responses, Gemini, Bedrock, Mistral | Anthropic only | Server-side, model-dependent prompt variants (`gpt5-codex`, `dsv3-1018`, `latest`, …) |
| **Error signal** | `isError` → `is_error` (Anthropic), `{error:…}` (Gemini); dropped for OpenAI | `is_error: true`; validation errors wrapped in `<tool_use_error>…</tool_use_error>` | `isError` on the tool-result part; typed error/rejected cases with separate `modelVisibleErrorMessage` and `clientVisibleErrorMessage` |
| **Read line numbers** | **None**, raw text | `N\tline`, no padding | `     N\|line` (padded to 6) by default; `L12:` or cat -n style for some models |
| **Read default cap** | 2000 lines / 50 KB, head kept, continuation hint | Whole file, 256 KB byte cap and 25k token cap (otherwise an error) | 100k chars (otherwise an error) |
| **Shell exit code** | Omitted on success; `\n\nCommand exited with code N` appended plus `isError` on failure | `Exit code N` **prepended** on failure; nothing on success | `Exit code: N` header **always** present |
| **Shell stdout/stderr** | Interleaved, unlabelled | Interleaved (shared fd), unlabelled | Interleaved, inside a fenced code block |
| **Shell truncation** | Tail kept: last 2000 lines / 50 KB; full log at `$TMPDIR/pi-bash-*.log` | Above 30k chars: spilled to disk, `<persisted-output>` with a 2 KB preview | Head 10k + tail 10k chars; above 40 KB, spilled to `agent-tools/*.txt` |
| **Edit success text** | `Successfully replaced N block(s) in <path>.` | `The file <path> has been updated successfully.` | `The file <path> has been updated.` |
| **Diff shown to model?** | No (it goes to `details`) | No (it goes to `structuredPatch`) | No (it stays in the protobuf) |
| **Lints after edit** | No | No | Not appended; the model is told to call `ReadLints` (the legacy protocol did append them) |
| **Extra injected context** | None | `<system-reminder>` blocks folded **into** the last `tool_result` content | Cursor rules/skills appended to Read results; occasional `<system_reminder>` |
| **Old result pruning** | None; only compaction (summary) | `[Old tool result content cleared]`, client-side or via the API's `clear_tool_uses_20250919` (flag-gated) | Server-side and opaque |

### Recurring patterns

1. **All three keep a UI payload separate from the model payload.** The model gets a terse string while the UI gets structured data. Edits are the clearest case: none of the three harnesses shows the diff to the model, and all reply with a one-line confirmation.
2. **Errors are delivered as tool results.** Unknown tools, schema failures, exceptions, rejections and aborts all come back as an error-flagged result, never as a failed turn.
3. **Large output is spilled to a file plus a pointer** in Claude Code and Cursor. pi truncates and writes the full log to a temp file only for bash.
4. **Truncation messages tell the model how to continue,** for example `Use offset=2001 to continue.` or `Full output saved to: …`.
5. **The size limits cluster around the same numbers:** 2000 lines, 50 KB, about 20–30k chars for shell, and about 100k chars for file reads.

---

## 2. Side-by-Side Wire Examples

### 2.1 Successful Read of a 3-line file

**pi → Anthropic** [emp]
```json
{"role":"user","content":[{"type":"tool_result","tool_use_id":"toolu_…","content":"line one\nline two\nline three\n","is_error":false}]}
```

**Claude Code → Anthropic** [emp]. Note the trailing empty numbered line and the folded system reminder.
```json
{"role":"user","content":[{"tool_use_id":"toolu_01ShTUtAZjS3NqZmU9zt4yF5","type":"tool_result",
  "content":"1\tline one\n2\tline two\n3\tline three\n4\t\n\n<system-reminder>\n<total_tokens>14965508 tokens left</total_tokens>\n</system-reminder>"}]}
```

**Cursor**, rendered tool text [code/inf]
```
     1|line one
     2|line two
     3|line three
```

### 2.2 Failing shell command: `echo out; echo err >&2; exit 3`

| Harness | Model-visible content | Error flag |
|---|---|---|
| pi | `"out\nerr\n\n\nCommand exited with code 3"` [emp] | `is_error: true` |
| Claude Code | `"Exit code 3\nout\nerr"` [emp] | `is_error: true` |
| Cursor | ``"Exit code: 3\n\n```\nout\nerr\n```\n\nCommand completed in N ms.\n\nShell state (cwd, env vars) persists for subsequent calls. Current directory: /path"`` [code] | `isError` per render |

### 2.3 Edit whose `old_string` is not found

| Harness | Model-visible content |
|---|---|
| pi | `Could not find the exact text in <path>. The old text must match exactly including all whitespace and newlines.` (`is_error: true`) [emp] |
| Claude Code | `<tool_use_error>String to replace not found in file.\nString: zzz</tool_use_error>` (`is_error: true`) [emp] |
| Cursor | `Error: The string to replace was not found in the file[ (even after relaxing whitespace)]. Found a possible fuzzy match, did you mean:\n<line-numbered snippet>`. The UI gets a shorter message. [code] |

### 2.4 Schema validation failure

| Harness | Model-visible content |
|---|---|
| pi | `Validation failed for tool "read":\n  - offset: must be number\n\nReceived arguments:\n{…}`, after first attempting type coercion and stripping `null`s [emp] |
| Claude Code | `<tool_use_error>InputValidationError: Read failed due to the following issue:\nThe parameter \`limit\` type is expected as \`number\` but provided as \`string\`</tool_use_error>` [code] |
| Cursor | A typed error with classification `INVALID_ARGS`, rendered as `Error: …` [code] |

---

## 3. pi (pi.dev)

Paths below use `AI` for `node_modules/@earendil-works/pi-ai/dist`, `CORE` for `…/pi-agent-core/dist`, and `CA` for `pi-coding-agent/dist`.

### 3.1 Data model [code]

```ts
// CORE/types.d.ts:370-392
interface AgentToolResult<T> {
  content: (TextContent | ImageContent)[];   // the only part sent to the model
  details: T;                                // UI and logging only
  structuredContent?: JsonValue;             // programmatic callers (codemode); never sent
  usage?: Usage;
  isError?: boolean;                         // report failure without throwing
  terminate?: boolean;                       // stop the loop after this batch
}
```

Tools have the signature `execute(toolCallId, params, signal?, onUpdate?, ctx?)`. A tool reports failure either by throwing or by returning `isError: true`, which bash does for a non-zero exit. The result is stored as a `ToolResultMessage`, `{role:"toolResult", toolCallId, toolName, content, details, isError, timestamp, durationMs}`. Errors generated by the harness itself are always `{content:[{type:"text",text:msg}], details:{}}`.

Results can be rewritten before storage in three places:
- an `afterToolCall` hook;
- extension `tool_result` handlers;
- automatic image resizing (`normalizeToolResultImages`).

In addition, the extension `context` event can rewrite the entire message list before each request.

### 3.2 Wire format per provider [code, Anthropic also emp]

Fields that are never sent to any provider: `details`, `usage`, `nestedCalls`, `structuredContent`.

| API | Shape | Error | Images |
|---|---|---|---|
| Anthropic | All consecutive results are merged into **one** `role:"user"` message of `tool_result` blocks. `content` is a **string** (text blocks joined with `\n`) unless there are images. `cache_control` is set on the last result. | `is_error` | Inline base64 blocks. For error results, images move after all of the turn's results, with a caption. |
| OpenAI Chat | One `{role:"tool", tool_call_id, content:<string>}` per result | **Not sent** | Moved to a following `role:"user"` message, `"Attached image(s) from tool result:"`. Some providers also need a synthetic assistant turn in between. |
| OpenAI Responses | `{type:"function_call_output", call_id, output}` | **Not sent** | Inline `input_image` |
| Gemini | A `functionResponse{name, response}` part in a user turn | `response:{error}` vs `{output}` | Gemini 3 and later: nested `parts`. Older models: a separate user turn. |
| Mistral / Bedrock | — | `[tool error] ` text prefix / `status: ERROR` | — |

The per-request transforms are:
- on non-vision models, images become `(tool image omitted: model does not support images)`;
- orphaned tool calls get a synthetic `No result provided` error result;
- assistant turns that errored or were aborted are dropped.

### 3.3 Built-in tool text [code + emp]

The shared limits are 2000 lines, 50 KB, and 500 chars per grep line.

| Tool | Format |
|---|---|
| **read** | Raw text, **no line numbers**, head-truncated on line boundaries. Footers: `[Showing lines 1-2000 of 2500. Use offset=2001 to continue.]`, `[… (50.0KB limit). Use offset=Z to continue.]`, `[3 more lines in file. Use offset=2 to continue.]`. A single line over 50 KB gets a `sed -n` hint. Images return `Read image file [image/png]` plus an image block. |
| **bash** | stdout and stderr interleaved and unlabelled, **tail**-truncated, with the full log at `$TMPDIR/pi-bash-<hex>.log`. Exit 0 returns the output only; empty output returns `(no output)`. A non-zero exit appends `\n\nCommand exited with code N` and sets `isError`. Footer: `[Showing lines 1001-3000 of 3000. Full output: /tmp/pi-bash-….log]`. Thrown errors: `Command timed out after N seconds`, `Command aborted`. |
| **edit** | `Successfully replaced N block(s) in <path>.` The diff goes to `details` only. Errors: not found, `Found K occurrences … must be unique`, `edits[i] and edits[j] overlap …`, `No changes made …`. Malformed `edits` arguments are auto-repaired. |
| **write** | `Successfully wrote to <path>` |
| **grep** (ripgrep) | `path:LINE: text`, with context lines as `path-LINE- text`. Default 100 matches. Notices go in a single `[...]`, e.g. `[100 matches limit reached. Use limit=200 for more, or refine pattern]`. No hits: `No matches found`. |
| **find** (fd) | Relative paths; default 1000. No hits: `No files found matching pattern`. |
| **ls** | Sorted, `/` suffix on directories, dotfiles included; default 500. Empty: `(empty directory)`. |

### 3.4 Errors [code + emp]

Every case becomes `isError: true` text:

| Case | Text |
|---|---|
| Tool throws | `error.message` |
| Unknown tool | `Tool <name> not found` |
| Bad arguments | `Validation failed for tool "x":\n  - field: msg\n\nReceived arguments:\n<json>` |
| Arguments not valid JSON | `Invalid arguments for tool "x": <parse error>\n\nReceived arguments:\n<raw>` |
| Blocked by a hook | The hook's reason, or `Tool execution was blocked` |
| Aborted | `Operation aborted` |
| Output token limit hit mid-call | `Tool call "x" was not executed: the response hit the output token limit, so its arguments may be truncated. Re-issue the tool call with complete arguments.` |

### 3.5 Pruning and UI [code]

Old results are **never pruned in place**. Compaction replaces older history with a summary, and when that history is sent to the summarizer, tool results are cut to 2000 chars. The TUI renders from `details` (diffs, truncation warnings, a 5-line collapsed bash preview, streamed `onUpdate` output), none of which the model sees.

---

## 4. Claude Code

### 4.1 Data model [code]

Each tool returns structured `data`. This is persisted as `toolUseResult` in the transcript and emitted as `tool_use_result` in stream-json. `mapToolResultToToolResultBlockParam(data, id)` builds the API block, and a post-processor then applies two rules:
- empty content becomes `(<Tool> completed with no output)`;
- content over the size threshold is persisted to disk and replaced by `<persisted-output>`.

`content` is a string for nearly all tools. It is a block array (`text`/`image`/`document`) for image, PDF and notebook reads, for image stdout from Bash, and for Agent results. Results with `is_error` are forced to text only. Bash always sets `is_error` explicitly, including `false`.

### 4.2 Wire format [code + emp]

Each result is a `tool_result` block inside a `role:"user"` message: `{type, tool_use_id, content, is_error?}`.

The notable difference from the other harnesses is that **system reminders are folded into the tool result** (for example `<total_tokens>`, date and task reminders). For string content the reminder is appended after `\n\n`; for array content it becomes an extra text block. This behavior is gated by a flag that was active in testing.

Other details:
- The last `tool_result` gets `cache_control: {type:"ephemeral"}`.
- Requests carried `context_management: {edits:[{type:"clear_thinking_20251015"}]}`.
- When a background task finishes, a **separate user turn** arrives later: `<task-notification><task-id>…</task-id><status>completed</status><summary>Background command "…" completed (exit code 0)</summary></task-notification>`.

### 4.3 Built-in tool text [code + emp]

| Tool | Format |
|---|---|
| **Read** | `N\tline`, unpadded. This build does **not** use the `→` arrow, though the line-number stripper still accepts `→`, `\t` and `:`. A trailing newline produces a final empty numbered line. With no `limit` the whole file is read; the "2000 lines" in the prompt is never enforced. Lines are not truncated. Caps: 256 KB (likely) and 25,000 tokens, configurable via `CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS`. Over the cap: `File content (N tokens) exceeds maximum allowed tokens (25000). Use offset and limit …`, or an automatic partial view with a `[Truncated: PARTIAL view — …]` notice. Empty file: `<system-reminder>Warning: the file exists but the contents are empty.</system-reminder>`. An unchanged re-read returns `Wasted call — file unchanged since your last Read. …`. Images become an image block (max 2000×2000 px, 5 MB). A PDF becomes `PDF file read: …` plus a `document` block. Notebooks become `<cell id>` blocks. |
| **Bash** | Interleaved output. Success: `[stdout, stderr, bgMsg, hints].join("\n")`. Failure: `Exit code N\n<stderr>\n<stdout>`, plus `is_error`. Timeout: `Exit code 143\nCommand timed out after 1s` (default 120 s, max 600 s). Abort: `<error>Command was aborted before completion</error>`. Over 30k chars (configurable up to 150k), the output is persisted: `<persisted-output>\nOutput too large (39.1KB). Full output saved to: ~/.claude/projects/…/tool-results/<id>.txt\n\nPreview (first 2KB):\n…\n</persisted-output>`. Background: `Command running in background with ID: X. Output is being written to: … To check interim output, use Read on that file path.` |
| **Edit / Write** | `The file <path> has been updated successfully.` With replace_all: `… All occurrences were successfully replaced.` A new file: `File created successfully at: <path>`. Optional suffix: ` (file state is current in your context — no need to Read it back)`. If the user modified the edit, a sentence says so. **No `cat -n` snippet** in this version. Validation errors are wrapped in `<tool_use_error>`: not found, `Found N matches … replace_all is false …`, `File has not been read yet. Read it first before writing to it.`, `File has been modified since read …`. |
| **Grep** | Default head_limit 250. Modes: `Found 2 files\n…`, content lines, or counts ending `Found M total occurrences across F files.` Pagination footer. Empty results: `No files found` / `No matches found`. |
| **Glob** | Newline-separated paths, limit 100, with a truncation note. |
| **Others** | WebFetch returns a secondary model's summary of the page. WebSearch ends with `REMINDER: You MUST include the sources …`. Agent returns the subagent's text plus an `agentId: …<usage>…</usage>` trailer. TodoWrite returns a fixed success sentence. |

There is **no MultiEdit or BashOutput tool** in this build, and no malware-warning reminder on reads.

### 4.4 Errors [code + emp]

Every error is `is_error: true`. Whether it is wrapped in `<tool_use_error>` depends on which stage failed:

| Case | Content |
|---|---|
| Unknown tool | `<tool_use_error>Error: No such tool available: X</tool_use_error>` |
| Bad JSON | `<tool_use_error>InputValidationError: Read was called with input that could not be parsed as JSON.\nYou sent (first N bytes): … Retry with valid JSON.</tool_use_error>` |
| Zod failure | `<tool_use_error>InputValidationError: X failed due to the following issue:\nThe parameter \`p\` type is expected as …</tool_use_error>` |
| `validateInput` rejects | `<tool_use_error>{message}</tool_use_error>` |
| `call()` throws | **Unwrapped** message, e.g. `File does not exist. Note: your current working directory is …` |
| Permission denied (rule or headless) | Unwrapped, e.g. `Claude requested permissions to use X, but you haven't granted it yet.` |
| User rejects | `The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). STOP what you are doing and wait for the user to tell you how to proceed.` With feedback: `…the user said:\n<feedback>` |
| Interrupt | `The user doesn't want to take this action right now. STOP …`, plus `[Request interrupted by user for tool use]` in the conversation |
| Missing result | `[Tool result missing due to internal error]` |

### 4.5 Limits and pruning [code]

- **Persistence threshold:** `min(tool.maxResultSizeChars, 50000)`. The per-tool values are 30k for Bash, 20k for Grep, 100k for most tools, and ∞ for Read.
- **MCP output:** capped at 25k tokens, with `[OUTPUT TRUNCATED - exceeded 25000 token limit]`.
- **Clearing old results** applies to Read, Bash, Grep, Glob, Web* and Edit/Write, and keeps the last 5. Cleared results become `[Old tool result content cleared]` or a `<persisted-output>` pointer. This happens either client-side (flag `tengu_hazel_osprey`) or via the API's `clear_tool_uses_20250919` after 65 minutes idle (flag `tengu_zany_pike`).

### 4.6 UI vs model [code + emp]

The TUI renders from `data`, so Bash shows `(No output)` while the model sees `(Bash completed with no output)`, and Edit draws its diff from `structuredPatch`. Errors in `toolUseResult` are stored as `Error: <msg>` without the XML tags. Denials are tagged in the transcript with a `toolDenialKind` that the model never sees.

---

## 5. Cursor

### 5.1 Data model [code]

Every tool has a typed `agent.v1` protobuf result shaped as `XxxToolCall{args, result}`, wrapped in a `ToolCall` oneof with about 70 variants. That list includes a set of `pi_read/pi_bash/pi_edit/pi_write/pi_grep/pi_find/pi_ls` tools, which suggests Cursor ships a pi-compatible harness mode with pi's 2000-line / 50 KB limits.

| Tool | Result oneof → key fields |
|---|---|
| Read | success / error / rejected / file_not_found / permission_denied / invalid_file. Success fields: `content\|data, total_lines, file_size, truncated, exceeded_limit, read_range, include_line_numbers, related_cursor_rules` |
| Shell | success / failure / timeout / rejected / spawn_error / permission_denied. Fields: `exit_code, signal, stdout, stderr, interleaved_output, execution_time, output_location, output_head/tail, elided_chars, aborted, abort_reason, is_background` |
| Edit / Write | success / file_not_found / read/write_permission_denied / rejected / error. Success fields: `diff_string, before/after_full_file_content, lines_added/removed, message`. `EditError{error, model_visible_error}` |
| Grep / Glob / Ls | Structured matches per workspace, truncation flags, directory tree |
| MCP | success / error / rejected / permission_denied / tool_not_found / server_not_found. `McpSuccess{content[text\|image], is_error, structured_content}` |

The legacy `aiserver.v1.ClientSideToolV2Result` is still referenced in the workbench. It has a `ToolResultError` with three fields: `client_visible_error_message`, `model_visible_error_message`, and `actual_error_message_only_send_from_client_to_server_never_the_other_way_around_because_that_may_be_a_security_risk`. In the legacy model, edit results carried `linter_errors`.

### 5.2 Execution and transport [code]

- **Default mode (server-driven loop).** The client opens a bidirectional `agent.v1.AgentService/Run` stream over Connect, with SSE and poll fallbacks. The server sends `ExecServerMessage{<tool>_args}`, the client executes locally, and it replies with `ExecClientMessage{<tool>_result}`. The reply is the **structured protobuf, not text**. Shell output streams back as `shell_stream` events. Conversation state is stored as content-addressed blobs. [inf] The server renders the protobuf into prompt text using the same `render()` code that ships in the client.
- **Private Inference mode (client-driven loop).** The client calls `render()` itself, which produces `{role:"tool", content:[{type:"tool-result", toolCallId, toolName, result:<text>, experimental_content:[text|image], isError}]}` (Vercel AI SDK shape). This is mapped to `InferenceToolResultPart{tool_call_id, tool_name, result: google.protobuf.Value, is_error, experimental_content}` and sent to `aiserver.v1.InferenceService/RunInference`.

### 5.3 Rendered tool text [code]

| Tool | Format |
|---|---|
| **Read** | `${n.padStart(6)}\|${line}`. Some models get other formats: `gpt5CodexCatN` uses cat -n style, `gpt5StyleLineNumbers` uses `L12:code`, and there is also a sparse numbering mode. Omitted parts of a range are marked `... 40 lines not shown ...`. Empty file: `File is empty.` Over 100k chars: `File content (N characters) exceeds maximum allowed characters (100000 characters).\nPlease use offset and limit … or use the 'grep' tool …`. Images: `Read image file: <path>` plus an image. **Matching Cursor rules and skills are appended** on the first read of a path. |
| **Shell** | ``Exit code: N\n\nCommand output[ (truncated to 20000 characters)]:\n\n```\n<interleaved>\n```\n\nCommand completed in N ms.\n\nShell state (cwd, env vars) persists for subsequent calls. Current directory: /path``, plus an optional `[SANDBOXING: …]` note. Truncation keeps the head 10k and tail 10k, joined by `... (output truncated) ...`. Spilled output: `Command output has been written to: <file> (12.3 KB, 456 lines)`. Background commands return a fixed block with the shell ID, PID and output file ("Don't mention Shell ID to the user."). Timeout: `Command timed out. … The shell has been terminated. On the next invocation of this tool, a new shell will be started at the project root.` |
| **Edit / StrReplace / Write / ApplyPatch** | The message only: `The file <path> has been updated.`, `N occurrences in file <path> have been updated.`, `Wrote contents to <path>`, or `Success. Updated the following files:\nA <path>`. **No diff and no lints.** Errors use `model_visible_error`, which includes a fuzzy-match suggestion with a line-numbered snippet. |
| **Grep** | Wrapped in `<workspace_result workspace_path="…">…</workspace_result>`, with a 15k-char budget split across workspaces. Lines are `  12:match` and `  13-context`. A `<system_reminder>` suggests SemanticSearch when the pattern has many `\|` alternatives. |
| **Glob** | `Result of search in '<dir>' (total N files):\n- a\n- b`, capped at 5k chars. |
| **Ls** | An indented tree capped at 10k chars. Unexpanded directories show `[N files in subtree: 12 *.ts, …]`. Timeout after 5 s. |
| **Todos** | `Successfully updated TODOs. …` followed by a markdown list of the todos and their statuses. |
| **ReadLints** | `Found N linter errors in M files:\n\n<path> (k errors):\n  [ERROR] L12:4 - msg (source)` |
| **Web search / fetch** | `Title/URL/Content` blocks separated by `---`. Fetch returns `# Content from <url>\n\n<markdown>`, capped at 100k or spilled to a file. |
| **MCP** | Content items passed through almost unchanged, with images as images and `isError = is_error`. Large text is spilled to a file. |

### 5.4 Errors [code]

Typed errors carry `{clientVisibleErrorMessage, modelVisibleErrorMessage, classification}`. The classifications include INVALID_ARGS, TIMEOUT, USER_REJECTED, ABORTED, HOOK_DENIED and MCP_AUTH_ERROR. Only the model-visible string reaches the model.

| Case | Model-visible text |
|---|---|
| Rejection | `Rejected: <reason>`, `The web search was rejected by the user.` |
| Write tool in ask mode | `You are in ask mode and cannot run non read-only tools. Ask the user to switch to agent mode if edits are required.` |
| Interrupt | `Error: Shell command was interrupted by the user after Nms before it completed.\n\nOutput collected before interruption: …` |
| No exit status | `The shell command returned no exit status, so its result is unknown — do not assume it ran or succeeded…` |

At the protocol level, the server sends `ExecServerAbort` and the client reports failures with `ExecClientThrow{error, stack_trace}`.

### 5.5 Limits [code]

| Limit | Value |
|---|---|
| Read | 100k chars |
| Shell render | 20k chars (head 10k + tail 10k) |
| Shell / MCP / web spill threshold | 40 KB, written to `<project>/agent-tools/<uuid>.txt` |
| Grep | 15k chars |
| Glob | 5k chars |
| Ls | 10k chars |
| Web fetch | 100k chars |
| Notebook cell output | 2k chars |
| Spill-file retention | 30 days |

### 5.6 UI vs model [code + transcript]

The UI and the `stream-json` output carry the full `ToolCall` protobuf as JSON: `{type:"tool_call", subtype:"completed", call_id, tool_call}`. The model gets only the `render()` text. Local transcripts record only `tool_use` blocks and `turn_ended` markers, never tool results. Dynamic, web and MCP tools are invoked through `CallDynamicTool{namespace, toolName, arguments}`.

---

## 6. Takeaways

- **Line numbers differ in all three:** pi uses none, Claude Code uses `N\t`, and Cursor uses `     N|`. Claude Code's edit errors and the line-number stripper suggest the numbering exists mainly to help the model build exact `old_string` values.
- **Exit codes are placed differently.** Claude Code prepends `Exit code N` only on failure. pi appends `Command exited with code N` only on failure. Cursor always prints an `Exit code: N` header and adds timing and cwd notes.
- **Edits return only a short confirmation everywhere.** The diff is shown to the user but never to the model.
- **Large outputs are handled three ways.** pi truncates with a continuation hint, and for bash also keeps a full log file. Claude Code persists the output and returns a 2 KB preview inside `<persisted-output>`. Cursor keeps the head and tail, or spills to a file and returns a pointer.
- **Error presentation:** Claude Code uses an XML-like envelope (`<tool_use_error>`) for validation errors. pi uses plain text plus the provider's error flag. Cursor keeps separate model-facing and user-facing error strings.
- **The harnesses differ in how much they inject into results.** pi injects nothing. Claude Code folds `<system-reminder>` blocks into the tool result. Cursor appends rules and skills to reads and occasional `<system_reminder>` blocks to other results.
- **The error flag is lost on some providers.** pi drops `isError` for both OpenAI APIs, so on those providers errors can only be recognized from the text.
