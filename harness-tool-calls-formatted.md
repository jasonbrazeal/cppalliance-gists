# Tool Call Results in pi, Claude Code, and Cursor: A Code-Level Survey

**Report type:** Informational. This report records how each harness forms tool results and does not recommend a design.

## Executive Summary

All three harnesses send the model a short text result and keep a richer structured record for their UI. They differ in line numbering, exit-code placement, error envelopes, and how they handle large output.

**The model payload is terse.** pi, Claude Code, and Cursor each turn a tool's output into a few text (and image) blocks for the model. Diffs, raw stdout, and truncation metadata stay in a separate UI payload. For example, every harness answers a successful edit with one sentence, such as Claude Code's `The file <path> has been updated successfully.`, and never shows the model the diff.

**Errors come back as tool results.** Unknown tools, schema failures, exceptions, user rejections, and aborts all return as error-flagged tool results, never as a failed turn.

**Conventions diverge in the details.**
- *Line numbers:* pi returns file text with no line numbers, Claude Code prefixes `N<tab>`, and Cursor prefixes a six-wide padded number and a pipe (`     N|`).
- *Exit codes:* pi appends `Command exited with code N` only on failure, Claude Code prepends `Exit code N` only on failure, and Cursor always opens with `Exit code: N`.
- *Large output:* pi keeps the first 2,000 lines or 50 KB of a file and the last 2,000 lines or 50 KB of shell output. Claude Code saves shell output over 30,000 characters to disk and sends a 2 KB preview. Cursor keeps the first and last 10,000 characters, or saves output over 40 KB to a file and sends the path.
- *Injected context:* Claude Code folds `<system-reminder>` blocks into the tool result. Cursor appends project rules to file reads. pi injects nothing.

**Confidence differs by harness.** Results for pi and Claude Code come from their code and were confirmed by capturing the requests actually sent to the API. Cursor's format comes from its client code alone, because its server builds the prompt in the default mode. The server likely uses the same rendering code that ships in the client, and we hold that judgment with moderate confidence.

## Contents

1. Scope
2. Method and Evidence Quality
3. Cross-Harness Findings
4. pi: Plain Text, Provider-Neutral Results
5. Claude Code: Anthropic-Native Results with Folded Reminders
6. Cursor: Typed Protobuf Results Rendered to Text
7. Limitations and Open Items
- Appendix A. pi Literal Strings
- Appendix B. Claude Code Literal Strings
- Appendix C. Cursor Literal Strings

## 1. Scope

This report answers one question: what does a tool call result look like in pi (pi.dev), Claude Code, and Cursor? It covers six aspects:
- the internal data structure;
- the wire format sent to the LLM (large language model) provider;
- the text each built-in tool returns;
- error handling;
- size limits and later pruning;
- the gap between what the user sees and what the model sees.

Two things are out of scope: the tool definitions the model receives and the harnesses' system prompts.

## 2. Method and Evidence Quality

**Each harness was traced from installed code.** A separate research agent studied each harness and was told to read code rather than documentation, then verify behavior at runtime where possible. Table 1 lists the sources. A second pass re-checked about 30 of the key literal strings and constants against the installed files.

*Table 1. Sources and verification method for each harness.*

| Harness | Version | Code examined | Runtime verification |
|---|---|---|---|
| pi | `@earendil-works/pi-coding-agent`, global npm install | Shipped JS in `dist/`, plus the bundled `pi-ai` and `pi-agent-core` packages | `pi -p` run with an extension that saved every provider request body |
| Claude Code | v2.1.285 | About 1,450 `// @bun` source chunks (39 MB) extracted from the compiled `bin/claude.exe` | `claude -p --model haiku` run through a local proxy that captured each `/v1/messages` body |
| Cursor | IDE 3.22.12; `cursor-agent` CLI 2026.10.18 | Bundled extension JS (`cursor-agent-exec`, `cursor-agent-host`, `cursor-local-agent-runtime`, workbench) and the protobuf descriptors embedded in it | Local transcripts and spill files under `~/.cursor/projects/` |

**Every claim carries an evidence tag.** **[code]** means the claim was read in source. **[emp]** means it was observed at runtime. **[inf]** means it was inferred.

