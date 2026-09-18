# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo>=0.24",
#     "pandas",
#     "pysbd>=0.3.4",
# ]
# ///

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="columns", app_title="the CHONK report")


@app.cell(column=0)
def _():
    import ast
    import bisect
    import inspect
    import re
    import statistics
    import textwrap
    from dataclasses import dataclass, field
    from enum import Enum, auto
    from pathlib import Path
    from typing import cast

    import marimo as mo
    import pandas as pd
    from pysbd import Segmenter
    from pysbd.utils import TextSpan

    return (
        Enum,
        Path,
        Segmenter,
        TextSpan,
        ast,
        auto,
        bisect,
        cast,
        dataclass,
        field,
        inspect,
        mo,
        pd,
        re,
        statistics,
        textwrap,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # the CHONK report - 9/16/26

    How `wg21-paperflow` splits WG21 papers before processing. This notebook is
    self-contained: the chunking code is copied verbatim from the repository
    into the cells below (see provenance), and every statistic is computed by
    running those copies over the sample papers.

    Questions this report answers:

    1. Is there one chunking algorithm or several?
    2. For a sample of papers, how many chunks do they become?
    3. Are the chunks contextualized?
    4. Is it parameterized for chunk size and overlap experiments?
    5. Does it misbehave on edge cases (tiny papers, huge papers, no headings)?
    """)
    return


@app.cell
def _(Path, mo):
    VENDORED_COMMIT = "6152381cf51b2c91f53d622180cf096473f25d8b"
    VENDORED_AT = "2026-09-18T18:19Z"
    PAPERSTORE_DIR = Path(
        mo.cli_args().get("paperstore", mo.notebook_dir() / "data" / "paperstore")
    )
    PAPER_IDS = [
        "p3045r9",
        "p2728r14",
        "p0260r20",
        "p1040r11",
        "p3091r6",
        "p2806r5",
        "p3100r8",
        "p2826r4",
        "p2287r6",
        "p2719r7",
    ]
    return PAPERSTORE_DIR, PAPER_IDS, VENDORED_AT, VENDORED_COMMIT


@app.cell(hide_code=True)
def _(PAPERSTORE_DIR, VENDORED_AT, VENDORED_COMMIT, mo):
    mo.md(f"""
    ## Provenance

    All repository code in this notebook was copied by hand from
    `wg21-paperflow` at commit `{VENDORED_COMMIT[:12]}` on {VENDORED_AT}
    (UTC). Only the parts needed to run the three chunkers were copied. Four
    mechanical deviations from the originals, all forced by running inside
    marimo cells:

    1. `from __future__ import annotations` is dropped (not legal inside a
       cell).
    2. Each module body is wrapped in a `_module()` factory so its names stay
       module-local instead of colliding across cells.
    3. Module-private names lose their leading underscore (`_parse_headings`
       becomes `parse_headings`, `_chunk_markdown` becomes `chunk_markdown`,
       and so on). marimo treats any `_name` as cell-private and rewrites or
       deletes it, which breaks closures called from other cells.
    4. The one self-referential dataclass field (`TreeSection.children`) uses
       a string annotation.

    Logic, ordering, docstrings and comments are otherwise unchanged. The
    prose in this report keeps the original names (`_chunk_markdown`, etc.)
    when referring to the repository.

    | Notebook cell | Copied from |
    |---|---|
    | markdown helpers | `packages/pipeline/src/pipeline/markdown.py` (`HEADING_RE`, `YAML_FENCE_RE`, `front_matter_end_index`) |
    | token budget | `packages/pipeline/src/pipeline/tokens.py` |
    | heading classifiers | `packages/assay/src/assay/heading_classifiers.py` (blanking classifiers only) |
    | blanking | `packages/assay/src/assay/blanking.py` |
    | standardese | `packages/assay/src/assay/paper_routing/standardese.py` |
    | algorithm 1 | `packages/assay/src/assay/chunker.py` |
    | algorithm 2 | `packages/assay/src/assay/rag.py` (`RagChunk`, `_estimate_tokens`, `_chunk_markdown`) |
    | algorithm 3 | `packages/assay/src/assay/paper_routing/split.py` |
    | line formatting | `packages/assay/src/assay/locs.py` |

    Paper markdown is read from `{PAPERSTORE_DIR}`. Override with
    `-- --paperstore /path/to/dir` when launching marimo.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Q1. One algorithm or several?

    **Three**, each independent and each with its own size logic. None share
    code beyond `pipeline.markdown.HEADING_RE`.

    | # | Function | Defined | Called from | Unit of output | Used by |
    |---|---|---|---|---|---|
    | 1 | `chunk_paper()` | `packages/assay/src/assay/chunker.py` | `assay/pipeline.py` `_custom_survey` (Step 3) | `Section` (heading, level, line range, char count) | Every per-chunk LLM step (Extract, Decide, Classify, Analyze, Challenge) |
    | 2 | `_chunk_markdown()` | `packages/assay/src/assay/rag.py` | `rag.py` `build_cited_paper_index` / `build_single_paper_index` (Step 2) | `RagChunk` (text, heading, line range) | Embedding index over cited papers |
    | 3 | `split_sentences()` | `packages/assay/src/assay/paper_routing/split.py` | `paper_routing/hypotheses.py` | `RawSentence` (text, start line) | Paper-routing NLI / seqcls classifier |

    The three algorithms serve three different consumers, so "chunking" means
    something different for each:

    - **Algorithm 1, `chunk_paper()`**: cuts the paper under review into pieces
      that are each sent, one at a time, as the prompt to an LLM call (Extract,
      Decide, Classify, Analyze). A chunk here is literally "the text the model
      reads in one request." If this chunker splits badly, the model reasons
      over a bad slice. This is the one that matters for anti-pattern hunting.
    - **Algorithm 2, `_chunk_markdown()`**: cuts *other* papers (the ones the
      paper under review cites) into small pieces, embeds each with a
      sentence-transformer, and stores them in an in-memory vector index. The
      LLM never sees these chunks directly; later steps run a similarity search
      and inject the top hits as evidence. A chunk here is "a retrievable
      passage," sized for embedding quality (400 tokens), not for a model's
      context window.
    - **Algorithm 3, `split_sentences()`**: cuts the paper under review into
      individual sentences (plus whole code blocks and BNF lines) and feeds each
      to a small local NLI/seqcls classifier to decide what kind of paper it is
      and where it should route. Nothing is sent to an LLM; the output is
      per-sentence scores. Calling it "chunking" is a stretch, but it is a third
      independent place the paper text gets divided before any processing, and
      it has its own rules about what stays together.

    So: 1 shapes LLM input, 2 shapes retrieval, 3 shapes classifier input.
    """)
    return


@app.cell(hide_code=True)
def _(VENDORED, mo):
    def _code(origin: str) -> object:
        return mo.md(f"```python\n{VENDORED[origin]}\n```")

    mo.accordion(
        {
            "Algorithm 1: `assay/chunker.py`": _code("assay/chunker.py"),
            "Algorithm 2: `assay/rag.py::_chunk_markdown`": _code("assay/rag.py"),
            "Algorithm 3: `assay/paper_routing/split.py`": _code(
                "assay/paper_routing/split.py"
            ),
            "Support: `pipeline/tokens.py`": _code("pipeline/tokens.py"),
            "Support: `pipeline/markdown.py`": _code("pipeline/markdown.py"),
            "Support: `assay/blanking.py`": _code("assay/blanking.py"),
            "Support: `assay/heading_classifiers.py`": _code(
                "assay/heading_classifiers.py"
            ),
            "Support: `assay/paper_routing/standardese.py`": _code(
                "assay/paper_routing/standardese.py"
            ),
            "Support: `assay/locs.py`": _code("assay/locs.py"),
        }
    )
    return


@app.cell
def _(CHARS_PER_TOKEN, mo):
    chunk_tokens_slider = mo.ui.slider(
        250, 8000, value=2000, step=250, show_value=True, label="chunk-tokens"
    )
    chars_per_token_slider = mo.ui.slider(
        2.5, 5.0, value=CHARS_PER_TOKEN, step=0.25, show_value=True, label="chars per token"
    )
    rag_tokens_slider = mo.ui.slider(
        100, 2000, value=400, step=50, show_value=True, label="max_tokens"
    )
    blank_switch = mo.ui.switch(value=True, label="run blank_paper() on the markdown first")
    return (
        blank_switch,
        chars_per_token_slider,
        chunk_tokens_slider,
        rag_tokens_slider,
    )


@app.cell
def _(chars_per_token_slider, chunk_tokens_slider):
    max_chars = int(chunk_tokens_slider.value * chars_per_token_slider.value)
    return (max_chars,)


@app.cell
def _(PAPERSTORE_DIR, PAPER_IDS, blank_paper, blank_switch):
    raw_papers = {pid: (PAPERSTORE_DIR / f"{pid}.md").read_text() for pid in PAPER_IDS}
    papers = (
        {pid: blank_paper(md, paper_id=pid) for pid, md in raw_papers.items()}
        if blank_switch.value
        else raw_papers
    )
    return (papers,)


@app.cell
def _(HEADING_RE, dataclass):
    @dataclass(frozen=True)
    class ChunkView:
        index: int
        heading: str
        start_line: int
        end_line: int
        chars: int
        text: str

    def sections_to_views(sections, source: str) -> list[ChunkView]:
        lines = source.splitlines()
        return [
            ChunkView(
                index=i,
                heading=s.heading,
                start_line=s.start_line,
                end_line=s.end_line,
                chars=s.char_count,
                text="\n".join(lines[s.start_line - 1 : s.end_line]),
            )
            for i, s in enumerate(sections)
        ]

    def rag_to_views(chunks) -> list[ChunkView]:
        return [
            ChunkView(
                index=i,
                heading=c.heading,
                start_line=c.start_line,
                end_line=c.end_line,
                chars=len(c.text),
                text=c.text,
            )
            for i, c in enumerate(chunks)
        ]

    def heading_path(source: str) -> list[str]:
        """Ancestor breadcrumb for each source line, from the heading stack."""
        stack: list[tuple[int, str]] = []
        paths: list[str] = []
        for line in source.splitlines():
            m = HEADING_RE.match(line)
            if m:
                level = len(m.group(1))
                stack = [(lv, t) for lv, t in stack if lv < level]
                stack.append((level, m.group(2).strip()))
            paths.append(" > ".join(t for _, t in stack))
        return paths

    return heading_path, rag_to_views, sections_to_views


@app.cell
def _(re, statistics):
    DATA_URI_RE = re.compile(r"data:[a-z]+/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=]+")

    def size_bar(chars: int, budget: int, width: int = 20) -> str:
        filled = min(width, round(width * chars / budget)) if budget else 0
        over = "!" if chars > budget else ""
        return "█" * filled + "·" * (width - filled) + over

    def coverage(views, source: str) -> tuple[int, int, int]:
        """(non-blank lines covered, non-blank lines total, overlapping line count)."""
        lines = source.splitlines()
        nonblank = {i + 1 for i, ln in enumerate(lines) if ln.strip()}
        seen: dict[int, int] = {}
        for v in views:
            for ln in range(v.start_line, v.end_line + 1):
                seen[ln] = seen.get(ln, 0) + 1
        covered = len(nonblank & seen.keys())
        overlapping = sum(1 for n in seen.values() if n > 1)
        return covered, len(nonblank), overlapping

    def data_uri_chars(source: str) -> int:
        return sum(len(m.group(0)) for m in DATA_URI_RE.finditer(source))

    def summarize(pid: str, views, source: str, budget: int) -> dict:
        sizes = [v.chars for v in views] or [0]
        covered, total, overlapping = coverage(views, source)
        return {
            "paper": pid,
            "lines": len(source.splitlines()),
            "chars": len(source),
            "data: URI chars": data_uri_chars(source),
            "chunks": len(views),
            "min": min(sizes),
            "median": int(statistics.median(sizes)),
            "max": max(sizes),
            "over budget": sum(1 for s in sizes if s > budget),
            "tiny (<10%)": sum(1 for s in sizes if s < budget * 0.1),
            "coverage": f"{covered}/{total}",
            "overlap lines": overlapping,
        }

    return coverage, size_bar, summarize


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Q2. How many chunks per paper?

    The switch below controls the input to **all** tables in this report.

    `blank_paper()` (`assay/blanking.py`) is a pre-processing pass that erases
    the non-prose parts of a paper so the LLM never sees them. It does **not**
    delete lines; it overwrites each targeted line with an empty line so the
    file keeps the same line count and every line number downstream still
    points at the right place. Four passes:

    1. YAML frontmatter (`---` block at top) → blank.
    2. Any section whose heading looks like a revision history ("Revision
       History", "Changes since R3", ...) → heading and body blanked, up to the
       next heading that does not look like revision history.
    3. Same for reference sections ("References", "Bibliography").
    4. Same for acknowledgments.

    Heading detection uses the classifiers in `assay/heading_classifiers.py`,
    plus a per-paper override table (currently only `P0260`, which also blanks
    "Old Revision History").

    Effect on chunking: the blanked regions still exist as runs of empty lines
    inside whatever section they fall in, so they still count toward
    `char_count` (1 char per blanked line) and can still be emitted as a chunk
    if the heading tree puts them there. They just contain nothing.

    The LLM pipeline always blanks before `chunk_paper()` (`_custom_receive`,
    Step 0). The RAG index reads cited papers raw and never blanks. Switch off
    to see the raw-input numbers.
    """)
    return


