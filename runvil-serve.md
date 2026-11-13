Assuming something like `runvil serve ./prompts --mcp mcp.json`, that runs one long-lived process that is both an MCP server and an MCP client.

- Inbound: clients connect over Streamable HTTP and see each prompt in `./prompts` as a tool.
- Outbound: it connects once to the servers in `mcp.json` (e.g. `wg21-papers`), and every run's `mcp` Pack uses those connections.

## startup

1. Parse every `.md` in `./prompts`. Files that fail to parse aren't listed.
2. The tool name is the frontmatter `name`, not the filename. Duplicate names are a startup error.
3. Prompts whose `uses:`/`models:` the server can't satisfy aren't listed.
4. Connect to the `mcp.json` servers up front, so runs never hit a server that's still loading.

## tools/list

Each prompt becomes a tool:
- `name` and `description` come from the frontmatter.
- `inputSchema` comes from `args:`. Types map 1:1, args without `optional: true` are required, and `default`/`description` carry over.
- A prompt with no `args:` gets an optional `prose` string.

```json
{ "name": "summarize",
  "description": "Summarize a paper with its metadata, then critique the summary",
  "inputSchema": { "type": "object",
    "properties": { "paper": { "type": "string" }, "paper_id": { "type": "string" } },
    "required": ["paper", "paper_id"] } }
```

## tools/call

1. Validate `arguments` against `inputSchema`. A bad call returns `isError` and no run starts.
2. Encode `arguments` as the argument string and start a fresh run. The prompt reads it as `argv`.
3. The run's return value is the tool result. A run error returns `isError` with the message, and a client cancel cancels the run.

Each call is an independent run with its own store and `var`.

## advantages

- The same prompt file runs under the CLI or over MCP, and the frontmatter is the whole contract.
- `execute("critique.md", ...)` resolves next to the calling file and runs in-process, not over MCP.
- Outbound MCP servers and their tokens stay on the server and are never exposed to callers.
- Edited prompts are re-parsed, and the server sends `notifications/tools/list_changed`.