**Likelihood and confidence are stated separately.** Likelihood uses the scale *roughly even chance*, *likely*, *almost certain*. Confidence (high, moderate, or low) describes the strength of the evidence behind the judgment.

## 3. Cross-Harness Findings

Table 2 summarizes the comparison. Sections 3.1 to 3.6 explain each row, and Sections 4 to 6 give the per-harness detail.

*Table 2. Tool result conventions in pi, Claude Code, and Cursor.*

| Dimension | pi | Claude Code | Cursor |
|---|---|---|---|
| Internal result | `{content, details, isError?, structuredContent?, terminate?}` | Per-tool `data` plus an API `tool_result` block | Typed `agent.v1` protobuf per tool, rendered to text |
| Model payload | Text and image blocks | String for most tools; block array for images, PDFs, notebooks | Text and image parts, `{content:[…], isError}` |
| UI payload | `details` | `toolUseResult` (transcript), `tool_use_result` (stream-json) | Full `ToolCall` protobuf |
| Providers | Anthropic, OpenAI Chat, OpenAI Responses, Gemini, Bedrock, Mistral | Anthropic only | Server-side, with per-model prompt variants |
| Error signal | `is_error` (Anthropic), `{error}` (Gemini); none for OpenAI | `is_error`; validation errors wrapped in `<tool_use_error>` | `isError`; separate model-visible and user-visible error strings |
| Read line numbers | None | `N\tline` | `     N\|line` |
| Read cap | 2,000 lines / 50 KB, first lines kept, continuation hint | 256 KB and 25,000 tokens; error when exceeded | 100,000 characters; error when exceeded |
| Shell exit code | Appended on failure only | Prepended on failure only | Header on every result |
| Shell truncation | Last 2,000 lines / 50 KB kept; full log saved | Over 30,000 characters spilled; 2 KB preview | First and last 10,000 characters kept; over 40 KB spilled |
| Edit success | `Successfully replaced N block(s) in <path>.` | `The file <path> has been updated successfully.` | `The file <path> has been updated.` |
| Injected context | None | `<system-reminder>` folded into the result | Project rules on reads; occasional `<system_reminder>` |
| Old-result pruning | None (compaction summarizes instead) | `[Old tool result content cleared]`, flag-gated | Not observable from the client |

### 3.1 All Three Keep the Model Payload Separate from the UI Payload

**The model receives only rendered text.** In pi, the `details` field carries diffs and truncation metadata for the terminal UI, and the provider converters never send it. Claude Code stores each tool's structured `data` as `toolUseResult`; the model sees only the `tool_result` block built from it. Cursor sends the client the full protobuf, including `diff_string`, `before_full_file_content`, and `after_full_file_content`, but its `render()` functions emit only the edit message for the model [code, all three].

**No harness shows the model its own edit diff.** All three reply with a one-sentence confirmation. The diff stays in the UI payload.

### 3.2 Wire Formats Differ in Error Signaling and Image Handling

**Claude Code speaks only Anthropic's format.** It sends a `tool_result` block inside a `role:"user"` message with `tool_use_id`, `content`, and an optional `is_error` [code, emp].

**pi converts one result type for six provider APIs.** Its Anthropic converter matches Claude Code's shape, except that it merges consecutive results into one user message. Its Gemini converter signals failure with `response:{error}`.

**pi loses the error flag on OpenAI.** Neither OpenAI converter sends `isError`, so on those APIs the model can recognize a failure only from the text [code].

**Cursor's wire format to the model is not directly observable.** In its client-driven "Private Inference" mode, the client builds a Vercel AI SDK `tool-result` part with `isError` and image parts [code].

### 3.3 Per-Tool Text Conventions Diverge

**Line numbering differs across all three.** pi returns raw file text. Claude Code writes `N<tab>line` with no padding; this build does not use the `→` arrow, though its line-number parser still accepts it. Cursor pads to six columns before a pipe, and its GPT-5 variants switch to `L12:` or cat -n style [code, emp].

**Exit-code placement also differs.** Section 3.7 shows the same failing command in each harness.

### 3.4 Every Failure Returns as a Tool Result