@app.cell
def _(blank_switch):
    blank_switch
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Algorithm 1: `chunk_paper()` (what the LLM steps see)

    The two sliders are multiplied to give the `max_chars` argument:
    `chunk_paper(md, max_chars=chunk_tokens * chars_per_token)`. In the real
    pipeline `chunk-tokens` comes from the `**chunk-tokens:**` prompt field
    (default 2000) and `chars per token` from the agent's `SERVICES.toml`
    entry (fallback 3.25). Drag either one and this table recomputes.

    `coverage` is non-blank source lines that land in some chunk over all
    non-blank lines. `overlap lines` counts lines appearing in more than one
    chunk (expected: 0, there is no overlap mechanism).
    """)
    return


@app.cell
def _(chunk_paper, max_chars, papers, sections_to_views):
    alg1_views = {
        pid: sections_to_views(chunk_paper(md, max_chars=max_chars), md)
        for pid, md in papers.items()
    }
    return (alg1_views,)


@app.cell
def _(
    alg1_views,
    chars_per_token_slider,
    chunk_tokens_slider,
    max_chars,
    mo,
    papers,
    pd,
    summarize,
):
    alg1_df = pd.DataFrame(
        [summarize(pid, alg1_views[pid], papers[pid], max_chars) for pid in papers]
    )
    mo.vstack(
        [
            mo.hstack([chunk_tokens_slider, chars_per_token_slider], justify="start"),
            mo.md(
                f"`chunk_paper(md, max_chars={chunk_tokens_slider.value} × "
                f"{chars_per_token_slider.value} = **{max_chars:,}**)`"
            ),
            mo.ui.table(alg1_df, selection=None, pagination=False),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Algorithm 2: `_chunk_markdown()` (RAG index)

    The slider is the `max_tokens` argument:
    `_chunk_markdown(md, pid, "citation", max_tokens=...)`. Default 400. The
    function converts it to characters with its own hard-coded 4 chars/token,
    ignoring `pipeline.tokens.CHARS_PER_TOKEN`.

    Note that the RAG chunker's `start_line`/`end_line` are *computed* from
    paragraph text rather than tracked from the source, so `coverage` and
    `overlap lines` here measure how far its bookkeeping drifts, not real
    overlap in content.
    """)
    return


