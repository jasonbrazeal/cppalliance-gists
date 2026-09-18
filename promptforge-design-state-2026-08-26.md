<!-- source: Vinnie huddle transcript, 2026-08-26 1:12 PM-2:11 PM PT (auto-generated) | context: none supplied -->

# PromptForge Design State - 2026-08-26

## Executive Summary

Vinnie walked Jason, Greg, and Glenn through the PromptForge design: the executor and credential-holding gateway that normalizes all models, the workshop IDE with step-through runs, caching, and replay, and modal agents (research, planning, run) with specialized tool sets. Three things moved: the RunPod will be locked down so the Alliance cloud gateway is the sole access point; the team discovered Agora's rhetoric table has never been populated — nothing calls store-rhetoric — and agreed to start the pipeline over with strict data-flow discipline; and Papergate's "vibes" verdicts will be replaced by an explicit, tested rubric that Jason owns. The central open question is how the closed, single-executable workshop accesses databases — Agora's assay-pipeline inputs — with no acceptable mechanism yet found. Several of Vinnie's newer ideas (the research database, UI-into-gateway integration, the writing-packet pipeline) were floated but remain unconfirmed.

## Settled Design Principles

### The PromptForge scribe

- **Design-discussion meetings are captured as transcripts, and Jason runs each transcript through the PromptForge scribe; the scribe must distinguish locked-down designs from open design points and track both so they can be revisited in later meetings.**
  - Basis: stated as the established workflow; no dissent
  - Speakers: Vinnie; Greg and Jason acknowledged

### Component map: executor and gateway

- **PromptForge consists of the executor (PromptForge core) and the PromptForge gateway; the gateway is the proxy for all inference and holds all credentials — RunPod, the Brave key, everything.**
  - Basis: stated as fact by the design authority; no dissent
  - Speakers: Vinnie

### Gateway normalization

- **The gateway normalizes all models — Anthropic, OpenAI, however a model works or presents thinking blocks — so every client speaks the same language and receives a normalized response; models differ even within the OpenAI interface.**
  - Basis: stated as the design; no dissent
  - Speakers: Vinnie
- **The gateway owns implementing every model dialect: when a new architecture ships with differently trained tool calls (e.g., Gemma 5, Qwen 4 [transcribed "Queen 4"]), a dialect is added in the gateway so clients never have to care.**
  - Basis: stated as an assigned responsibility; no dissent
  - Speakers: Vinnie
- **Normalization must accurately separate chats, thinking blocks, and tool calls, because key workshop features depend on that distinction.**
  - Basis: stated as a hard requirement; no dissent
  - Speakers: Vinnie
- **Finding: Cursor's chat transcripts cannot distinguish the model's replies from its thinking blocks without Cursor's database — lose the database and the thinking blocks are unrecoverable. This motivates the gateway's normalization requirement.**
  - Basis: undisputed implementation finding
  - Speakers: Vinnie
- **The gateway will provide statistics — tokens per second, time to first token, KV cache usage, KV cache prefix misses — passing through whatever each backend exposes; closed-weight models expose nothing and vLLM only limited information.**
  - Basis: stated as committed plan with an accepted backend constraint; no dissent
  - Speakers: Vinnie

### Workshop IDE: step-through, caching, optimization

- **The workshop is an IDE for building prompts: run a prompt, step through it, see what each step does, spot nondeterminism, and cache inputs/outputs so a run can be replayed or rerun from a later step.**
  - Basis: stated as the design; no dissent
  - Speakers: Vinnie
- **The workshop provides run-analysis and optimization tooling — where a run spends its time, KV-cache prefix management, and the optimum concurrency for the setup — with the LLM helping.**
  - Basis: stated as the design goal; no dissent
  - Speakers: Vinnie