**Every failure becomes an error-flagged result.** In pi, an exception, unknown tool, schema failure, hook block, or abort becomes `isError: true` text. Claude Code returns all errors with `is_error: true`. It wraps the validation-stage errors in `<tool_use_error>`, while errors thrown during execution and permission denials arrive unwrapped. Cursor's typed errors carry both a `modelVisibleErrorMessage` and a `clientVisibleErrorMessage`, so the model and the user can receive different wording for the same failure [code].

**User rejections carry the strongest instructions.** Claude Code tells the model to `STOP what you are doing and wait for the user to tell you how to proceed.` Cursor's rejected mode switch says `Do not attempt to switch modes again.` [code].

### 3.5 Large Outputs Are Truncated or Spilled with a Continuation Hint

**Each harness tells the model how to recover the missing output.** Each one either truncates in place or "spills" the full output to a file and sends a pointer to it.
- *pi:* truncates in place and gives a continuation hint, such as `Use offset=2001 to continue.`. For bash it also saves the full log to `$TMPDIR/pi-bash-<hex>.log`.
- *Claude Code:* spills output above a per-tool threshold, for example 30,000 characters for Bash. The model receives `<persisted-output>` with a 2 KB preview.
- *Cursor:* keeps the first and last 10,000 characters of shell output. It spills shell, MCP (Model Context Protocol), and web output above 40 KB to `agent-tools/<uuid>.txt` [code].

**The limits cluster around the same numbers.** They fall near 2,000 lines, 50 KB, 20,000 to 30,000 characters of shell output, and 100,000 characters for file reads. Cursor even ships a set of pi-named tools (`pi_read`, `pi_bash`, and others) that use pi's 2,000-line and 50 KB limits [code].

### 3.6 Injected Context and Pruning Differ

**Claude Code puts the most extra text into results.** It folds `<system-reminder>` blocks, such as the remaining-token count, into the content of the last tool result rather than sending them as separate blocks [code, emp].

**The other two inject less.** Cursor appends matching project rules and skills to the first read of a path. pi injects nothing [code].

**Only Claude Code clears old results in place.** It replaces older Read, Bash, Grep, Glob, Web, and Edit results with `[Old tool result content cleared]`, keeping the last five. This runs either client-side or through the API's `clear_tool_uses_20250919`, behind feature flags that were off in testing. pi never edits old results; its compaction replaces older history with a summary instead [code].

### 3.7 The Same Failing Command Produces Three Different Results

Table 3 shows the content each harness sends for `echo out; echo err >&2; exit 3`. pi and Claude Code were captured at runtime. Cursor's text comes from its renderer.

*Table 3. Model-visible result of a shell command that exits with code 3.*

| Harness | Content | Error flag |
|---|---|---|
| pi | `"out\nerr\n\n\nCommand exited with code 3"` [emp] | `is_error: true` |
| Claude Code | `"Exit code 3\nout\nerr"` [emp] | `is_error: true` |
| Cursor | ``"Exit code: 3\n\nCommand output:\n\n```\nout\nerr\n```\n\nCommand completed in N ms.\n\nShell state (cwd, env vars) persists for subsequent calls. Current directory: /path"`` [code] | `isError` |

Table 4 shows how an edit whose search text is missing fails in each harness.

*Table 4. Model-visible result of an edit whose target text is absent.*

| Harness | Content |
|---|---|
| pi | `Could not find the exact text in <path>. The old text must match exactly including all whitespace and newlines.` [emp] |
| Claude Code | `<tool_use_error>String to replace not found in file.\nString: zzz</tool_use_error>` [emp] |
| Cursor | `Error: The string to replace was not found in the file. Found a possible fuzzy match, did you mean:` followed by a line-numbered snippet [code] |

The successful three-line Read below shows each harness's line format. pi sends the raw text `"line one\nline two\nline three\n"` [emp]. Claude Code sends the following [emp]:

```json
{"role":"user","content":[{"tool_use_id":"toolu_01ShTUtAZjS3NqZmU9zt4yF5","type":"tool_result",
  "content":"1\tline one\n2\tline two\n3\tline three\n4\t\n\n<system-reminder>\n<total_tokens>14965508 tokens left</total_tokens>\n</system-reminder>"}]}
```