@app.cell
def _(chunk_markdown, papers, rag_to_views, rag_tokens_slider):
    alg2_views = {
        pid: rag_to_views(
            chunk_markdown(md, pid, "citation", max_tokens=rag_tokens_slider.value)
        )
        for pid, md in papers.items()
    }
    return (alg2_views,)


@app.cell
def _(
    RAG_CHARS_PER_TOKEN,
    alg2_views,
    mo,
    papers,
    pd,
    rag_tokens_slider,
    summarize,
):
    rag_budget = rag_tokens_slider.value * RAG_CHARS_PER_TOKEN
    alg2_df = pd.DataFrame(
        [summarize(pid, alg2_views[pid], papers[pid], rag_budget) for pid in papers]
    )
    mo.vstack(
        [
            rag_tokens_slider,
            mo.md(
                f"`_chunk_markdown(..., max_tokens={rag_tokens_slider.value})` → "
                f"{rag_tokens_slider.value} × 4 = **{rag_budget:,} chars**"
            ),
            mo.ui.table(alg2_df, selection=None, pagination=False),
        ]
    )
    return (rag_budget,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### Algorithm 3: `split_sentences()` (routing classifier)

    Unit counts rather than chunk counts. Fenced code blocks are kept whole,
    which is where the `max` column comes from.
    """)
    return


@app.cell
def _(mo, papers, pd, split_sentences, statistics):
    def _summarize_sentences(pid: str, source: str) -> dict:
        units = split_sentences(source)
        sizes = [len(u.text) for u in units] or [0]
        fenced = sum(1 for u in units if u.text.lstrip().startswith(("```", "~~~")))
        return {
            "paper": pid,
            "units": len(units),
            "fenced blocks": fenced,
            "min": min(sizes),
            "median": int(statistics.median(sizes)),
            "max": max(sizes),
        }

    alg3_df = pd.DataFrame([_summarize_sentences(pid, md) for pid, md in papers.items()])
    mo.ui.table(alg3_df, selection=None, pagination=False)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Q3. Are the chunks contextualized?

    Minimally. Concretely:

    - **Algorithm 1** carries only the chunk's own heading title. When small
      sections are coalesced the heading becomes `"A + B + C"`. There is no
      parent breadcrumb (compare the two heading columns in the chunk browser
      at the end),
      no paper title or abstract prepended, and no overlap with neighbouring
      chunks. The pipeline adds `# Paper: {pid}` and `(chunk i, lines a-b)` at
      prompt-build time, nothing else.
    - **Algorithm 2** prepends `## {heading}` to paragraph-split sub-chunks so
      each embedded text has its section title. Whole-section chunks already
      contain their heading line. No parent context, no overlap.
    - **Algorithm 3** carries nothing but the sentence and its line number.
      Section context is recovered separately via `line_section_map`.

    The table below counts how often the carried heading differs from the full
    ancestor path, i.e. how many chunks lose their parent context.
    """)
    return


@app.cell
def _(alg1_views, alg2_views, heading_path, mo, papers, pd):
    def _context_row(pid: str) -> dict:
        paths = heading_path(papers[pid])
        v1 = alg1_views[pid]
        v2 = alg2_views[pid]
        coalesced = sum(1 for v in v1 if " + " in v.heading)
        nested1 = sum(
            1
            for v in v1
            if 0 < v.start_line <= len(paths) and " > " in paths[v.start_line - 1]
        )
        subchunks = sum(1 for v in v2 if v.text.startswith(f"## {v.heading}\n\n"))
        return {
            "paper": pid,
            "alg1 chunks": len(v1),
            "alg1 coalesced (A + B)": coalesced,
            "alg1 nested (parent dropped)": nested1,
            "alg2 chunks": len(v2),
            "alg2 heading-prepended sub-chunks": subchunks,
        }

    context_df = pd.DataFrame([_context_row(pid) for pid in papers])
    mo.ui.table(context_df, selection=None, pagination=False)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Q4. Is it parameterized for size and overlap experiments?

    **Size: yes. Overlap: no.**

    - Algorithm 1 takes `max_chars`. The pipeline derives it from the prompt
      field `**chunk-tokens:**` (default 2000) times the agent's
      `chars_per_token`. Changing chunk size for a run is a one-line prompt edit.
    - Algorithm 2 takes `max_tokens` (default 400), but hard-codes 4
      chars/token independently of `pipeline.tokens.CHARS_PER_TOKEN`.
    - Algorithm 3 has no size parameter at all; it is unit-based.
    - No algorithm has an overlap parameter or any sliding-window logic.
      `pipeline/prompt.py` mentions `**chunk-overlap:** 100` only as an
      example of an *unconsumed* extra field.

    The actual signatures, read from the vendored code, and a size sweep of
    Algorithm 1 over the sample:
    """)
    return


@app.cell
def _(chunk_markdown, chunk_paper, inspect, mo, split_sentences):
    def _params(fn) -> str:
        return ", ".join(
            f"{name}={p.default!r}" if p.default is not inspect.Parameter.empty else name
            for name, p in inspect.signature(fn).parameters.items()
        )

    signature_rows = [
        {"function": "chunk_paper", "parameters": _params(chunk_paper)},
        {"function": "_chunk_markdown", "parameters": _params(chunk_markdown)},
        {"function": "split_sentences", "parameters": _params(split_sentences)},
    ]
    mo.ui.table(signature_rows, selection=None, pagination=False)
    return


@app.cell
def _(CHARS_PER_TOKEN, chunk_paper, mo, papers, pd):
    _sweep_tokens = [500, 1000, 2000, 4000, 8000]
    sweep_df = pd.DataFrame(
        [
            {
                "paper": pid,
                **{
                    f"{t} tok": len(chunk_paper(md, max_chars=int(t * CHARS_PER_TOKEN)))
                    for t in _sweep_tokens
                },
            }
            for pid, md in papers.items()
        ]
    )
    mo.vstack(
        [
            mo.md("Chunk count from `chunk_paper()` at each `chunk-tokens` setting:"),
            mo.ui.table(sweep_df, selection=None, pagination=False),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Q5. Edge cases

    Synthetic inputs run through both chunkers at the current budget. Things to
    look for: a tiny paper exploding into many chunks, a huge unsplittable
    section being truncated, or content going missing.
    """)
    return


