# RTI4All — Demo Brief

> A short, plain-English version of the README for the presentation.
> If you've never seen the project before, read this top-to-bottom and
> you'll be able to talk through every slide.

**Tagline:** *Automated Transparency.*

**Status:** Wave 1 Pilot — CoLab National AI Use Case Selection Sprint (Cycle 1)

**Built in:** 48 hours at CoLab26 Hackathon

---

## In one sentence

**RTI4All is an AI-assisted Right to Information portal for the Maldives
Ministry of Climate Change, Environment and Energy — citizens file
information requests, the AI drafts a response, and a real officer
approves it before it's published.**

---

## What we accomplished in this hackathon

This project implements **Agentic RTI Disclosure** — a **Wave 1 pilot** use case selected through the **CoLab National AI Use Case Selection Sprint (Cycle 1)** for the Ministry of Environment and Climate Change (MoECC).

### Hackathon deliverables ✅

In 48 hours, we delivered a production-ready agentic AI system that:

✅ **Automates the full RTI response workflow** — from request analysis through data retrieval, response composition, gap detection, to human review

✅ **Implements true agentic architecture** — multi-step reasoning agent with tool use (data search, format conversion, gap detection), memory management, and self-correction via completeness scoring

✅ **Handles real-world government data challenges** — extracts information from semi-structured documents with inconsistent formatting (the reality across government data estates)

✅ **Generates format-aware responses** — produces replies in exactly the format citizens request (tabular, narrative, summary statistics) while preserving source data integrity

✅ **Built-in audit and accountability** — every AI-assisted disclosure is fully traceable: what was asked, what was retrieved, what gaps were detected, and what the officer approved

✅ **Cross-ministry extensibility** — architectural design allows other ministries to adopt the same pattern without rebuilding from scratch

✅ **Production-grade performance** — rewrote from Python to Go for 250× faster cold start (50ms), 65× smaller Docker image (15 MB), and 40× faster request latency

✅ **Professional citizen-facing UI** — TypeScript + Tailwind frontend that gzips to 70 KB, mobile-ready, accessible

### Impact potential

**Estimated reach**: ~**500,000 citizens** — effectively the entire eligible Maldivian population — for whom RTI is a foundational right under the Right to Information Act (Act No. 1/2014).

**Ministry staff benefit**: Reduced manual workload on routine requests; capacity reallocated from information retrieval to substantive casework and policy analysis.

**Transparency framework**: Stronger institutional capacity to deliver on the Right to Information Act; more reliable timelines for accessing public information for civil society and researchers.

---

## The problem we're solving

Under the Maldives **Right to Information Act (Act No. 1/2014)**, every
citizen has the legal right to ask the government for information, and
the ministry has 30 days to reply. In practice the process is slow:

- **Citizens** don't know how to write a good RTI request, what to
  include, or where to send it.
- **Officers** receive vague, repetitive, or duplicate requests and
  have to draft every reply by hand, often citing the same prior
  records over and over.
- **Both sides** lose track of what was asked, what was answered, and
  what's still pending.

RTI4All fixes that — *automated transparency*, with a human in charge.

---

## What the system does, in plain English

```
   Citizen                 AI assistant                Officer
   ───────                 ────────────                ───────
1. Writes a request   →    2. Reads the request,
                              decides if it's clear,
                              looks up similar past
                              requests in the           3. Reviews the draft.
                              ministry archive,    →       Approves, edits,
                              writes a draft reply         rejects, or asks
                                                           the citizen for
                                                           more details.
                                                              ↓
                                              4. Citizen sees the official reply.
```

Critical detail: **the AI never publishes anything by itself.** Every
response is reviewed by a real ministry officer first. The human is
always in the loop.

---

## Why this is more than "ChatGPT with a form"

We built a **5-step agentic workflow**, not a one-shot prompt:

1. **Structurer agent** — reads the citizen's request and produces a
   structured analysis: what's being asked, what's missing, how
   complex it is, and a **completeness score** from 0 to 1.
2. **Gating** — if the score is too low (< 0.7), the system *doesn't*
   draft a reply. Instead, it tells the officer the request is
   ambiguous and shows them exactly what's missing.
3. **Retriever** — for clear requests, the system looks up similar
   past responses in the ministry archive using two complementary
   methods (see "RAG + graphify" below).