## 4. pi: Plain Text, Provider-Neutral Results

### 4.1 Tools Return Content Blocks plus UI-Only Details

**A pi tool returns an `AgentToolResult`** (defined in `pi-agent-core/dist/types.d.ts:370-392`) [code]:

```ts
interface AgentToolResult<T> {
  content: (TextContent | ImageContent)[];   // the only part sent to the model
  details: T;                                // UI and logging only
  structuredContent?: JsonValue;             // programmatic callers; never sent
  usage?: Usage;
  isError?: boolean;
  terminate?: boolean;
}
```

**A tool can fail in two ways.** It can throw, or it can return `isError: true`; bash does the latter for a non-zero exit. The harness stores each result as a `ToolResultMessage` with `role:"toolResult"`, `toolCallId`, `toolName`, `content`, `details`, `isError`, and timing fields.

**Several hooks can rewrite a result before storage.** These are an `afterToolCall` hook, extension `tool_result` handlers, and automatic image resizing. Separately, an extension `context` event can rewrite the whole message list before each request [code].

### 4.2 Converters Reshape Results for Each Provider

Table 5 lists the per-provider shapes [code; Anthropic also emp]. No converter sends `details`, `usage`, or `structuredContent` to the model.

*Table 5. How pi serializes a tool result for each provider API.*

| API | Shape | Error signal | Images |
|---|---|---|---|
| Anthropic | Consecutive results merged into one `role:"user"` message of `tool_result` blocks; `content` is a string unless images are present; `cache_control` set on the last result | `is_error` | Inline base64; in error results, images move after the turn's results with a caption |
| OpenAI Chat | One `{role:"tool", tool_call_id, content}` message per result | None | Sent in a following user message |
| OpenAI Responses | `{type:"function_call_output", call_id, output}` | None | Inline `input_image` |
| Gemini | `functionResponse{name, response}` part in a user turn | `response:{error}` vs `{output}` | Nested parts on Gemini 3 and later; a separate turn on older models |
| Mistral / Bedrock | Native shapes | `[tool error] ` prefix / `status: ERROR` | Native |

**Every request is also adjusted on the way out.** pi makes three changes:
- On models without vision, images become `(tool image omitted: model does not support images)`.
- A tool call left without a result gets a synthetic `No result provided` error.
- Assistant turns that errored or were aborted are dropped [code].

### 4.3 Built-In Tools Return Raw Text with Bracketed Footers

**pi's built-in tools share one set of limits.** These are 2,000 lines, 50 KB (`truncate.js:10-11`), and 500 characters per grep line.

**read and bash truncate from opposite ends.**
- *read:* returns raw file text without line numbers, cuts from the end on line boundaries, and adds a footer such as `[Showing lines 1-2000 of 2500. Use offset=2001 to continue.]`.
- *bash:* interleaves stdout and stderr without labels and keeps the last lines rather than the first. On a non-zero exit it appends `Command exited with code N` (`bash.js:297`) [code, emp].

Appendix A gives the full set of literal strings.

### 4.4 Old Results Stay Unchanged Until Compaction

**pi never prunes old tool results in place.** Compaction replaces older history with a summary. When that history goes to the summarization model, each tool result is cut to 2,000 characters. The terminal UI renders from `details`, for example as diffs, truncation warnings, and a five-line collapsed bash preview. The model sees none of it [code].

## 5. Claude Code: Anthropic-Native Results with Folded Reminders

### 5.1 Each Tool Maps Structured Data to a `tool_result` Block

**Each Claude Code tool returns structured `data`.** The transcript stores it as `toolUseResult`, and stream-json emits it as `tool_use_result`. `mapToolResultToToolResultBlockParam` builds the API block from it. A post-processor then replaces empty content with `(<Tool> completed with no output)` and swaps output over the size threshold for a `<persisted-output>` pointer [code, emp].

**Content type depends on the tool.** It is a string for nearly all tools. It is a block array for image, PDF, and notebook reads and for Agent results. Results with `is_error` are forced to text only. Bash always sets `is_error`, including `false` on success [code, emp].

### 5.2 System Reminders Ride Inside the Last Result

