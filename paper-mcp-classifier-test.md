```bash
jason@debian-dev:/code/runvil-cli$ time /home/jason/.cache/cargo-target/release/runvil /mnt/VM/prompts/paper-classifier-mcp-demo.md --mcp /code/runvil-cli/mcp.json


# Proposal or not: 6 WG21 papers through paper-mcp

Tools used per paper: `get_metadata`, `get_outline`, `list_revisions`, `get_citations`, `get_sections`, `get_lines`, and `search` (three fulltext probes).

| Paper | Title | Group | Sections | Revs | Cites / cited by | Wording / polls / minutes hits | Heuristic | Model | Reply |
|---|---|---|---|---|---|---|---|---|---|
| p3045r9 | Quantities and units library | SG16 Unicode,LEWG Library Evolution | 37 | 2 | 5 / 0 | 10 / 4 / 4 | proposal (5) | **proposal** | `PROPOSAL` |
| p2728r14 | Unicode in the Library, Part 1: UTF Transcoding | SG9 Ranges,SG16 Unicode,LEWG Library Evolution | 15 | 2 | 5 / 0 | 10 / 6 / 6 | proposal (5) | **proposal** | `PROPOSAL` |
| p4313r1 | Bitmask operations for enums | LEWG Library Evolution | 8 | 2 | 0 / 0 | 3 / 0 / 0 | proposal (4) | **proposal** | `PROPOSAL` |
| p4294r1 | views::take_last and views::drop_last | SG9 Ranges,LEWG Library Evolution,LWG Library | 10 | 2 | 2 / 0 | 1 / 0 / 0 | proposal (4) | **proposal** | `PROPOSAL` |
| n5049 | WG21 2026-06 Brno Admin Telecon Minutes | All of WG21 | 6 | 1 | 5 / 0 | 2 / 0 / 6 | non-proposal (-2) | **non-proposal** | `NOT_PROPOSAL` |
| n5045 | WG21 agenda: 8-13 June 2026, Brno, Czechia | All of WG21 | 7 | 1 | 4 / 0 | 0 / 1 / 3 | non-proposal (-3) | **non-proposal** | `NOT_PROPOSAL` |

**Totals:** 4 proposal, 2 non-proposal, 0 unparsed. The heuristic agrees with the model on 6 of 6 papers.

## Results as JSON Lines

{"heuristic":"proposal","label":"proposal","paper_id":"p3045r9","reply":"PROPOSAL","title":"Quantities and units library"}
{"heuristic":"proposal","label":"proposal","paper_id":"p2728r14","reply":"PROPOSAL","title":"Unicode in the Library, Part 1: UTF Transcoding"}
{"heuristic":"proposal","label":"proposal","paper_id":"p4313r1","reply":"PROPOSAL","title":"Bitmask operations for enums"}
{"heuristic":"proposal","label":"proposal","paper_id":"p4294r1","reply":"PROPOSAL","title":"views::take_last and views::drop_last"}
{"heuristic":"non-proposal","label":"non-proposal","paper_id":"n5049","reply":"NOT_PROPOSAL","title":"WG21 2026-06 Brno Admin Telecon Minutes"}
{"heuristic":"non-proposal","label":"non-proposal","paper_id":"n5045","reply":"NOT_PROPOSAL","title":"WG21 agenda: 8-13 June 2026, Brno, Czechia"}

real    0m1.934s
user    0m0.098s
sys     0m0.072s

```