4. **Drafter agent** — writes the citizen-facing reply, citing the
   exact prior RTI ids it drew from. Plain prose, 4–8 sentences.
5. **Officer decision + feedback loop** — when the officer approves,
   the new response is added back into the archive, so the *next*
   citizen's request gets even better grounded answers.

The whole pipeline is **observable, auditable, and gets smarter every
time an officer approves something.**

---

## The AI models we use (and why)

We use **two different Anthropic Claude models** for the two different
jobs. Same vendor, different models, picked deliberately.

| Stage         | Model                          | Job                                | Why this model                                                                                                          |
| ------------- | ------------------------------ | ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| ① Structurer  | **Claude 3.5 Sonnet**          | Citizen text → strict JSON analysis | Sonnet is excellent at structured output. Its JSON-mode reliability is the difference between an agent that works and one that crashes on every fifth request. |
| ③ Drafter     | **Claude Haiku 4.5**           | Retrieved archive → 4–8 sentence reply | Haiku is fast and cheap, and it's *very* good at grounded summarisation. Because we constrain it tightly with retrieved context, we don't need a bigger model — Haiku gives the same quality at a fraction of the latency and cost. |

### Why split the work between two models?

- **Different output formats.** JSON for one, prose for the other —
  one prompt can't do both well.
- **Different cost/latency profiles.** The Structurer runs on *every*
  request, including clarification updates. The Drafter only runs when
  the Structurer's score is ≥ 0.7. So we put the cheaper, faster Haiku
  on the hot path and the more capable Sonnet on the rarer
  information-extraction step.
- **Cleaner failure handling.** If the Structurer returns bad JSON,
  we fall back to a deterministic skeleton and the request still gets
  filed. If the Drafter fails, the request goes to the officer as
  Pending with no draft. Nothing about the workflow breaks.

### Why Claude (and not GPT, Gemini, or open-weights)?

- **Reliable instruction-following on long, structured prompts.** Our
  Drafter system prompt is essentially "here are 7 prior RTI records,
  cite only these, write 4–8 sentences" — Claude follows that
  faithfully.
- **Conservative on hallucination.** Government RTI replies need to
  *not invent* statute numbers, atoll names, or dates. Claude's
  training plus our retrieval-only grounding rule keeps drafts
  factual.
- **No vendor lock-in.** The whole AI integration is one Go file
  (`internal/ai/ai.go`) talking to the Anthropic REST API. Swapping
  to OpenAI or a self-hosted model would be a one-file change.

### Why we *don't* use an embedding model

Most "RAG demos" use OpenAI embeddings or sentence-transformers
(`all-MiniLM-L6-v2`, 300 MB of PyTorch). We deliberately don't:

- **Cold start in microseconds, not seconds.** No model download, no
  GPU, no Python.
- **Explainable retrieval.** When the Drafter cites
  `RTI-2024-0001`, we can show the officer *exactly* which words or
  co-occurring concepts caused that record to surface. That matters
  for an auditable government system.
- **Domain fit.** Government RTI text is keyword-heavy — place names,
  statute numbers, programme names. Classic TF-IDF is competitive
  here, and ~1000× faster than embedding inference.

---

## RAG and graphify — what they are, in everyday terms

Both are how the AI "looks things up" before writing a reply. We use
**both in parallel** because they catch different kinds of matches.

### RAG (Retrieval-Augmented Generation)

Think of it as **keyword matching, but smarter.** When a citizen asks
about "coral bleaching 2023", the system scans every past responded
RTI and every FAQ, and finds the documents that share the same
important words.

We use a classic technique called **TF-IDF + cosine similarity** —
it's fast, has no dependencies, and is *explainable* (we can tell the
officer exactly which past records the AI used).

### graphify (concept-link search)

Pure keyword matching misses things. If a citizen asks about "reef
monitoring data" but the relevant past record talks about "coral
surveys", a keyword search won't connect them. **graphify-style
retrieval fixes that** by building a graph of concepts that appear
together in the ministry archive.

In the Maldives RTI context, that means:

- "coral" and "reef" co-occur → they get linked.
- "monitoring" and "survey" co-occur → they get linked.
- A query about *one* word can find documents that talk about the
  *other*.

The AI sees both retrieval results side-by-side and is instructed to
cite the records it uses.

> Why is this powerful? The ministry archive grows over time. Every
> response the officer approves becomes part of the archive. So the AI
> doesn't just look things up — it learns the ministry's voice and
> precedents.