**Reminders are folded into the last tool result.** Claude Code appends `<system-reminder>` attachments, such as the remaining-token count, to the content of the final `tool_result` rather than sending them as separate blocks. For string content it appends the reminder after a blank line. For array content it adds an extra text block [code, emp].

**The captured requests showed three more features.** They marked the last result with `cache_control: {type:"ephemeral"}`. They carried `context_management` with `clear_thinking_20251015`. A finished background task arrived later as its own user turn wrapped in `<task-notification>` [emp].

### 5.3 Read and Bash Encode Status in Prefixes and Envelopes

**Read numbers lines as `N<tab>line`.** Without a `limit`, it reads the whole file; the 2,000-line figure in its prompt is never enforced. The caps are 25,000 tokens and probably a 256 KB byte cap. A read over the cap returns an error unless Claude Code automatically trims it to a partial view. Re-reading an unchanged file returns `Wasted call — file unchanged since your last Read.` [code, emp].

**Bash puts the exit code first on failure.** It returns `Exit code N`, then stderr, then stdout (function `Pwr`). Output over 30,000 characters is spilled to `~/.claude/projects/…/tool-results/<id>.txt`, and the model receives a 2 KB preview inside `<persisted-output>` [code, emp].

This build has no MultiEdit or BashOutput tool and no warning text attached to file reads. Appendix B gives the full set of literal strings.

### 5.4 Old Results Can Be Cleared Behind Feature Flags

**Claude Code can clear old results in place.** It caps MCP output at 25,000 tokens. It can replace old results with `[Old tool result content cleared]`, either client-side (flag `tengu_hazel_osprey`) or through the API's `clear_tool_uses_20250919` after 65 idle minutes [code]. Both flags were off during testing, so this behavior was not observed.

## 6. Cursor: Typed Protobuf Results Rendered to Text

### 6.1 Each Tool Returns a Typed Protobuf

**Every Cursor tool has its own result message.** Each `agent.v1` result has a `oneof` covering success, error, rejected, and tool-specific cases. Table 6 lists the main ones; their field names come from the compact protobuf descriptors embedded in the client [code].

*Table 6. Cursor result messages for the main tools.*

| Tool | Result cases | Key success fields |
|---|---|---|
| Read | success, error, rejected, file_not_found, permission_denied, invalid_file | `content`, `total_lines`, `truncated`, `exceeded_limit`, `read_range`, `related_cursor_rules` |
| Shell | success, failure, timeout, rejected, spawn_error, permission_denied | `exit_code`, `signal`, `stdout`, `stderr`, `interleaved_output`, `output_location`, `output_head/tail`, `elided_chars` |
| Edit / Write | success, file_not_found, permission errors, rejected, error | `diff_string`, `before/after_full_file_content`, `lines_added/removed`, `message`; errors carry `model_visible_error` |
| MCP | success, error, rejected, permission_denied, tool_not_found, server_not_found | `content` (text or image), `is_error`, `structured_content` |

**The older protocol is still referenced.** Its `aiserver.v1.ClientSideToolV2Result` has a three-part `ToolResultError` and edit results that carried linter errors.

### 6.2 The Client Executes Tools and the Server Likely Renders Them

**In the default mode, Cursor's server runs the agent loop.** The client executes each tool locally and returns the typed result to the server over a bidirectional `agent.v1.AgentService/Run` stream; the result goes back as protobuf, not text [code].

**In Private Inference mode, the client renders the prompt itself.** It calls `render()` and sends `InferenceToolResultPart{tool_call_id, tool_name, result, is_error, experimental_content}` to `aiserver.v1.InferenceService/RunInference` [code].

**The server likely uses the same renderers.** The client ships every `render()` function with per-model variants, so the server probably runs this same `@anysphere/agent` code. Likelihood: likely. Confidence: moderate, because server code is unavailable [inf].

### 6.3 Rendered Text Adds Headers, Fences, and Workspace Tags

**Read uses six-wide padded line numbers.** It numbers lines with `padStart(6," ")` and a pipe and returns `File is empty.` for empty files. Above 100,000 characters (`TL=1e5`) it returns an error telling the model to use offset and limit [code].

