
 This assumes a hypothetical runvil serve command. It hosts a folder of prompts as an MCP server and is also an MCP client to the
 wg21-papers server.

 ```
   runvil serve ./prompts --mcp mcp.json
 ```

 Listing

 Each .md in ./prompts becomes a tool, so summarize.md becomes summarize and another.md becomes critique. inputSchema comes from args::

 ```json
   { "name": "summarize",
     "description": "Summarize a paper with its metadata, then critique the summary",
     "inputSchema": { "type": "object",
       "properties": { "paper": { "type": "string" }, "paper_id": { "type": "string" } },
       "required": ["paper", "paper_id"] } }
 ```
