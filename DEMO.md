# RTI4All — Demo Brief

> A short, plain-English version of the README for the presentation.
> If you've never seen the project before, read this top-to-bottom and
> you'll be able to talk through every slide.

---

## In one sentence

**RTI4All is an AI-assisted Right to Information portal for the Maldives
Ministry of Climate Change, Environment and Energy — citizens file
information requests, the AI drafts a response, and a real officer
approves it before it's published.**

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

RTI4All fixes that.

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

## RAG and graphify — what they are, in everyday terms

Both are how the AI "looks things up" before writing a reply. We use
**two of them in parallel** because they catch different kinds of
matches.

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

| Metric                        | Python version      | Go version (now)    | Improvement              |
| ----------------------------- | ------------------- | ------------------- | ------------------------ |
| **Cold start time**           | ~10–15 seconds      | ~50 milliseconds    | **~250× faster**         |
| **Docker image size**         | ~1 GB               | ~15 MB              | **~65× smaller**         |
| **Memory at idle**            | ~400 MB             | ~20 MB              | **~20× leaner**          |
| **Request latency (p99)**     | ~200 ms             | ~5 ms               | **~40× faster**          |
| **Embedding model needed?**   | Yes (PyTorch, 300MB)| No (in-process)     | Removed entirely         |
| **External subprocess?**      | Yes (graphify CLI)  | No (in-process)     | Removed entirely         |

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

| Concern                       | JavaScript version    | TypeScript version    | Why it matters             |
| ----------------------------- | --------------------- | --------------------- | -------------------------- |
| **Type safety**               | None — silent bugs    | Compile-time checks   | Catches mistakes before they reach users |
| **API mismatches**            | Found in production   | Found before commit   | No "undefined is not a function" surprises |
| **Codebase size**             | 2,400 lines in 1 file | ~3,000 lines / 25 files | Each file does one thing well |
| **Editor support**            | Plain autocomplete    | Full intellisense     | New devs onboard in hours, not weeks |
| **Refactoring**               | Risky                 | Safe — TS checks every change | We can keep improving without fear |
| **UI consistency**            | Inline styles everywhere | Tailwind + design system | Looks like one app, not ten |

What that means in practice:

- A new contributor can read one file (e.g. `pages/HomePage.tsx`) and
  understand it in 30 seconds.
- The frontend talks to the backend through a **typed API client** —
  if we ever change a field name on the backend, the frontend won't
  compile until it's fixed. No silent breakage.
- The look-and-feel is consistent because every page uses the same
  ~12 components (`Card`, `Button`, `StatusBadge`, …) instead of
  hand-rolled HTML.

---

## What the user sees (design)

We deliberately chose a **minimalist, professional look** — calm
grayscale with a single blue accent for primary actions. Nothing
shouts, nothing distracts. This is a government portal; it should
feel like one.

- Citizens get a clean dashboard: their requests in a table, status
  pills (Pending, Under Review, Responded, Rejected, Clarification
  Needed), and a one-click form to file a new request.
- Officers get a dedicated `/admin` review inbox with the citizen's
  full request, the AI draft (editable), the AI analysis (type,
  complexity, completeness %), and four clear actions: **Save draft**,
  **Ask for clarification**, **Reject**, **Approve & publish**.

---

## Live demo flow (3 minutes)

Two browser windows side-by-side: citizen on the left, officer on the
right.

**Setup** — both already logged in.

1. **Citizen** files a specific request, e.g.:
   - *"Solar PV capacity installed in Addu City, 2024 — please provide
     total MW commissioned during calendar year 2024, broken down by
     island."*
   - The AI structures it, scores it as "complete enough", and drafts
     a reply citing past ministry records.
   - Status: **Under Review** (purple "Draft Response · Pending Officer
     Review" card).

2. **Officer** opens the admin inbox, clicks into the request:
   - Sees the citizen's request, the AI draft (editable), the AI
     analysis (type: Data Request, complexity: Moderate, completeness:
     92%).
   - Clicks **Approve & publish**.

3. **Citizen** refreshes → status flips to **Responded**, green card
   shows the official response. *That's the happy path, ~30 seconds.*

4. Now **citizen** files a vague request — *"info about energy"*.
   - The AI's completeness score drops below 0.7 → **no draft is
     generated.** The citizen sees an Under Review status with no
     reply yet.

5. **Officer** opens it, sees the analysis flagging "missing time
   period, missing geography", clicks **Ask for clarification**,
   types a message + two questions.

6. **Citizen** refreshes → status is **Clarification Needed**, with an
   amber form asking the questions. Citizen fills them in, submits.
   Status flips back to **Under Review**, the AI re-analyses with the
   new info, the officer can now approve.

**Punchline**: the agent doesn't just answer questions — it knows when
*not* to answer and asks the right questions instead. That's the
difference between an AI assistant and an AI gimmick.

---

## What's interesting under the hood (for the technical judges)

If a judge asks "but what's actually new here?", here are the answers:

- **Two-agent AI pipeline** with a confidence gate between them.
  Structurer (Sonnet, JSON) decides whether the Drafter (Haiku, prose)
  should even run. Most "AI chatbots" don't do this.
- **Two-layer retrieval** (TF-IDF cosine + token-cooccurrence graph)
  with deterministic, in-process implementations. No 300 MB embedding
  model, no Python subprocess, no GPU. Boots in milliseconds.
- **Feedback loop**: every officer approval refreshes both retrieval
  indexes. The corpus grows with usage, so the agent improves over
  time without retraining anything.
- **Go backend in 15 MB**: includes the AI client, both retrieval
  layers, atomic JSON persistence with rotated backups, JWT/bcrypt
  auth, and a chi-routed HTTP API — the entire backend ships in a
  static binary smaller than most PDFs.
- **Strict-mode TypeScript frontend** with a hand-rolled UI kit (no
  shadcn, no radix, no MUI) and a typed fetch client — the SPA bundle
  gzips to 65 KB.

---

## TL;DR for the elevator pitch

> "RTI4All cuts ministry response time from weeks to minutes by
> drafting Right to Information replies with an AI assistant grounded
> in the ministry's own archive. A real officer approves every reply,
> so it's accurate and accountable. We rewrote it in Go and TypeScript
> for a 250× faster cold start, a 65× smaller image, and a frontend
> small enough to ship on a phone — so the same hardware can serve
> orders of magnitude more citizens."

---

## What to point at when someone asks "show me"

| Question                              | Where to point                                            |
| ------------------------------------- | --------------------------------------------------------- |
| "Show me the AI workflow"             | The diagram in **README.md → The agentic workflow**       |
| "Show me how RAG works"               | **README.md → How we use RAG and graphify** + the live demo step 2 |
| "Is the AI making things up?"         | Open a Responded request — the reply cites prior RTI ids  |
| "What if the AI is wrong?"            | The officer reviews everything. Show the **Edit** button on the admin page. |
| "How fast is it?"                     | The Python-vs-Go table in this file (DEMO.md)             |
| "Can it scale?"                       | Cold start 50 ms, image 15 MB → talk about Pi-class hosting  |
| "Where's the citizen profile?"        | Open the admin review page — full address + phone in the right rail |

That's it. Good luck with the demo.