**Shell always leads with the exit code.** It opens with `Exit code: N`, puts the interleaved output in a code fence, and keeps 20,000 characters (`iz=2e4`) split between head and tail. It closes with the run time and the current directory [code].

**Grep and Glob return tagged or prefixed lists.** Grep wraps results in `<workspace_result workspace_path="…">` within a 15,000-character budget. Glob caps results at 5,000 characters [code].

Appendix C gives the full set of literal strings.

### 6.4 The UI Receives the Full Protobuf

**The UI and `stream-json` receive the full `ToolCall` record.** The model receives only `render()` text. Local transcripts record `tool_use` blocks and `turn_ended` markers but no tool results, so they cannot confirm the server-side prompt text [code, transcript].

## 7. Limitations and Open Items

**Four questions remain unverified; none affects the main findings.**
1. *Cursor's server-side prompt text* is inferred from client renderers (likely, moderate confidence).
2. *Claude Code's 256 KB Read cap* (`LHe=262144`) is probably the byte cap; this was not confirmed at runtime.
3. *Claude Code's Zod validation wording* was read in function `qW`, but the runtime test hit the JSON-parse error path instead.
4. *Flag-gated behaviors* in Claude Code, including in-place result clearing, were inactive during testing.

**The findings are version-specific.** They describe Claude Code v2.1.285, Cursor 3.22.12, and the pi build installed at survey time. All three harnesses change their formats between releases.

---

## Appendix A. pi Literal Strings

*Table A1. pi built-in tool output formats [code, emp].*

| Tool | Format and strings |
|---|---|
| read | Raw text. Footers: `[Showing lines X-Y of N. Use offset=Z to continue.]`, `[Showing lines X-Y of N (50.0KB limit). Use offset=Z to continue.]`, `[K more lines in file. Use offset=Z to continue.]`. A single line over 50 KB gets a `sed -n` hint. Images return `Read image file [image/png]` plus an image block. Error: `Offset N is beyond end of file (M lines total)`. |
| bash | Interleaved output. Empty output: `(no output)`. Failure: `\n\nCommand exited with code N`. Footer: `[Showing lines X-Y of N. Full output: /tmp/pi-bash-….log]`. Thrown errors: `Command timed out after N seconds`, `Command aborted`. |
| edit | `Successfully replaced N block(s) in <path>.` Errors: `Could not find the exact text in <path>. …`, `Found K occurrences of the text in <path>. The text must be unique. …`, `edits[i] and edits[j] overlap in <path>. …`, `No changes made to <path>. …` |
| write | `Successfully wrote to <path>` |
| grep | `path:LINE: text`, context lines `path-LINE- text`. Default limit 100. Notice: `[100 matches limit reached. Use limit=200 for more, or refine pattern]`. No matches: `No matches found`. |
| find | Relative paths. Default limit 1,000. No matches: `No files found matching pattern`. |
| ls | Sorted, `/` suffix on directories. Default limit 500. Empty: `(empty directory)`. |

*Table A2. pi harness-level error strings [code, emp].*

| Case | Text |
|---|---|
| Unknown tool | `Tool <name> not found` |
| Schema failure | `Validation failed for tool "x":\n  - field: msg\n\nReceived arguments:\n<json>` (after type coercion and stripping `null`s) |
| Invalid JSON | `Invalid arguments for tool "x": <parse error>\n\nReceived arguments:\n<raw>` |
| Hook block | The hook's reason, or `Tool execution was blocked` |
| Abort | `Operation aborted` |
| Output token limit | `Tool call "x" was not executed: the response hit the output token limit, so its arguments may be truncated. Re-issue the tool call with complete arguments.` |

## Appendix B. Claude Code Literal Strings

*Table B1. Claude Code built-in tool output formats [code, emp].*