@app.cell
def _(
    chunk_markdown,
    chunk_paper,
    coverage,
    max_chars,
    mo,
    pd,
    rag_budget,
    rag_to_views,
    rag_tokens_slider,
    sections_to_views,
):
    _tiny = "# Tiny\n\nOne line.\n\n## A\n\nTwo.\n\n## B\n\nThree.\n\n## C\n\nFour.\n"
    _no_headings = "Just prose.\n\n" * 200
    _one_huge_para = "# Big\n\n" + ("word " * 20000).strip() + "\n"
    _many_paras_no_sub = "# Big\n\n" + "\n\n".join(["A paragraph. " * 40] * 100) + "\n"
    _bold_subs = "# Big\n\n" + "\n\n".join(
        f"**3.{i}** **Issue {i}**\n\n" + ("Body text. " * 120) for i in range(1, 30)
    ) + "\n"
    _skip_level = "# Root\n\n" + "\n\n".join(
        f"#### Issue {i}\n\n" + ("Body text. " * 100) for i in range(1, 30)
    ) + "\n"
    _empty = ""

    _cases = {
        "tiny paper (4 headings, ~60 chars)": _tiny,
        "empty string": _empty,
        "no headings, 200 paragraphs": _no_headings,
        "one 100k-char paragraph, one heading": _one_huge_para,
        "one heading, 100 paragraphs, no subsections": _many_paras_no_sub,
        "one heading, 29 bold **3.N** subsections": _bold_subs,
        "H1 then 29 H4s (skip-level)": _skip_level,
    }

    def _row(name: str, src: str) -> dict:
        v1 = sections_to_views(chunk_paper(src, max_chars=max_chars), src)
        v2 = rag_to_views(chunk_markdown(src, "synthetic", "citation", max_tokens=rag_tokens_slider.value))
        c1, t1, _ = coverage(v1, src)
        chars1 = sum(v.chars for v in v1)
        return {
            "case": name,
            "input chars": len(src),
            "alg1 chunks": len(v1),
            "alg1 max chunk": max((v.chars for v in v1), default=0),
            "alg1 over budget": sum(1 for v in v1 if v.chars > max_chars),
            "alg1 chars lost": len(src) - chars1,
            "alg1 coverage": f"{c1}/{t1}",
            "alg2 chunks": len(v2),
            "alg2 max chunk": max((v.chars for v in v2), default=0),
            "alg2 over budget": sum(1 for v in v2 if v.chars > rag_budget),
        }

    edge_df = pd.DataFrame([_row(n, s) for n, s in _cases.items()])
    mo.vstack(
        [
            mo.md(
                f"Using the budgets set above: `chunk_paper` max_chars = "
                f"**{max_chars:,}**, `_chunk_markdown` = **{rag_budget:,}** chars."
            ),
            mo.ui.table(edge_df, selection=None, pagination=False),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ### RAG line-attribution drift

    `_chunk_markdown` derives `start_line`/`end_line` for paragraph-split
    sub-chunks by counting newlines in the *joined* text, after `re.split`
    has collapsed runs of blank lines and after prepending a two-line heading.
    The check below locates each sub-chunk's first body line in the real
    source and compares it to the reported `start_line`.
    """)
    return


@app.cell
def _(alg2_views, mo, papers, pd):
    def _drift_row(pid: str) -> dict:
        lines = papers[pid].splitlines()
        drifts: list[int] = []
        cursor = 0
        for v in alg2_views[pid]:
            prefix = f"## {v.heading}\n\n"
            if not v.text.startswith(prefix):
                continue
            first_body = v.text[len(prefix):].split("\n", 1)[0].strip()
            if not first_body:
                continue
            actual = next(
                (i + 1 for i in range(cursor, len(lines)) if lines[i].strip() == first_body),
                None,
            )
            if actual is None:
                continue
            cursor = actual
            drifts.append(v.start_line - actual)
        return {
            "paper": pid,
            "sub-chunks checked": len(drifts),
            "exact": sum(1 for d in drifts if d == 0),
            "drifted": sum(1 for d in drifts if d != 0),
            "max |drift| lines": max((abs(d) for d in drifts), default=0),
            "end_line > file length": sum(
                1 for v in alg2_views[pid] if v.end_line > len(lines)
            ),
        }

    drift_df = pd.DataFrame([_drift_row(pid) for pid in papers])
    mo.ui.table(drift_df, selection=None, pagination=False)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Findings

    - **Three separate chunkers**, not one. Only `chunk_paper()` affects what
      the LLM steps read. They disagree on chars-per-token (3.25 vs 4) and on
      which heading levels count (`#`-`######` vs `##`/`###` only).
    - **Chunk counts** for the sample are in the Q2 tables and respond to the
      sliders above. Use the chunk browser at the end to eyeball individual
      chunks.
    - ⚠️ **Context is thin**: chunk heading title only, no ancestor path, no
      overlap. Coalesced chunks get an `A + B + C` heading, which is the only
      hint that unrelated sections were glued together.
    - **Size is a one-line prompt parameter; overlap does not exist** in any of
      the three algorithms.
    - ⚠️ **No force-split**: `chunk_paper()` never truncates (chars lost is 0),
      but a section with no child headings and no bold `**N.N**` markers is
      emitted whole regardless of size, so over-budget chunks are possible.
      Tiny papers are coalesced into one chunk rather than exploded.
      `_chunk_markdown()` will emit an oversized chunk for any single paragraph
      over budget.
    - 🐞 **Base64 images are not stripped.** Papers with inline `data:image/...`
      URIs (`p2728r14`, `p1040r11` in the sample) produce single chunks of
      hundreds of thousands to over a million characters, because the image is
      one markdown line inside a section with nothing to split on. That chunk
      goes to the model verbatim. Compare the `data: URI chars` and `max`
      columns in the Algorithm 1 table.
    - 🐞 **RAG line numbers are wrong.** Every paragraph-split sub-chunk from
      `_chunk_markdown()` reports a `start_line` that does not match the
      source (see the drift table), because line offsets are reconstructed from
      the collapsed paragraph text rather than tracked from the input.

    ⚠️ = design risk worth reviewing. 🐞 = behaviour that looks like a bug.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Chunk browser

    Pick a paper and algorithm, inspect the size distribution, then open one
    chunk to see what actually goes out. Uses the budgets set by the sliders
    in Q2. For Algorithm 1 the rendering below is what
    `_build_extract_user_message` sends to the model (minus the untrusted
    guard wrapper).
    """)
    return


@app.cell
def _(PAPER_IDS, mo):
    browse_paper = mo.ui.dropdown(PAPER_IDS, value=PAPER_IDS[0], label="paper")
    browse_alg = mo.ui.dropdown(
        {"1: chunk_paper": 1, "2: _chunk_markdown": 2}, value="1: chunk_paper", label="algorithm"
    )
    mo.hstack([browse_paper, browse_alg], justify="start")
    return browse_alg, browse_paper


@app.cell
def _(alg1_views, alg2_views, browse_alg, browse_paper, max_chars, rag_budget):
    browse_views = (alg1_views if browse_alg.value == 1 else alg2_views)[browse_paper.value]
    browse_budget = max_chars if browse_alg.value == 1 else rag_budget
    return browse_budget, browse_views


@app.cell
def _(
    browse_budget,
    browse_paper,
    browse_views,
    heading_path,
    mo,
    papers,
    pd,
    size_bar,
):
    _paths = heading_path(papers[browse_paper.value])
    browse_df = pd.DataFrame(
        [
            {
                "#": v.index,
                "heading (as chunk carries it)": v.heading,
                "ancestor path (not carried)": _paths[v.start_line - 1]
                if 0 < v.start_line <= len(_paths)
                else "",
                "lines": f"{v.start_line}-{v.end_line}",
                "chars": v.chars,
                "size": size_bar(v.chars, browse_budget),
            }
            for v in browse_views
        ]
    )
    mo.ui.table(browse_df, selection=None, pagination=False)
    return


@app.cell
def _(browse_views, mo):
    chunk_picker = mo.ui.number(
        0, max(len(browse_views) - 1, 0), value=0, step=1, label="chunk #"
    )
    chunk_picker
    return (chunk_picker,)


@app.cell
def _(
    browse_alg,
    browse_paper,
    browse_views,
    chunk_picker,
    format_numbered_lines,
    mo,
    papers,
):
    _v = browse_views[chunk_picker.value]
    if browse_alg.value == 1:
        _lines = papers[browse_paper.value].splitlines()
        _numbered = format_numbered_lines(_lines, _v.start_line, _v.end_line)
        _rendered = (
            f"# Paper: {browse_paper.value}\n\n"
            f"## {_v.heading} (chunk {_v.index}, lines {_v.start_line}-{_v.end_line})\n\n"
            f"{_numbered}"
        )
    else:
        _rendered = _v.text
    mo.md(f"**{_v.chars:,} chars**\n\n```markdown\n{_rendered}\n```")
    return


@app.cell(column=1, hide_code=True)
def _(mo):
    mo.md(r"""
    ## Vendored code

    Copies of the repository modules the report runs. See Provenance in the
    main column for commit, date, and the list of deviations. The accordion
    under Q1 renders these cells' source.
    """)
    return


@app.cell
def _(re):
    "vendored: pipeline/markdown.py"

    def _module():
        YAML_FENCE_RE = re.compile(r"^---\s*$")

        HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")

        def front_matter_end_index(lines: list[str]) -> int:
            """Index of the first body line after YAML front matter.

            Returns 0 when the document does not begin with a ``---`` fence
            (first non-blank line is not a fence). When the opening fence has
            no closing fence, returns ``len(lines)`` so the entire document is
            treated as front matter, matching assay blanking Pass 1.
            """
            saw_open = False
            for i, line in enumerate(lines):
                stripped = line.lstrip()
                if YAML_FENCE_RE.match(stripped):
                    if saw_open:
                        return i + 1
                    saw_open = True
                elif not saw_open and stripped:
                    return 0
            if saw_open:
                return len(lines)
            return 0

        return HEADING_RE, front_matter_end_index

    HEADING_RE, front_matter_end_index = _module()
    return HEADING_RE, front_matter_end_index


@app.cell
def _():
    "vendored: pipeline/tokens.py"

    def _module():
        CHARS_PER_TOKEN: float = 3.25
        """Conservative characters-per-token for modern BPE tokenizers.

        Lower than the empirical ratios so that token estimates never overfill
        a model's context window. Calibrated against WG21 papers (English prose
        with embedded C++ code) via study/token-ratio/:

          Claude Opus 4.6:    3.51 measured (use 3.25 conservative)
          Qwen3 (32B/235B):  4.05 measured (use 4.0 conservative)
          DeepSeek-R1-70B:   4.20 measured (use 4.0 conservative)

        Open-weight models show stdev ~0.35-0.70 across 256-token windows,
        with code-heavy chunks dropping to ~2.5 chars/token and prose-heavy
        sections reaching ~5.5. Per-model values are set in SERVICES.toml
        via chars_per_token; this constant is the fallback when no agent is
        available.
        """

        def est_tokens(text: str, *, agent: "AgentBackend | None" = None) -> int:
            """Estimate token count from text length.

            Uses the agent's calibrated chars_per_token if provided,
            otherwise falls back to the global CHARS_PER_TOKEN constant.
            """
            cpt = agent.chars_per_token if agent else CHARS_PER_TOKEN
            return max(1, int(len(text) / cpt))

        def tokens_to_chars(tokens: int, *, agent: "AgentBackend | None" = None) -> int:
            """Convert a token budget to a character budget.

            Uses the agent's calibrated chars_per_token if provided,
            otherwise falls back to the global CHARS_PER_TOKEN constant.
            """
            cpt = agent.chars_per_token if agent else CHARS_PER_TOKEN
            return int(tokens * cpt)

        return CHARS_PER_TOKEN

    CHARS_PER_TOKEN = _module()
    return (CHARS_PER_TOKEN,)


@app.cell
def _(Enum, HEADING_RE, auto, re):
    "vendored: assay/heading_classifiers.py"

    def _module():
        class HeadingKind(Enum):
            """Tri-state result for blanking heading classifiers."""

            YES = auto()
            NO = auto()
            UNKNOWN = auto()

        REVISION_HEADING_RES: list[re.Pattern[str]] = [
            re.compile(r"^#{1,6}\s+.*revision\s+history", re.IGNORECASE),
            re.compile(r"^#{1,6}\s+.*change\s*log", re.IGNORECASE),
            re.compile(r"^#{1,6}\s+.*document\s+history", re.IGNORECASE),
            re.compile(
                r"^#{1,6}\s+(?:\d+[\.\d]*\s+)?changes\s+(?:since|from)\s+"
                r"(?:R\d|revision|the\s+previous|[PD]\d+R\d+|v\d)",
                re.IGNORECASE,
            ),
            re.compile(
                r"^#{1,6}\s+.*changes\s+in\s+this\s+(?:revision|paper)",
                re.IGNORECASE,
            ),
            re.compile(r"^#{1,6}\s+R\d+(?!\.\s*[A-Za-z])\b", re.IGNORECASE),
            re.compile(r"^#{1,6}\s+Revision\s+\d+", re.IGNORECASE),
            re.compile(
                r"^#{1,6}\s+(?:\d+[\.\d]*\s+)?changes\s+in\s+(?:R\d|revision\s+\d)",
                re.IGNORECASE,
            ),
        ]

        BOLD_REVISION_RES: list[re.Pattern[str]] = [
            re.compile(r"^\*\*\s*Revision\s+History\s*\*\*\s*$", re.IGNORECASE),
            re.compile(r"^\*\*\s*Changelog\s*\*\*\s*$", re.IGNORECASE),
            re.compile(r"^\*\*\s*Document\s+history\s*\*\*\s*$", re.IGNORECASE),
        ]

        REFERENCE_HEADING_RES: list[re.Pattern[str]] = [
            re.compile(
                r"^#{1,6}\s+(?:[\divxlcdm]+[\.\)]\s*)?\*?"
                r"(?:informative|normative)?\s*references\s*\*?"
                r"\s*[:{]?\s*(?:\{[^}]*\})?\s*$",
                re.IGNORECASE,
            ),
            re.compile(
                r"^#{1,6}\s+(?:[\divxlcdm]+[\.\)]\s*)?\*?"
                r"bibliography\*?\s*(?:\{[^}]*\})?\s*$",
                re.IGNORECASE,
            ),
        ]

        ACKNOWLEDGMENT_HEADING_RE = re.compile(
            r"^#{1,6}\s+(?:[\divxlcdm]+[\.\)]\s*)?\*?"
            r"acknowledg[e]?ments?\s*\*?"
            r"\s*[:{]?\s*(?:\{[^}]*\})?\s*$",
            re.IGNORECASE,
        )

        def is_revision_heading(
            line: str,
            overrides: set[str] | frozenset[str] = frozenset(),
        ) -> HeadingKind:
            """YES: heading and revision history. NO: heading, not revision.

            UNKNOWN: not a heading. Bold standalone lines count as headings.
            """
            stripped = line.lstrip()

            if HEADING_RE.match(stripped):
                for rx in REVISION_HEADING_RES:
                    if rx.match(stripped):
                        return HeadingKind.YES
                if overrides:
                    low = stripped.lower()
                    for token in overrides:
                        if token in low:
                            return HeadingKind.YES
                return HeadingKind.NO

            for rx in BOLD_REVISION_RES:
                if rx.match(stripped):
                    return HeadingKind.YES

            return HeadingKind.UNKNOWN

        def is_reference_heading(line: str) -> HeadingKind:
            """YES: heading that starts a references/bibliography section."""
            stripped = line.lstrip()
            if not HEADING_RE.match(stripped):
                return HeadingKind.UNKNOWN
            for rx in REFERENCE_HEADING_RES:
                if rx.match(stripped):
                    return HeadingKind.YES
            return HeadingKind.NO

        def is_acknowledgment_heading(line: str) -> HeadingKind:
            """YES: heading that starts an acknowledgment section."""
            stripped = line.lstrip()
            if not HEADING_RE.match(stripped):
                return HeadingKind.UNKNOWN
            if ACKNOWLEDGMENT_HEADING_RE.match(stripped):
                return HeadingKind.YES
            return HeadingKind.NO

        return HeadingKind, is_acknowledgment_heading, is_reference_heading, is_revision_heading

    HeadingKind, is_acknowledgment_heading, is_reference_heading, is_revision_heading = _module()
    return (
        HeadingKind,
        is_acknowledgment_heading,
        is_reference_heading,
        is_revision_heading,
    )


@app.cell
def _(
    HeadingKind,
    front_matter_end_index,
    is_acknowledgment_heading,
    is_reference_heading,
    is_revision_heading,
    re,
):
    "vendored: assay/blanking.py"

    def _module():
        PAPER_OVERRIDES: dict[str, set[str]] = {
            "P0260": {"old revision history"},
        }

        STEM_RE = re.compile(r"[PN]\d+", re.IGNORECASE)

        def get_overrides(paper_id: str | None) -> set[str]:
            if not paper_id:
                return set()
            m = STEM_RE.match(paper_id)
            if not m:
                return set()
            return PAPER_OVERRIDES.get(m.group(0).upper(), set())

        def blank_section(
            lines: list[str],
            classifier,
        ) -> None:
            """Blank all lines belonging to sections identified by *classifier*.

            Multi-pass: after exiting a block on a NO heading, scanning continues
            from PRE back to IN, so split or interrupted sections are all caught.
            """
            in_section = False
            for i in range(len(lines)):
                kind = classifier(lines[i])
                if in_section:
                    if kind is HeadingKind.NO:
                        in_section = False
                    else:
                        lines[i] = "\n"
                elif kind is HeadingKind.YES:
                    lines[i] = "\n"
                    in_section = True

        def blank_paper(source: str, paper_id: str | None = None) -> str:
            """Blank frontmatter, revision history, references, and acknowledgments.

            YAML frontmatter is always blanked. Non-prose sections (revision
            history, references, acknowledgments) are detected via tri-bool
            heading classifiers and blanked in independent passes so ordering
            within the document does not matter.
            """
            lines = source.splitlines(keepends=True)
            overrides = get_overrides(paper_id)

            # Pass 1: blank YAML frontmatter
            fm_end = front_matter_end_index(lines)
            for i in range(fm_end):
                lines[i] = "\n"

            # Pass 2: blank revision history (with paper-specific overrides)
            blank_section(lines, lambda line: is_revision_heading(line, overrides))

            # Pass 3: blank references
            blank_section(lines, is_reference_heading)

            # Pass 4: blank acknowledgments
            blank_section(lines, is_acknowledgment_heading)

            return "".join(lines)

        return blank_paper

    blank_paper = _module()
    return (blank_paper,)


@app.cell
def _(re):
    "vendored: assay/paper_routing/standardese.py"

    def _module():
        # Labels aligned with W1 hypothesis regex in hypotheses.py, the standard's
        # [structure.specifications] normative element list, plus common wording
        # elements from tomd golden fixtures.
        STANDARDESE_LABELS: tuple[str, ...] = (
            "Effects",
            "Returns",
            "Requires",
            "Remarks",
            "Throws",
            "Complexity",
            "Mandates",
            "Preconditions",
            "Postconditions",
            "Constraints",
            "Error conditions",
            "Recommended practice",
            "Hardware constraints",
            "Synchronization",
            "Expects",
            "Notes",
        )

        LABEL_ALT = "|".join(re.escape(label) for label in STANDARDESE_LABELS)

        # Line-start matcher: optional markdown emphasis (*Effects:* or **Effects**:),
        # case-insensitive.
        STANDARDESE_LINE_RE = re.compile(
            rf"^\s*(?:\*{{1,2}})?({LABEL_ALT})(?:\*{{1,2}})?\s*:",
            re.IGNORECASE,
        )

        # Unanchored matcher for label boundaries inside a sentence (post-split pass).
        # The negative lookbehind keeps a label from matching mid-word (e.g. "notes"
        # inside "footnotes:") now that the label set has grown to include compound
        # phrases such as "Hardware constraints".
        STANDARDESE_LABEL_RE = re.compile(
            rf"(?<![A-Za-z])(?:\*{{1,2}})?({LABEL_ALT})(?:\*{{1,2}})?\s*:",
            re.IGNORECASE,
        )

        def is_standardese_line(line: str) -> bool:
            """Return True when *line* begins with a normative element label."""
            return STANDARDESE_LINE_RE.match(line.strip()) is not None

        return STANDARDESE_LABEL_RE, is_standardese_line

    STANDARDESE_LABEL_RE, is_standardese_line = _module()
    return STANDARDESE_LABEL_RE, is_standardese_line


@app.cell
def _(HEADING_RE, dataclass, field, re):
    "vendored: assay/chunker.py"

    def _module():
        BOLD_SUBSECTION_RE = re.compile(r"^\*\*\d+(?:\.\d+)+\*\*")

        @dataclass
        class Section:
            """A leaf section produced by heading-based recursive chunking."""

            heading: str
            level: int
            start_line: int
            end_line: int
            char_count: int

        @dataclass
        class TreeSection:
            heading: str
            level: int
            start_line: int
            end_line: int
            char_count: int
            children: list["TreeSection"] = field(default_factory=list)

        def chunk_paper(
            source: str,
            *,
            max_chars: int = 6500,
        ) -> list[Section]:
            """Chunk paper markdown into leaf sections by heading structure.

            Builds a heading tree (with skip-level fallback and prefix
            recursion; see module docstring), flattens oversized nodes into
            children or bold-subsection splits, then coalesces small adjacent
            leaves.

            Parameters:
                source: Full paper markdown text (already blanked by the caller).
                max_chars: Maximum characters per chunk before recursing into
                    children. Sections exceeding this that have no heading-based
                    children will attempt a bold-subsection split.

            All size parameters are in characters. Use ``pipeline.tokens_to_chars()``
            to convert from a token budget.
            """
            lines = source.splitlines()
            headings = parse_headings(lines)

            if not headings:
                return [Section(
                    heading="(untitled)",
                    level=1,
                    start_line=1,
                    end_line=len(lines),
                    char_count=len(source),
                )]

            top_level = min(lv for _, lv, _ in headings)
            tree = build_tree(lines, headings, 0, len(lines), top_level - 1)
            leaves = flatten(tree, max_chars, lines)
            leaves = coalesce(leaves, max_chars, lines)

            return [
                Section(
                    heading=s.heading,
                    level=s.level,
                    start_line=s.start_line,
                    end_line=s.end_line,
                    char_count=s.char_count,
                )
                for s in leaves
            ]

        def parse_headings(lines: list[str]) -> list[tuple[int, int, str]]:
            """Extract (line_index, level, title) for all markdown headings."""
            headings: list[tuple[int, int, str]] = []
            for i, line in enumerate(lines):
                m = HEADING_RE.match(line)
                if m:
                    headings.append((i, len(m.group(1)), m.group(2).strip()))
            return headings

        def char_count(lines: list[str], start: int, end: int) -> int:
            """Character count for a line range (including newlines)."""
            return sum(len(lines[i]) + 1 for i in range(start, min(end, len(lines))))

        def build_tree(
            lines: list[str],
            headings: list[tuple[int, int, str]],
            start: int,
            end: int,
            parent_level: int,
        ) -> list[TreeSection]:
            """Build a heading tree for the line span ``[start, end)``.

            Direct children are headings at ``parent_level + 1``. If none exist,
            skip-level fallback selects the shallowest deeper heading in the
            span (see module docstring).

            Child headings on the span's opening line (``ln == start``) are
            included; the strict ``start < ln`` bound would drop an H1 at line 0
            when the root span begins there.

            When the span has leading prose before its first child heading, that
            prefix is emitted as its own section and ``build_tree`` is called
            again on the prefix with the same ``parent_level`` so nested
            skip-level headings (e.g. H4 under H2) still split inside the prefix.
            """
            children_hdgs = [
                (ln, lv, t)
                for ln, lv, t in headings
                if start <= ln < end and lv == parent_level + 1
            ]
            if not children_hdgs:
                deeper_hdgs = [
                    (ln, lv, t)
                    for ln, lv, t in headings
                    if start <= ln < end and lv > parent_level + 1
                ]
                if not deeper_hdgs:
                    return []
                child_level = min(lv for _, lv, _ in deeper_hdgs)
                children_hdgs = [
                    (ln, lv, t) for ln, lv, t in deeper_hdgs if lv == child_level
                ]

            sections: list[TreeSection] = []

            first_child_line = children_hdgs[0][0]
            prefix_chars = char_count(lines, start, first_child_line)
            non_blank_prefix = sum(1 for i in range(start, first_child_line) if lines[i].strip())
            if non_blank_prefix > 0 and prefix_chars > 0:
                prefix_heading = next(
                    (t for ln, lv, t in headings if ln == start),
                    "(preamble)",
                )
                sections.append(TreeSection(
                    heading=prefix_heading,
                    level=parent_level + 1,
                    start_line=start + 1,
                    end_line=first_child_line,
                    char_count=prefix_chars,
                    children=build_tree(
                        lines, headings, start, first_child_line, parent_level,
                    ),
                ))

            for idx, (ln, lv, title) in enumerate(children_hdgs):
                child_end = children_hdgs[idx + 1][0] if idx + 1 < len(children_hdgs) else end
                sec = TreeSection(
                    heading=title,
                    level=lv,
                    start_line=ln + 1,
                    end_line=child_end,
                    char_count=char_count(lines, ln, child_end),
                    children=build_tree(lines, headings, ln, child_end, lv),
                )
                sections.append(sec)
            return sections

        def flatten(
            sections: list[TreeSection], max_chars: int, lines: list[str]
        ) -> list[TreeSection]:
            """Flatten tree to leaves, recursing into children when oversized."""
            leaves: list[TreeSection] = []
            for sec in sections:
                if sec.char_count <= max_chars or not sec.children:
                    if sec.char_count > max_chars and not sec.children:
                        split = split_bold_subsections(sec, lines)
                        if split:
                            leaves.extend(split)
                            continue
                    leaves.append(TreeSection(
                        heading=sec.heading,
                        level=sec.level,
                        start_line=sec.start_line,
                        end_line=sec.end_line,
                        char_count=sec.char_count,
                        children=[],
                    ))
                else:
                    leaves.extend(flatten(sec.children, max_chars, lines))
            return leaves

        def coalesce(
            leaves: list[TreeSection], max_chars: int, lines: list[str]
        ) -> list[TreeSection]:
            """Fold small adjacent sections into predecessor if combined stays under max_chars."""
            if not leaves:
                return leaves

            result: list[TreeSection] = [TreeSection(
                heading=leaves[0].heading,
                level=leaves[0].level,
                start_line=leaves[0].start_line,
                end_line=leaves[0].end_line,
                char_count=leaves[0].char_count,
            )]
            for leaf in leaves[1:]:
                prev = result[-1]
                combined = char_count(lines, prev.start_line - 1, leaf.end_line)
                if combined <= max_chars:
                    prev.end_line = leaf.end_line
                    prev.char_count = combined
                    prev.heading = prev.heading + " + " + leaf.heading
                else:
                    result.append(TreeSection(
                        heading=leaf.heading,
                        level=leaf.level,
                        start_line=leaf.start_line,
                        end_line=leaf.end_line,
                        char_count=leaf.char_count,
                    ))
            return result

        def split_bold_subsections(
            sec: TreeSection, lines: list[str]
        ) -> list[TreeSection] | None:
            """Split a section on bold-numbered subsection patterns.

            Detects lines like **3.5.1** **Title** and splits there.
            Returns None if no such patterns found.
            """
            start_idx = sec.start_line - 1
            end_idx = sec.end_line

            split_points: list[tuple[int, str]] = []
            for i in range(start_idx + 1, end_idx):
                if i < len(lines) and BOLD_SUBSECTION_RE.match(lines[i]):
                    title = lines[i].replace("**", "").strip()
                    split_points.append((i, title))

            if not split_points:
                return None

            result: list[TreeSection] = []

            first_end = split_points[0][0]
            if first_end > start_idx + 1:
                result.append(TreeSection(
                    heading=sec.heading,
                    level=sec.level,
                    start_line=sec.start_line,
                    end_line=first_end,
                    char_count=char_count(lines, start_idx, first_end),
                    children=[],
                ))

            for idx, (ln, title) in enumerate(split_points):
                sub_end = split_points[idx + 1][0] if idx + 1 < len(split_points) else end_idx
                result.append(TreeSection(
                    heading=title,
                    level=sec.level + 1,
                    start_line=ln + 1,
                    end_line=sub_end,
                    char_count=char_count(lines, ln, sub_end),
                    children=[],
                ))

            return result if len(result) > 1 else None

        return chunk_paper

    chunk_paper = _module()
    return (chunk_paper,)


@app.cell
def _(dataclass, re):
    "vendored: assay/rag.py"

    def _module():
        HEADING_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
        CHARS_PER_TOKEN = 4

        @dataclass
        class RagChunk:
            paper_id: str
            text: str
            heading: str
            start_line: int
            end_line: int
            relationship: str

        def estimate_tokens(text: str) -> int:
            return len(text) // CHARS_PER_TOKEN

        def chunk_markdown(
            source: str,
            paper_id: str,
            relationship: str,
            *,
            max_tokens: int = 400,
        ) -> list[RagChunk]:
            """Split markdown into heading-aware chunks within token budget.

            Strategy: split on ## / ### headings as natural boundaries. If a
            section exceeds max_tokens, split on paragraph boundaries. No
            mechanical overlap - headings are prepended to sub-chunks for context.
            """
            lines = source.splitlines()
            max_chars = max_tokens * CHARS_PER_TOKEN

            sections: list[tuple[str, int, int]] = []
            heading_positions: list[tuple[int, str]] = []

            for i, line in enumerate(lines):
                m = HEADING_RE.match(line)
                if m:
                    heading_positions.append((i, m.group(2).strip()))

            if not heading_positions:
                heading_positions = [(0, "(untitled)")]

            for idx, (line_idx, heading) in enumerate(heading_positions):
                start = line_idx
                end = heading_positions[idx + 1][0] if idx + 1 < len(heading_positions) else len(lines)
                section_text = "\n".join(lines[start:end])
                sections.append((heading, start, end))

            chunks: list[RagChunk] = []

            for heading, start, end in sections:
                section_text = "\n".join(lines[start:end]).strip()
                if not section_text:
                    continue

                if estimate_tokens(section_text) <= max_tokens:
                    chunks.append(RagChunk(
                        paper_id=paper_id,
                        text=section_text,
                        heading=heading,
                        start_line=start + 1,
                        end_line=end,
                        relationship=relationship,
                    ))
                else:
                    body_start = start + 1 if start < end else start
                    body_text = "\n".join(lines[body_start:end]).strip()
                    paragraphs = re.split(r"\n\n+", body_text)

                    current_parts: list[str] = []
                    current_chars = 0
                    chunk_start_line = body_start + 1

                    for para in paragraphs:
                        para_chars = len(para)
                        if current_chars + para_chars > max_chars and current_parts:
                            chunk_text = f"## {heading}\n\n" + "\n\n".join(current_parts)
                            para_lines = chunk_text.count("\n") + 1
                            chunks.append(RagChunk(
                                paper_id=paper_id,
                                text=chunk_text,
                                heading=heading,
                                start_line=chunk_start_line,
                                end_line=chunk_start_line + para_lines - 1,
                                relationship=relationship,
                            ))
                            chunk_start_line += sum(p.count("\n") + 2 for p in current_parts)
                            current_parts = []
                            current_chars = 0

                        current_parts.append(para)
                        current_chars += para_chars

                    if current_parts:
                        chunk_text = f"## {heading}\n\n" + "\n\n".join(current_parts)
                        para_lines = chunk_text.count("\n") + 1
                        chunks.append(RagChunk(
                            paper_id=paper_id,
                            text=chunk_text,
                            heading=heading,
                            start_line=chunk_start_line,
                            end_line=end,
                            relationship=relationship,
                        ))

            return chunks

        return chunk_markdown, CHARS_PER_TOKEN

    chunk_markdown, RAG_CHARS_PER_TOKEN = _module()
    return RAG_CHARS_PER_TOKEN, chunk_markdown


@app.cell
def _(
    HEADING_RE,
    STANDARDESE_LABEL_RE,
    Segmenter,
    TextSpan,
    bisect,
    cast,
    dataclass,
    front_matter_end_index,
    is_standardese_line,
    re,
):
    "vendored: assay/paper_routing/split.py"

    def _module():
        FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})(\w*)")
        BNF_PRODUCTION_RE = re.compile(r"^[a-z][a-z0-9_-]*\s*:\s*.+")
        # Lowercase lhs tokens that look like BNF but are wording directives or prose.
        BNF_FALSE_POSITIVE_LHS = frozenset({"add", "modify", "insert", "strike", "delete"})
        # A genuine BNF right-hand side is made of grammar tokens (nonterminal names,
        # terminals, meta-symbols): no sentence-terminal punctuation and no
        # capitalized prose words. Lines that fail this look like informal lowercase
        # labels ("note:", "caveat:", "aside:") rather than grammar productions, and
        # would otherwise be swallowed whole instead of sentence-split.
        BNF_RHS_PROSE_RE = re.compile(r"[.!?](?:\s|$)|[A-Z]")
        SEGMENTER = Segmenter(language="en", clean=False, char_span=True)

        @dataclass(frozen=True)
        class RawSentence:
            """A split sentence with its starting line index (0-based)."""

            text: str
            start_line: int

        def split_sentences(paper_md: str) -> list[RawSentence]:
            """Split paper markdown into routable sentence units.

            Fenced code blocks and grammar-production lines are each kept as a
            single unit. Inline code stays attached to prose sentences.
            """
            lines = paper_md.splitlines()
            units: list[RawSentence] = []
            i = front_matter_end_index(lines)

            while i < len(lines):
                line = lines[i]

                if not line.strip():
                    i += 1
                    continue

                if HEADING_RE.match(line):
                    units.append(RawSentence(text=line.strip(), start_line=i))
                    i += 1
                    continue

                fence = FENCE_OPEN_RE.match(line.strip())
                if fence:
                    fence_char = fence.group(1)[0]
                    fence_len = len(fence.group(1))
                    block_lines = [line]
                    start = i
                    i += 1
                    while i < len(lines):
                        block_lines.append(lines[i])
                        stripped = lines[i].strip()
                        if stripped.startswith(fence_char * fence_len):
                            tail = stripped[fence_len:].strip()
                            if not tail or not tail[0].isalnum():
                                break
                        i += 1
                    units.append(RawSentence(text="\n".join(block_lines), start_line=start))
                    i += 1
                    continue

                if is_bnf_production_line(line):
                    units.append(RawSentence(text=line.strip(), start_line=i))
                    i += 1
                    continue

                prose_start = i
                prose_buf: list[str] = []
                while i < len(lines):
                    cur = lines[i]
                    if not cur.strip():
                        i += 1
                        break
                    if HEADING_RE.match(cur):
                        break
                    if FENCE_OPEN_RE.match(cur.strip()):
                        break
                    if is_bnf_production_line(cur):
                        break
                    prose_buf.append(cur)
                    i += 1
                if prose_buf:
                    units.extend(split_prose_units(prose_buf, prose_start))

            return [u for u in units if u.text.strip()]

        def is_bnf_production_line(line: str) -> bool:
            """Return True for lowercase BNF grammar productions, not Standardese labels."""
            stripped = line.strip()
            if is_standardese_line(stripped):
                return False
            match = BNF_PRODUCTION_RE.match(stripped)
            if match is None:
                return False
            lhs, _, rhs = stripped.partition(":")
            if lhs.strip() in BNF_FALSE_POSITIVE_LHS:
                return False
            if BNF_RHS_PROSE_RE.search(rhs.strip()):
                return False
            return True

        def prose_line_offsets(prose_lines: list[str]) -> list[int]:
            """Character offset of each prose line within a newline-joined paragraph."""
            if not prose_lines:
                return [0]
            offsets = [0]
            for line in prose_lines[:-1]:
                offsets.append(offsets[-1] + len(line) + 1)
            return offsets

        def offset_to_prose_line(line_offsets: list[int], char_offset: int) -> int:
            """Map a paragraph character offset to a 0-based index within *prose_lines*."""
            idx = bisect.bisect_right(line_offsets, char_offset) - 1
            return max(0, idx)

        NORMATIVE_SPLIT_SUFFIX_RE = re.compile(
            r"(?:add:\s*$|modify:\s*$)",
            re.IGNORECASE,
        )
        ATTACHED_LABEL_PREFIX_RE = re.compile(
            r"(?:"
            r"[-*]\s*$"  # markdown list marker
            r"|\(\w+\)\s*$"  # lettered (a), (b)
            r"|\d+(?:\.\d+)+\s*$"  # clause ref 1.2.3
            r"|\d+\.\s*$"  # numbered normative 1.
            r"|\b[A-Za-z]+\s*$"  # prose word before label (Release, with)
            r")",
            re.IGNORECASE,
        )

        def should_split_at_standardese(prefix: str) -> bool:
            """Return True when an internal Standardese label should start a new unit."""
            if ATTACHED_LABEL_PREFIX_RE.search(prefix):
                return False
            return NORMATIVE_SPLIT_SUFFIX_RE.search(prefix) is not None

        def standardese_split_points(text: str) -> list[int]:
            """Local offsets where *text* should split before an internal Standardese label."""
            points: list[int] = []
            for match in STANDARDESE_LABEL_RE.finditer(text):
                if match.start() == 0:
                    continue
                prefix = text[: match.start()]
                if not should_split_at_standardese(prefix):
                    continue
                points.append(match.start())
            return points

        def post_split_standardese(span: TextSpan) -> list[tuple[str, int]]:
            """Split a pySBD TextSpan on internal Standardese label boundaries."""
            text = span.sent
            base = span.start
            points = standardese_split_points(text)
            if not points:
                return [(text, base)]

            parts: list[tuple[str, int]] = []
            prev = 0
            for point in points:
                chunk = text[prev:point]
                if chunk.strip():
                    parts.append((chunk, base + prev))
                prev = point
            tail = text[prev:]
            if tail.strip():
                parts.append((tail, base + prev))
            return parts

        def split_prose_units(prose_lines: list[str], prose_start: int) -> list[RawSentence]:
            """Split prose lines into sentences with per-sentence source line attribution."""
            paragraph = "\n".join(prose_lines)
            line_offsets = prose_line_offsets(prose_lines)
            units: list[RawSentence] = []

            for raw_span in SEGMENTER.segment(paragraph):
                span = cast(TextSpan, raw_span)
                for part_text, abs_offset in post_split_standardese(span):
                    text = part_text.strip()
                    if not text:
                        continue
                    local_line = offset_to_prose_line(line_offsets, abs_offset)
                    units.append(RawSentence(text=text, start_line=prose_start + local_line))

            return units

        return split_sentences

    split_sentences = _module()
    return (split_sentences,)