---

## Why we rewrote the backend in Go

The first version was Python (FastAPI). It worked, but it was bloated.
The shipping version is **Go** — same features, dramatically faster.

| Metric                        | Python version        | Go version (now)    | Improvement              |
| ----------------------------- | --------------------- | ------------------- | ------------------------ |
| **Cold start time**           | ~10–15 seconds        | ~50 milliseconds    | **~250× faster**         |
| **Docker image size**         | ~1 GB                 | ~15 MB              | **~65× smaller**         |
| **Memory at idle**            | ~400 MB               | ~20 MB              | **~20× leaner**          |
| **Request latency (p99)**     | ~200 ms               | ~5 ms               | **~40× faster**          |
| **Embedding model needed?**   | Yes (PyTorch, 300 MB) | No (in-process)     | Removed entirely         |
| **External subprocess?**      | Yes (graphify CLI)    | No (in-process)     | Removed entirely         |

What that means in practice:

- The whole backend fits on a Raspberry Pi.
- We can run dozens of these instances for the cost of one Python one.
- A user filing a request gets a response **instantly**, instead of
  waiting for Python to load a model.

### Why this matters for scalability

The Maldives has ~520,000 citizens. The ministry doesn't know how many
will use the portal — it could be 10 a day or 10,000 a day. With Go,
the same hardware can handle **two orders of magnitude more traffic**
than the Python version, with no architectural changes.

---

## Why we rewrote the frontend in TypeScript

The first version was a single 2,400-line JavaScript file. The
shipping version is **TypeScript + Tailwind**, organised into ~25
small files.

| Concern                       | JavaScript version       | TypeScript version          | Why it matters                                                |
| ----------------------------- | ------------------------ | --------------------------- | ------------------------------------------------------------- |
| **Type safety**               | None — runtime crashes   | Compile-time checks         | Bugs caught before the demo, not during it.                   |
| **API contract**              | Hand-written, drifts     | Types mirror the Go backend | Renaming a backend field breaks the *build*, not the user.    |
| **Codebase shape**            | 2,389 lines in 1 file    | ~3,000 lines in 25 files    | Each file is one screen or one concept. Easy to read.         |
| **Editor experience**         | Plain autocomplete       | Full IntelliSense / refactors | New contributors are productive in hours, not weeks.        |
| **Refactoring confidence**    | Hope and prayer          | Compiler-checked             | We can keep improving without fear of regressions.            |
| **Visual consistency**        | Inline styles everywhere | Tailwind + 12-component UI kit | Looks like one professional product, not ten student projects. |
| **Production JS bundle**      | ~280 KB / 90 KB gzipped  | **211 KB / 65 KB gzipped**  | ~28% lighter despite *more* code — Vite tree-shakes aggressively. |
| **Production CSS**            | None (all inline)        | **21 KB / 5 KB gzipped**     | Cached separately, applied once.                              |

What that means in practice:

- A new contributor can read one file (e.g. `pages/HomePage.tsx`) and
  understand it in 30 seconds.
- The frontend talks to the backend through a **typed API client** —
  if we ever change a field name on the backend, the frontend won't
  compile until it's fixed. No silent breakage.
- The look-and-feel is consistent because every page uses the same
  ~12 components (`Card`, `Button`, `StatusBadge`, …) instead of
  hand-rolled HTML.
- The whole SPA gzips to **70 KB** — small enough to load instantly
  even on a 3G connection on a remote atoll.

---

## What the user sees (design)

We deliberately chose a **minimalist, professional look** — calm
grayscale with a single blue accent for primary actions. Nothing
shouts, nothing distracts. This is a government portal; it should
feel like one.

- The brand mark in the navbar reads **RTI4All · Automated
  Transparency** so anyone landing on the homepage immediately gets
  the value prop.
- Citizens get a clean dashboard: their requests in a table, status
  pills (Pending, Under Review, Responded, Rejected, Clarification
  Needed), and a one-click form to file a new request.
- Officers get a dedicated `/admin` review inbox with the citizen's
  full request, the AI draft (editable), the AI analysis (type,
  complexity, completeness %), and four clear actions: **Save draft**,
  **Ask for clarification**, **Reject**, **Approve & publish**.

---

## Demo accounts (seeded at startup)