| Tool | Format and strings |
|---|---|
| Read | `N\tline`; a trailing newline yields a final empty numbered line. Over cap: `File content (N tokens) exceeds maximum allowed tokens (25000). Use offset and limit …`. Empty file: `<system-reminder>Warning: the file exists but the contents are empty.</system-reminder>`. PDF: `PDF file read: <path> (<size>)` plus a `document` block. Images: an image block, at most 2000×2000 px and 5 MB. |
| Bash | Success: stdout, stderr, and hints joined by newlines; empty output: `(Bash completed with no output)`. Failure: `Exit code N\n<stderr>\n<stdout>`. Timeout: `Exit code 143\nCommand timed out after 1s` (default 120 s, max 600 s). Spill: `<persisted-output>\nOutput too large (39.1KB). Full output saved to: … \n\nPreview (first 2KB):\n…\n</persisted-output>`. Background: `Command running in background with ID: X. Output is being written to: …` |
| Edit / Write | `The file <path> has been updated successfully.`; `File created successfully at: <path>`; optional suffix ` (file state is current in your context — no need to Read it back)`. Validation errors: `String to replace not found in file.`, `Found N matches of the string to replace, but replace_all is false. …`, `File has not been read yet. Read it first before writing to it.` |
| Grep / Glob | Grep: `Found N files\n…`, content lines, or counts ending `Found M total occurrences across F files.`; default `head_limit` 250. Glob: newline-separated paths, limit 100. |
| Others | WebSearch ends with `REMINDER: You MUST include the sources above …`. Agent appends an `agentId: … <usage>…</usage>` trailer. TodoWrite returns `Todos have been modified successfully. …` |

*Table B2. Claude Code error strings [code, emp].*

| Case | Text |
|---|---|
| Unknown tool | `<tool_use_error>Error: No such tool available: X</tool_use_error>` |
| Invalid JSON | `<tool_use_error>InputValidationError: Read was called with input that could not be parsed as JSON. … Retry with valid JSON.</tool_use_error>` |
| Schema failure | `<tool_use_error>InputValidationError: X failed due to the following issue:\nThe parameter \`p\` type is expected as …</tool_use_error>` |
| Execution throws | Unwrapped message, for example `File does not exist. Note: your current working directory is …` |
| Permission denied | Unwrapped, for example `Claude requested permissions to use X, but you haven't granted it yet.` |
| User rejects | `The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). STOP what you are doing and wait for the user to tell you how to proceed.` |
| Interrupt | `The user doesn't want to take this action right now. STOP …` |
| Missing result | `[Tool result missing due to internal error]` |

## Appendix C. Cursor Literal Strings

*Table C1. Cursor rendered tool output formats [code].*

| Tool | Format and strings |
|---|---|
| Read | `     N\|line`; omitted ranges shown as `... 40 lines not shown ...`. Empty: `File is empty.` Over cap: `File content (N characters) exceeds maximum allowed characters (100000 characters). …`. Images: `Read image file: <path>` plus an image. |
| Shell | ``Exit code: N\n\nCommand output[ (truncated to 20000 characters)]:\n\n```\n…\n```\n\nCommand completed in N ms.\n\nShell state (cwd, env vars) persists for subsequent calls. Current directory: /path``. Truncation marker: `... (output truncated) ...`. Spill: `Command output has been written to: <file> (12.3 KB, 456 lines)`. Timeout: `Command timed out. … The shell has been terminated.` |
| Edit / Write | `The file <path> has been updated.`, `N occurrences in file <path> have been updated.`, `Wrote contents to <path>`, `Success. Updated the following files:\nA <path>`. No diff or linter output. |
| Grep | `<workspace_result workspace_path="…">` with `  12:match` and `  13-context` lines; 15,000-character budget. |
| Glob / Ls | `Result of search in '<dir>' (total N files):\n- a`, 5,000-character cap. Ls: indented tree, 10,000-character cap, 5 s timeout. |
| ReadLints | `Found N linter errors in M files:` followed by `[ERROR] L12:4 - msg (source)` lines |
| Web fetch | `# Content from <url>\n\n<markdown>`, 100,000-character cap or spill |

*Table C2. Cursor error strings [code].*

| Case | Text |
|---|---|
| Rejection | `Rejected: <reason>`; `The web search was rejected by the user.` |
| Write in ask mode | `You are in ask mode and cannot run non read-only tools. Ask the user to switch to agent mode if edits are required.` |
| Interrupt | `Error: Shell command was interrupted by the user after Nms before it completed.\n\nOutput collected before interruption: …` |
| No exit status | `The shell command returned no exit status, so its result is unknown — do not assume it ran or succeeded…` |