@app.cell
def _():
    "vendored: assay/locs.py"

    def _module():
        def format_numbered_lines(paper_lines: list[str], start_line: int, end_line: int) -> str:
            """Format paper lines with line-number prefix for LLM input.

            Collapses runs of 2+ blank lines to a single sentinel.
            """
            result = []
            blank_run = 0
            for i in range(start_line - 1, min(end_line, len(paper_lines))):
                line = paper_lines[i]
                line_num = i + 1
                if not line.strip():
                    blank_run += 1
                    if blank_run <= 1:
                        result.append(f"{line_num:>6}|")
                else:
                    blank_run = 0
                    result.append(f"{line_num:>6}| {line}")
            return "\n".join(result)

        return format_numbered_lines

    format_numbered_lines = _module()
    return (format_numbered_lines,)


@app.cell
def _(Path, ast, mo, textwrap):
    def vendored_sources() -> dict[str, str]:
        """Return {origin: code} for every cell tagged with a 'vendored:' marker.

        Each vendored module lives in a ``_module()`` factory inside its cell;
        this returns the factory body, dedented, minus its final ``return``.
        """
        location = Path(str(mo.notebook_location()))
        path = location if location.is_file() else Path(__file__)
        text = path.read_text()
        lines = text.splitlines()
        out: dict[str, str] = {}
        for node in ast.parse(text).body:
            if not isinstance(node, ast.FunctionDef) or not node.body:
                continue
            first = node.body[0]
            if not (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
                and first.value.value.startswith("vendored: ")
            ):
                continue
            module_fn = next(
                (s for s in node.body if isinstance(s, ast.FunctionDef) and s.name == "_module"),
                None,
            )
            if module_fn is None:
                continue
            body = [s for s in module_fn.body if not isinstance(s, ast.Return)]
            if not body:
                continue
            code = "\n".join(lines[body[0].lineno - 1 : body[-1].end_lineno])
            out[first.value.value.removeprefix("vendored: ")] = textwrap.dedent(code)
        return out

    VENDORED = vendored_sources()
    return (VENDORED,)


if __name__ == "__main__":
    app.run()