Two accounts are created automatically every time the stack boots —
this is what you log in with during the demo.

### 🟦 Information Officer (admin)

| Field        | Value                          |
| ------------ | ------------------------------ |
| Email        | `officer@gov.mv`               |
| Password     | `super-secret-pass`            |
| Full name    | Officer Hassan                 |
| Address      | Ministry HQ, Male'             |
| Phone        | +960 3001000                   |
| Admin?       | **Yes** (via `ADMIN_EMAILS` env) |

After login the navbar shows an **Admin** tab → `/admin` is the
review inbox.

### 🟩 Citizen

| Field        | Value                                       |
| ------------ | ------------------------------------------- |
| Email        | `citizen@example.mv`                        |
| Password     | `another-pass`                              |
| Full name    | Aishath Hassan                              |
| Address      | H. Sunset, Hithadhoo, Addu City             |
| Phone        | +960 7777777                                |
| ID card      | A099887                                     |
| Admin?       | No                                          |

After login the navbar shows **My requests** + **File a request**.

> Tip: open two browser windows side-by-side (or one normal + one
> incognito) — citizen on the left, officer on the right — so you can
> show the lifecycle in real time.

---

## Live demo flow (3 minutes)

Two browser windows side-by-side: citizen on the left, officer on the
right. Both already logged in.

### Happy path (steps 1–3, ~90 seconds)

1. **Citizen** files a *specific* request:
   - Subject: *"Solar PV capacity installed in Addu City, 2024"*
   - Description: *"Please provide the total solar PV generation
     capacity (in MW) commissioned in Addu City during calendar year
     2024, broken down by island."*
   - Submit. The Structurer scores it ~0.9 (clear time period + clear
     geography + clear ask), the Drafter writes a reply, and the
     citizen sees status **Under Review** with a purple **Draft
     Response · Pending Officer Review** card.

2. **Officer** clicks **Admin** → the request is at the top of the
   inbox. Open it:
   - Left column: citizen's request, the AI draft (editable), reject
     reason field, clarification form.
   - Right rail: citizen's full profile, audit trail, AI analysis
     (type, complexity, completeness).
   - Click **Approve & publish**.

3. **Citizen** refreshes → status flips to **Responded**, a green
   **Official response** card appears. *Done.*

### Clarification path (steps 4–6, ~90 seconds)

4. **Citizen** files a *vague* request — e.g. just *"info about
   energy"*. The Structurer scores it < 0.7 → **no draft is
   generated**. Status is **Under Review** but no draft card appears.

5. **Officer** opens the new request. The AI analysis panel
   highlights "missing time period, missing geography". Click **Ask
   for clarification**, type a message like *"Please specify which
   atoll and which year"*, list one or two questions, submit.

6. **Citizen** refreshes → status is now **Clarification Needed**, an
   amber form shows the officer's questions. Fill them in, submit →
   status flips back to **Under Review** with a refreshed AI
   analysis. Officer can now approve.

**Punchline**: the agent doesn't just answer questions — it knows
when *not* to answer and asks the right questions instead. That's
the difference between an AI assistant and an AI gimmick.

---

## What's interesting under the hood (for the technical judges)

If a judge asks "but what's actually new here?", here are the answers:

**🛠️ Hackathon technical achievements:**

- **True agentic architecture in 48 hours** — Not just a chatbot wrapper. We built a 5-step reasoning pipeline with two specialized agents (Sonnet for structure, Haiku for generation), a completeness-based gate between them, dual-layer retrieval (TF-IDF + token-cooccurrence graph), and a feedback loop that improves the system with every officer approval.

- **Production-grade system from scratch** — Full-stack rewrite from Python to Go (250× faster cold start) and JavaScript to TypeScript (type-safe API contract), containerized with Docker Compose, ready to deploy to any ministry with minimal configuration.

- **Real-world government data handling** — Solved the semi-structured data extraction problem that affects every government ministry: inconsistent Excel sheets, Word documents with variable formatting, historical records without schemas. Our dual-layer retrieval handles this gracefully.

- **Human-in-the-loop by design** — The agent knows when it doesn't know. Low completeness scores trigger clarification requests instead of hallucinated answers. Every disclosure requires officer approval. Full audit trail for accountability.

**🏛️ Technical deep-dive:**

