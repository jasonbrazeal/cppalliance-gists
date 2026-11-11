 ```lua
   markdown.section(md, "# Guide").title                                  --> "Guide"
   markdown.section(md, { "# Guide", "## Templates" }).line               --> 16
   markdown.section(md, { "# Guide", "## Templates", "### Extras" }).level --> 3
   markdown.section(md, "### Extras").line                                --> 34
   markdown.section(md, { "## Templates", "### Extras" }).line            --> 34
   markdown.section(md, "# Templates")                                    --> nil   (no level-1 Templates)
   markdown.section(md, { "# Guide", "## Nope" })                         --> nil
   markdown.section(guide.blocks, "## Usage").line                        --> 42
 ```