- **Finding: prompt runs are long — some prompts take 3–4 hours, a full Staker run [transcribed] takes a long time, and Agora takes ~20 minutes to process a thread (Glenn's observation) — which is why step-level caching and replay matter.**
  - Basis: undisputed implementation finding
  - Speakers: Vinnie
- **Finding: stepping forward and back through a run is a valued capability that Jason's current command-line one-shot usage cannot provide.**
  - Basis: undisputed implementation finding
  - Speakers: Jason, Vinnie

### Plan mode and smart compaction

- **A plan mode for PromptForge prompts will be built: the LLM is given a system prompt that teaches it the PromptForge prompting language — the Lua, the substitution, the APIs — so it knows how to build prompts.**
  - Basis: stated as a definite build plan; no dissent
  - Speakers: Vinnie
- **The compaction algorithm summarizes the least important things and preserves the context it needs at full strength, so a long-running planning or debugging session never loses attention.**
  - Basis: stated as fact; no dissent
  - Speakers: Vinnie

### Modal agents with specialized tools

- **Workshop agents are modal: when you create an agent you choose its type — research agent, planning agent, or run agent — and that choice limits it to a focused, specialized set of tools. The accepted trade-off is losing the type-anything chat box of current agentic workflows.**
  - Basis: stated as the design with the trade-off acknowledged; no dissent
  - Speakers: Vinnie

### Run agent and the event-log trace

- **Running a prompt creates an event log — a trace of the entire program, every section and every turn — viewable in a window and exposed to the model as a tool; the run agent inspects the trace's data flows and verifies that the data going in and out aligns with the goals.**
  - Basis: stated as the design; no dissent
  - Speakers: Vinnie
- **Use a frontier (best) model for the helper agent that reviews the trace, but the prompt being run does not always need the best model.**
  - Basis: stated as guidance; no dissent
  - Speakers: Vinnie

### Prompt decomposition and model choice

- **A PromptForge prompt can be decomposed into smaller pieces that do not require heavy inference, which is what makes smaller models viable for the decomposed work.**
  - Basis: stated as fact; no dissent
  - Speakers: Vinnie; Greg acknowledged
- **Finding: smaller models are fast because a smaller token vocabulary means less memory allocated during prefill and a smaller vector during decode; Vinnie observed ~325 tokens per second from the small model under discussion [transcribed "Gemaphore"].**
  - Basis: undisputed implementation finding (mechanism plus measurement)
  - Speakers: Vinnie
- **Kimi K3 [transcribed "Kimmy K3"] is accepted for report writing: a very capable open-weight writer that allows big inference jobs without closed endpoints. Finding: Jason already uses Kimi K3 for all Papergate work and reports it works well.**
  - Basis: in-room agreement plus undisputed usage finding
  - Speakers: Vinnie, Jason; Greg approved

### Research tooling already built

- **Finding: the HTML-stripping step of the research pipeline is implemented in Rust — Vinnie has already written the library that cleans HTML/CSS out of fetched pages, formatting them as AI-concentrated markdown to save tokens.**
  - Basis: undisputed implementation finding
  - Speakers: Vinnie

### The workshop (name) and the MCP server

- **The component formerly called the workbench is now called the workshop.**
  - Basis: stated as fact; no dissent
  - Speakers: Vinnie
- **The MCP server lets an agentic harness such as Cursor or Claude run PromptForge prompts. Finding: this path double-pays time-to-first-token — once for the harness and once for PromptForge — and is clumsy enough that Vinnie dislikes it.**
  - Basis: stated as fact plus undisputed implementation finding
  - Speakers: Vinnie
- **Finding: in the IDE a run is deterministic — there is an actual button — but the IDE is in a very primitive state and none of it is done yet; it already supports talking to it and to the model, and an editor with a menu bar is planned.**
  - Basis: undisputed implementation findings; stated plan
  - Speakers: Vinnie; Greg affirmed

### Workshop UI architecture

- **The UI is two crates — a server and an app — delivered as a web app (TypeScript, HTML, CSS); the app compiles into an executable that opens the operating system's web view pointed at the internal server.**
  - Basis: stated as fact; corroborated by Jason
  - Speakers: Vinnie, Jason
- **Stack: Tauri [transcribed "tau. Rye"] for the app; the server uses Axum, Tokio [transcribed "Tokyo"], Rust Embed, whisper-rs for speech-to-text, and reqwest for HTTP; the UI uses Dockview and ESBuild, with the Mermaid UI [transcribed "MRM UI"] vendored in by copying its sources.**
  - Basis: undisputed implementation findings
  - Speakers: Vinnie
- **Delivering the UI as a web app in the OS web view on the desktop is accepted by the group as a good choice; the stated rationale is that Glenn, Greg, Jason — even Julio — can all work on it.**
  - Basis: in-room consensus
  - Speakers: Vinnie, Jason, Greg
- **Finding: the development workflow runs the app under a file watcher — editing TypeScript or HTML rebuilds the UI bundle, then shuts down and relaunches the program; it is smart enough to compile the UI.**
  - Basis: undisputed implementation finding
  - Speakers: Vinnie; Jason likened it to Django's dev server

### Gateway deployment: chaining and the RunPod lockdown

- **The gateway serves two use cases: running on a server ("for realsies") and running locally for yourself.**
  - Basis: stated as the design framing; no dissent
  - Speakers: Vinnie
- **Gateways can be chained: a local gateway forwards to the publicly accessible Alliance cloud gateway, which talks to RunPod's vLLM, which talks to the actual model — letting a pipeline mix models across steps, e.g., a local model for most steps and the remote RunPod DeepSeek for the final step.**
  - Basis: stated as the design; Jason questioned and then accepted
  - Speakers: Vinnie, Jason; Greg acknowledged
- **Finding: a local gateway can currently talk directly to RunPod via a RunPod profile — Jason has this set up, and Vinnie confirms it worked.**
  - Basis: undisputed implementation finding
  - Speakers: Jason, Vinnie
- **Decision: the RunPod will be locked down so no one can access it directly.**
  - Basis: stated as a decision by the design authority; Jason accepted ("That's a good gate then")
  - Speakers: Vinnie, Jason
- **Finding: vLLM has no robust round-robin or queuing support — under concurrent load requests are refused. The gateway owns load management instead: it is VRAM-aware for local models and supports configurable limits for remote models.**
  - Basis: undisputed implementation finding plus stated architectural relationship
  - Speakers: Vinnie; Jason acknowledged
- **For the gateway's limits to work, exactly one server may hold RunPod access — the Alliance server in the cloud; it proxies the cloud resources, and users connect to it to get queuing.**
  - Basis: stated as a requirement; Jason agreed ("Mhm. Makes sense.")
  - Speakers: Vinnie, Jason

### The gateway as shared infrastructure

- **The gateway is useful to applications beyond the workshop; the planned standalone mentographist [transcribed] will talk to it.**
  - Basis: stated as the gateway's role; no dissent
  - Speakers: Vinnie
- **Finding: the gateway exposes an API endpoint that downloads a requested Hugging Face model on the fly, and it can unload the old config and load a new one without taking the server down, allowing rapid iteration.**
  - Basis: undisputed implementation finding (existing capability)
  - Speakers: Vinnie

### Hermetically sealed sandbox

- **PromptForge is a hermetically sealed sandbox with no real access to the user's system; the only way to grant access is to give it tools — and a store that can touch the system (fragment; Vinnie broke off due to illness).**
  - Basis: stated as the current design; no dissent
  - Speakers: Vinnie

### The workshop is a closed app

- **The workshop is a closed app: users must not have to add crates to make it understand their environment; the goal is one executable everyone can use — including people testing the prompt-ified assay pipeline writing into SQLite or Postgres.**
  - Basis: stated as a firm requirement; Greg assented
  - Speakers: Vinnie, Greg
- **Finding (Rust linking): the linker bundles all compiled machine code and resolves all names into a fixed executable; once produced, no code can be added — a program can talk to a database only if the database code was compiled in.**
  - Basis: implementation finding explained by Vinnie and explicitly accepted by Jason
  - Speakers: Vinnie, Jason
- **PromptForge must not compile in everything anyone will ever want; the workshop must stay closed while remaining augmentable with features without recompiling or rebuilding.**
  - Basis: stated as the design goal; no dissent
  - Speakers: Vinnie
- **Rejected: exporting a Postgres-speaking tool into the workshop, because the tool would have to be compiled in — meaning every company tool anyone wants would have to be compiled into the app. "That doesn't work."**
  - Basis: rejected outright by the design authority; undefended
  - Speakers: Vinnie
- **Finding: the other PromptForge crates — at minimum the gateway core — are not yet part of the workshop app but will be.**
  - Basis: confirmed by Vinnie in answer to Greg
  - Speakers: Greg, Vinnie

### Database integration today: wrappers and JSON

- **Finding: Papergate's database integration is done in the wrapper and is basically working, though it is unclear how much that buys.**
  - Basis: undisputed implementation finding
  - Speakers: Vinnie
- **Finding (Paperflow precedent): Paperflow builds the thread for Agora and outputs a JSON file; the website's ingest side maps that JSON onto database rows across tables — the thread, the community, the comments, the personas.**
  - Basis: reported as how the system actually works; Vinnie probed and accepted the details
  - Speakers: Glenn, Vinnie
- **A prompt must remain debuggable on a developer's own computer; an approach that requires standing up an HTTP server with an API endpoint in order to debug is unacceptable.**
  - Basis: stated as a rule; Glenn, whose proposal it undercut, conceded the point
  - Speakers: Vinnie, Glenn
- **Agora requires a database with the assay-pipeline evidence baked in; running Agora's prompt in the workshop requires a way for the workshop to read those elements of the database.**
  - Basis: stated as Agora's requirement; unchallenged
  - Speakers: Vinnie

### Agora: the empty rhetoric table and the start-over decision

- **Agora's pipeline is supposed to collect rhetoric — the political statements — and that collection is the main thing Agora wants.**
  - Basis: stated as the pipeline's purpose; no dissent
  - Speakers: Vinnie
- **Finding: the whole-paper analysis dimensions (plausibility, substance, technical accuracy) are prone to hallucination, and whole-paper analysis is difficult. Rejected: thinking budgets — if an insufficient budget makes the analysis worse, the results are unpublishable.**
  - Basis: undisputed implementation finding; rejection undefended
  - Speakers: Vinnie
- **Finding: everything completed so far is in paper flow.**
  - Basis: Glenn's answer to whether Agora is up to date and merged; accepted
  - Speakers: Glenn
- **Finding: nobody on the team understands how the Agora package works — not even Vinnie, its author — and Glenn did the work without enough knowledge of the entire pipeline; this is why Vinnie is not confident about shipping Agora.**
  - Basis: asserted by Vinnie, confirmed by Greg, admitted by Glenn
  - Speakers: Vinnie, Greg, Glenn
- **Finding: the Agora pipeline still contains the dissect-markers and get-rhetoric steps (located in code; Greg confirms they exist). Paper Store owns the persistence API; store-rhetoric is the call that saves rhetoric.**
  - Basis: undisputed implementation findings from the in-room code trace
  - Speakers: Vinnie, Greg
- **Key finding: nothing calls store-rhetoric — the rhetoric table exists but is empty and unused; Agora relies on a table that has never had anything added to it. Anything in Agora that depends on rhetoric is therefore hallucinated, because the input is not there; this is the canonical example of an inference unsupported by its inputs.**
  - Basis: discovered in the in-room code trace; undisputed (Glenn agreed)
  - Speakers: Vinnie, Glenn
- **Decision: start over on the Agora pipeline rather than continue building on the existing implementation.**
  - Basis: proposed by Vinnie; explicit agreement from Glenn and Greg
  - Speakers: Vinnie, Glenn, Greg
- **You cannot build pipelines without understanding every single piece of data that goes in and what it is composed of.**
  - Basis: stated as a general principle alongside the start-over decision; no dissent
  - Speakers: Vinnie
- **Finding: the generated threads look good — good enough to almost fool Vinnie — but looking good does not establish that a thread's claims are correct.**
  - Basis: undisputed implementation finding
  - Speakers: Vinnie; Jason ("Looks great") is the kind of reaction being warned against
- **Constraint: threads will be generated for every paper in the mailing going back roughly three years, and the papers' named authors will read them; a single publicly posted hallucinated thread — one that says a paper makes a claim it does not make — would destroy the whole operation. Generated threads must never fabricate a paper's claims.**
  - Basis: stated as the driving constraint; no dissent
  - Speakers: Vinnie
- **The pipeline must be absolutely disciplined: at every step it must be provable that the AI's conclusions are the result of inference grounded in unambiguous signals.**
  - Basis: stated as a requirement following from the hallucination-risk constraint; no dissent
  - Speakers: Vinnie

### Papergate verdicts: vibes today, rubric tomorrow

- **Finding: Papergate's verdict is vibes — it has no calibration and no rubric distinguishing weak from average. Finding: the verdict changes from run to run, so a locally produced verdict cannot be meaningfully compared with what is on stage.**
  - Basis: asserted by Vinnie and confirmed by Greg (who observes the nondeterminism directly); Jason agreed
  - Speakers: Vinnie, Greg, Jason
- **Papergate is simple enough that the team can get a verdict they can trust.**
  - Basis: Vinnie asked for agreement; Greg explicitly agreed
  - Speakers: Vinnie, Greg
- **Finding: Papergate currently runs the "little" prompt; a separate "fancy" prompt exists that Vinnie needs to retire.**
  - Basis: undisputed implementation finding
  - Speakers: Vinnie; Greg confirmed he knows the little prompt
- **Finding: the Extract step asks the model for 7 different things at once; that pressure makes the model take shortcuts and start seeing things that are not there in order to satisfy the human.**
  - Basis: undisputed implementation finding (observed model behavior)
  - Speakers: Vinnie
- **Finding: the Papergate deployment on stage.WG21.org assigns a strong verdict with strong evidence to non-proposal papers — e.g., the reader's-guide paper "A Reader's Guide to the August 26, 2016 mailing" — which should receive no verdict because they contain no proposal and hence no evidence.**
  - Basis: reported by Jason; Vinnie confirmed it is a real problem
  - Speakers: Jason, Vinnie
- **Decision: Papergate must be fixed to be deterministic. A rubric will define each verdict level with concrete criteria — for example, strong = 5–7 sentences of evidence, adequate = 3–5, weak = 1–2 (evidence-sentence counting is the suggested criterion; most papers provide zero). Jason owns the rubric, with Glenn available to help.**
  - Basis: directed by Vinnie and Greg; Jason accepted ("Sure.")
  - Speakers: Vinnie, Greg, Jason
- **The rubric must be validated before it is proposed: run it on a set of papers, refine it until satisfied, ask a frontier model whether the rubric is ambiguous and whether the pipeline provides the data it needs to generate a real answer rather than vibes — then propose it to the group with the work shown.**
  - Basis: directed by Vinnie; Jason accepted ("I can do that. OK.")
  - Speakers: Vinnie, Jason

### Prompt-engineering discipline

- **Method: have the LLM analyze the data flow; build the prompt one step at a time; make sure the prompt and the input it receives are aligned and unambiguous; then test that one prompt over and over — on the order of 100 test cases — and use prompt engineering to shape it.**
  - Basis: stated as established practice ("that's how you do it"); no dissent
  - Speakers: Vinnie
- **Prompts must be matched to the model: prompt engineering is model-specific and changing the model changes results, so a prompt's wording must be re-tuned — kept under adjustment until it is right — when moving to a smaller open-weight model.**
  - Basis: stated as how the work goes in practice; no dissent
  - Speakers: Vinnie
- **Never ask a pipeline step to render a judgment it is not capable of rendering because its inputs do not provide the data.**
  - Basis: stated as a standing rule from half a year of prompt-building; no dissent
  - Speakers: Vinnie
- **Finding: different LLMs do not differ very much in practice — they share training data and even verbal tics (they all say "load bearing" and gloss every paragraph the same way, even the Chinese models) — which limits how much diversity switching models can buy for review.**
  - Basis: Glenn stated the shared-training-data point; Vinnie agreed ("in a sense") and expanded
  - Speakers: Glenn, Vinnie
- **What catches a missing field is tooling that lets you look at what data is flowing into a pipeline section — not an adversarial model. Finding: the pipeline Vinnie built has nothing in terms of debugging — you cannot step, replay, or examine — and step-by-step visibility tooling is a stated goal of the PromptForge workshop.**
  - Basis: asserted by Vinnie; unchallenged; reported by the pipeline's own builder
  - Speakers: Vinnie

## Open Design Questions

### The research database (singleton agent, per-user store, RAG)

- **Status:** raised, unconfirmed
- **Options:** as proposed: one singleton research agent; everything it gathers flows into a central per-user database independent of project, with a configurable cap (e.g., 10 GB); pages cached as HTML/CSS-stripped markdown; repeat runs reuse the cache without refetching; least-recently-used eviction deletes the oldest material at the cap; the whole database is RAG-indexed and exposed to every agent through a semantic-search tool — so the workflow becomes "bring material into the local database via the research agent, then every agent can see it" instead of asking the model to do its own internet research.
- **Positions:** Vinnie proposed it and asked "What do you think about that?"; Greg's only response was "Interesting."
- **Blocker:** no confirmation or decision in the room.

### Workshop memory: the document type is a database

- **Status:** raised, unconfirmed
- **Options:** the workshop's document type is a database that remembers everything the user did — a plan-mode chat is remembered forever; fetched pages are kept with no usefulness decision filtering what stays; storage is organized as multiple databases.
- **Positions:** Vinnie stated it as his idea for the workshop, answering Greg's question about whether every fetched page stays.
- **Blocker:** stated as design intent ("my idea"), never confirmed by the group.

### Skillgate built into the workshop

- **Status:** raised, unconfirmed
- **Options:** the chat must be saved for Skillgate; the workshop will have a small version of Skillgate built in, which keeps track of the user as they code and extracts principles as they go.
- **Positions:** Vinnie stated it as a want seeking agreement ("this is what we want for Skillgate, right?").
- **Blocker:** no explicit confirmation in the room.

### A small model for Papergate

- **Status:** raised, unconfirmed
- **Options:** use a small model [transcribed "Gemaphore"] to do Papergate — "maybe we could... that might work."
- **Positions:** Vinnie floated it tentatively as "the whole point of PromptForge."
- **Blocker:** framed as a maybe; no decision recorded.

### The writing-packet pipeline

- **Status:** raised, unconfirmed
- **Options:** collect evidence using small, fast models; build a writing packet containing all the facts, stated neutrally with no register — plain statements only; present the packet to a fresh subcontext on a frontier model and ask it to write the report.
- **Positions:** Vinnie proposed it ("maybe you make a pipeline...").
- **Blocker:** tentative proposal; no decision recorded.

### Does PromptForge need its own harness?

- **Status:** newly raised
- **Options:** a PromptForge harness so that running a prompt would not double-pay time-to-first-token.
- **Positions:** Greg raised it half-jokingly ("I'm mostly joking, but").
- **Blocker:** never answered in the room.

### Why is the app not using muda [transcribed]?

- **Status:** newly raised
- **Options:** adopt muda, or keep the current choice.
- **Positions:** Vinnie openly questioned why muda is not in use.
- **Blocker:** the question was never answered.

### Integrating the UI into the gateway

- **Status:** raised, unconfirmed
- **Options:** combine the UI into the gateway, or at least make it an optional feature of compilation / an optional build package — because every time you run the workshop you want the gateway anyway. Components as described: the desktop app launches the gateway and connects to itself with no configuration hassle and no keys; closing the window puts it in the tray and leaves the gateway running for other apps; the second mode installs the gateway as a service once a stable version exists, for all-you-can-eat local models; a workshop window would control the gateway and switch profiles visually.
- **Positions:** Vinnie favors it ("I'm thinking of integrating the UI into the gateway... and here's why"); Greg: "Very cool."
- **Blocker:** framed as in-progress thinking, not a decision.

### Running different sections in parallel

- **Status:** newly raised
- **Options:** fan-out exists and runs the same section multiple times, but there is no method of running different sections in parallel; such a method is needed.
- **Positions:** Vinnie states it is needed, is "not a big deal," and that he has a plan for it.
- **Blocker:** not yet implemented.

### Database access for the closed workshop (Agora's inputs)

- **Status:** newly raised — the central open question of the discussion
- **Options:** (a) compile a Postgres-speaking tool into the workshop — rejected (it means compiling in every company tool); (b) a general Postgres tool/crate — needs an abstraction for local testing without a database, "things start to get very messy," and Vinnie holds that Postgres access is a WG21.org-specific customization that breaks the encapsulation of generic PromptForge (Greg concedes the point while noting Postgres itself is obviously not website-specific); (c) the prompt outputs a file of JSON objects to be inserted, and a caller-side wrapper ingests them — the Paperflow precedent, a convenient sidestep for insert-only prompts; (d) a generic HTTP-call tool where the prompt supplies endpoint, method, and data — Glenn's stream-of-consciousness, undercut by the local-debuggability rule (Glenn conceded); (e) database URLs with raw SQL — Glenn; Jason objected that something still has to link and run the queries; (f) database capabilities exposed through Lua — Jason; feasible, but the capability still has to be linked into the executable; (g) SQLite for development vs Postgres for production — acknowledged valid but set aside as "the least interesting" part.
- **Positions:** Vinnie frames the problem and the constraints and rejects or problematizes each option; Greg favors a promptforge-postgres crate; Glenn favors JSON-out and HTTP; Jason favors Lua.
- **Blocker:** the linking constraint (a fixed executable can only use compiled-in capabilities) combined with the closed-app rule (one executable for everyone) and the augmentability rule (no recompiling to add features). Vinnie: "There's no good answer right now, and everybody needs to think about it" — the team is to study the design documents and Rust linking, then reconsider where Agora gets its inputs when run in the workshop.

### Splitting the Extract step

- **Status:** raised, unconfirmed
- **Options:** chunk the paper as is already done and give each of the 7 extraction items its own subagent, which would allow a smaller, very fast model.
- **Positions:** Vinnie proposed it tentatively ("we could probably").
- **Blocker:** no decision recorded.

### An evaluation baseline for verdicts

- **Status:** newly raised
- **Options:** a human-authored list of papers with their correct verdicts to check Papergate's output against.
- **Positions:** Jason asked how to evaluate changes to these tools and whether such a list exists.
- **Blocker:** no one answered; no such list is known to exist.

### Jason's PromptForge Papergate fix

- **Status:** raised, unconfirmed
- **Options:** Jason's local version of Papergate, which runs through PromptForge, returned "verdict: none" on the reader's-guide paper that stage mislabels.
- **Positions:** Jason reports the fix but notes he has checked only 3 or 4 papers and wants to evaluate on more.
- **Blocker:** sample too small to confirm; subsumed by the rubric work he now owns.

### What the assay database actually contains

- **Status:** newly raised
- **Options:** unknown — what a database row looks like and what a "claim" looks like are open questions; Vinnie does not know, and Greg recalls only vaguely.
- **Positions:** Glenn is to pick one preferably small paper, dig up its assay data, and produce a markdown report of the database contents so the group can see what is in there.
- **Blocker:** the contents are unknown until Glenn's report.

## Contested

### Adversarial review for the Agora rebuild

- **Position A (Glenn):** use adversarial reviews in which a different LLM than the one that produced the output checks it — different models checking things and arguing amongst themselves — on the hypothesis that this improves results; a fresh sub-agent still shares the same training data, which is the only thing that gives him pause about Vinnie's alternative.
- **Position B (Vinnie):** the idea of different models is "very weak"; the way to get a quote-unquote different model is a fresh sub-agent, which has no bias; the effective adversarial review is the human trying the prompt on a bunch of different inputs to make sure it is roughly correct, then checking subsequent steps to make sure each inference is supported by its inputs.
- **Authority:** Vinnie — transcript-established design authority (he presents the design, directs the work, and assigns tasks; no one disputes his authority in the room).
- **Resolution path:** Vinnie's fresh-sub-agent plus human multi-input testing method governs the rebuild; Glenn's shared-training-data concern stands as the noted point of tension if model diversity is later shown to matter.

## Provenance

All locations are in the 2026-08-26 Vinnie huddle transcript (1:12 PM-2:11 PM PT).

- PromptForge scribe (Settled): Vinnie 2:40-3:05; acknowledged Greg 3:22, Jason 3:22
- Component map / credentials (Settled): Vinnie 3:41-4:01
- Gateway normalization, dialects, chat/thinking/tool-call separation, Cursor finding (Settled): Vinnie 4:01, 23:38-24:52; Greg's pipeline experience referenced 23:58
- Gateway statistics and backend constraints (Settled): Vinnie 25:18
- Workshop IDE capabilities, long-run finding, optimization tooling (Settled): Vinnie 4:35-5:12; execution-control finding Jason 17:27-17:46
- Plan mode, compaction, modal agents (Settled): Vinnie 5:49-6:52
- Run agent, event log, helper verification, frontier-model rule (Settled): Vinnie 10:14-10:52
- Decomposition principle, small-model speed finding (Settled): Vinnie 11:19-11:45; Greg acknowledged 11:27
- Kimi K3 for writing (Settled): Vinnie 12:02-12:32; Jason 12:48-12:53; Greg 12:48
- Rust HTML-cleaning library (Settled): Vinnie 7:50
- Workshop rename, MCP server, double-TTFT finding, IDE state (Settled): Vinnie 13:22-14:57; Greg 14:39-14:50
- UI architecture, stack, group acceptance, file-watcher workflow (Settled): Vinnie 15:14-20:17; Jason 17:27, 19:06-19:16, 20:03; Greg 18:51, 19:01
- Gateway use cases, chaining, direct-RunPod finding, lockdown decision, vLLM finding, single-server requirement (Settled): Vinnie 21:07-23:38; Jason 22:18-22:46, 23:36; Greg 21:57
- Gateway as shared infrastructure, Hugging Face endpoint, hot config reload (Settled): Vinnie 26:38-26:54
- Sandbox (Settled): Vinnie 28:07-28:26
- Closed-app rule, linking finding, augmentability rule, rejected compile-in option, crates-to-come (Settled): Vinnie 29:30-30:04, 35:04-37:41; Greg 29:53-30:06, 35:17; Jason 36:46-37:22
- Papergate wrapper finding, Paperflow JSON precedent, debuggability rule, Agora's database requirement (Settled): Vinnie 28:55, 33:31-34:16, 38:05; Glenn 31:49-33:25, 34:26
- Agora rhetoric purpose, analysis findings, paper-flow finding, nobody-understands finding, get-rhetoric/store-rhetoric trace, empty-table finding, start-over decision, data-understanding principle, looks-good finding, hallucination constraint, discipline principle (Settled): Vinnie 39:48-48:03; Glenn 41:09, 45:42, 46:54-46:59; Greg 42:10, 44:21, 46:59; Jason 47:18
- Papergate vibes finding, nondeterminism finding, simple-enough agreement, little/fancy prompts, Extract 7-things finding (Settled): Vinnie 48:26-50:02; Greg 48:46-48:52, 49:24-49:34
- Stage misclassification finding, determinism/rubric decision, rubric validation process (Settled): Jason 54:49-55:47, 57:05, 57:58-58:13; Vinnie 55:12, 57:02-58:12; Greg 56:37-56:42, 57:06
- Prompt-engineering method, model-specific tuning, unsupported-judgment rule, models-don't-differ finding, tooling-over-adversarial-models (Settled): Vinnie 51:19-54:19; Glenn 51:09
- Research database (Open): Vinnie 7:08-9:07; Greg 9:22-9:27
- Workshop memory (Open): Vinnie 9:38-9:54; Greg 9:27
- Skillgate built-in (Open): Vinnie 9:54-10:14
- Small model for Papergate (Open): Vinnie 10:52
- Writing-packet pipeline (Open): Vinnie 11:28-12:02
- PromptForge harness (Open): Greg 14:18-14:27
- muda (Open): Vinnie 17:47
- UI-into-gateway integration (Open): Vinnie 20:17-20:35, 25:55-27:28; Greg 27:43
- Parallel sections (Open): Vinnie 27:45-28:07
- Database access for the closed workshop (Open): Vinnie 28:55-38:26; Greg 29:49-31:16; Glenn 31:49-36:02; Jason 34:40-36:19
- Extract split (Open): Vinnie 50:02
- Evaluation baseline (Open): Jason 54:28-54:49
- Jason's Papergate fix (Open): Jason 55:15-55:38
- Assay database contents (Open): Vinnie 58:33-59:17; Glenn 58:43-59:09; Greg 59:15
- Adversarial review (Contested): Glenn 50:30-51:09; Vinnie 50:57-52:59

*2026-09-17 18:31 - kimi-k3*