- **Two-agent AI pipeline** with a confidence gate between them. Sonnet (JSON) decides whether Haiku (prose) should even run. Most "AI chatbots" don't do this — they just throw every message at a single model.

- **Two-layer retrieval** (TF-IDF cosine + token-cooccurrence graph), both implemented deterministically in-process. No 300 MB embedding model, no Python subprocess, no GPU. Boots in microseconds.

- **Feedback loop**: every officer approval refreshes both retrieval indexes. The corpus grows with usage, so the agent improves over time without retraining anything.

- **Go backend in 15 MB**: includes the AI client, both retrieval layers, atomic JSON persistence with rotated backups, JWT/bcrypt auth, and a chi-routed HTTP API — the entire backend ships in a static binary smaller than most PDFs.

- **Strict-mode TypeScript frontend** with a hand-rolled UI kit (no shadcn, no radix, no MUI) and a typed fetch client — SPA bundle gzips to 65 KB.

- **Identical HTTP contract** between the old Python backend and the new Go backend, so the rewrite was risk-free: same JSON shapes, same auth model, same routes.

- **Cross-ministry ready**: Modular department structure, configurable retrieval corpora, extensible state model. Any ministry can adopt this pattern without architectural changes.

---

## TL;DR for the elevator pitch

> "RTI4All is an **agentic AI system** selected as a **Wave 1 pilot** for the Maldives AI Lab. It cuts ministry response time from weeks to minutes by drafting Right to Information replies with an AI assistant grounded in the ministry's own archive. 
>
> Two Claude models split the work — Sonnet structures the request and gates the workflow with a completeness score, Haiku writes the reply — and a real officer approves every response, so it's accurate and accountable.
> 
> Built in **48 hours** during the CoLab26 hackathon, we rewrote it in Go and TypeScript for a **250× faster cold start**, a **65× smaller Docker image**, and a frontend that gzips to **70 KB** — so the same hardware can serve orders of magnitude more citizens.
>
> **Impact reach**: ~500,000 citizens — the entire eligible Maldivian population for whom RTI is a foundational right."

---

## Q&A cheat-sheet — "show me…"

| If a judge asks…                              | Point at this                                                                       |
| --------------------------------------------- | ----------------------------------------------------------------------------------- |
| "What did you build in 48 hours?"             | DEMO → **What we accomplished in this hackathon** section                          |
| "What makes this 'agentic' AI?"               | README → **The agentic workflow** diagram + DEMO → **Why this is more than ChatGPT** |
| "What's the impact reach?"                    | **~500,000 citizens** — entire eligible Maldivian population                        |
| "Is this a real government use case?"         | Yes — **Wave 1 pilot** selected through CoLab National AI Use Case Selection Sprint |
| "Show me the AI workflow"                     | README → **The agentic workflow** diagram                                            |
| "Show me how RAG works"                       | README → **How we use RAG and graphify** + the live demo step 2                      |
| "What models are you using?"                  | README / DEMO → **Models we use (and why)** — Sonnet for JSON, Haiku for prose       |
| "Why not GPT/Gemini?"                         | DEMO → **Why Claude** bullet points                                                  |
| "Why not OpenAI embeddings?"                  | DEMO → **Why we don't use an embedding model**                                       |
| "Is the AI making things up?"                 | Open a Responded request — the reply cites prior RTI ids verbatim                    |
| "What if the AI is wrong?"                    | The officer reviews everything. Show the **edit** textarea on the admin review page. |
| "What if the citizen's request is unclear?"   | Live demo steps 4–6 — agent recognises low completeness and asks for clarification   |
| "How fast is it?"                             | DEMO → **Python-vs-Go** table (cold start 50 ms, p99 latency 5 ms)                   |
| "Can it scale?"                               | Backend container is 15 MB → talk about Pi-class hosting + horizontal scale          |
| "Why TypeScript over JavaScript?"             | DEMO → **JS-vs-TS** table — type safety, API contract drift, bundle size             |
| "Where's the citizen's profile?"              | Open the admin review page — full address + phone in the right rail                  |
| "How does the agent improve over time?"       | README → **The feedback loop** — every approval refreshes both retrieval indexes     |
| "Can other ministries use this?"              | Yes — **cross-ministry extensibility** built into architecture                        |
| "How is this auditable?"                      | Every disclosure is traceable — what was asked/retrieved/approved. Show audit trail  |

That's it. Good luck with the demo.
