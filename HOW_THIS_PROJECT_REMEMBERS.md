# How this project remembers things

Written because it's genuinely unclear which work survives a Claude session and which doesn't —
and the difference is the whole ballgame. Work has been lost to this before (a Form ADV pull built
in another session that was never written to a file, so there was nothing to bring over).

There are **three separate places** something can live. Only two of them survive.

---

## 1. The repo — SURVIVES

`C:\projects\Praxis_Point_IR`, pushed to `github.com/robbreza/praxis-iq`.

Code and documents. This exists **only if a file was actually written and committed.** Claude
showing you code in the chat does *not* put it here.

**How to check:** `git log --oneline | head -20` — if it's not in the log, it's not in the project.

## 2. The memory folder — SURVIVES

`C:\Users\Owner\.claude\projects\C--Users-Owner\memory\`

Decisions and context, read at the **start of every new session**. This is how Claude knows, in a
brand-new conversation, that:

- all valuation work is held to CFA-charterholder rigor
- the Loughran-McDonald licence was deliberately designed around
- the IRconnect mailbox is client-level, with a per-client information barrier
- consensus uses the median of collected models, street as a labeled fallback

`MEMORY.md` is the index; the other files hold the detail. **If a decision isn't written here, the
next session won't know about it.**

## 3. The conversation — DOES NOT SURVIVE

When the session ends, it's gone. Anything Claude only *displayed* — a code block, a table, an
analysis — disappears with it.

**This is where work gets lost.** Code in a chat window is not in a project. It becomes real the
moment it's written to a file, and durable the moment it's committed.

---

## Three rules

1. **If you want it kept, make it a file.**
   When Claude shows code in chat: *"write that to a file and commit it."*
   No Write/Edit tool call = nothing on disk.

2. **Ask it to prove it.**
   *"Is that committed?"* → it runs `git log`. Takes seconds, removes all doubt.

3. **End a work session with:**
   *"Commit and push everything, and update memory."*

---

## What lives where in this project

| File | What it's for |
|---|---|
| `CHANGELOG.md` | **Human-readable history of what got built and why.** Skim this first. |
| `HANDOFF.md` | Project state / handoff notes |
| `DEPLOY.md` | How to deploy a reachable instance (Render), env vars, security checklist |
| `.env` | Secrets — **never committed** (gitignored). `.env.example` documents what's needed |
| `core/` | The engines (consensus, contacts, targets, 13F, Form ADV, auth…) |
| `config/client_config.py` | The in-code client seed; DB overlay wins at runtime |
| `page_modules_nicegui/` | The UI pages |

Data itself (clients, contacts, holders, users) lives in **Neon Postgres**, not in the repo — so
it persists independently of the code and isn't affected by git operations.

---

## A worked example

The Form ADV pull was rebuilt on 2026-07-19. It is durable because three things happened:

1. A file was written — `core/form_adv.py`
2. It was committed and pushed — `5f7cac3`
3. The decisions were recorded in memory (`praxis-next-steps.md`): where the SEC data lives, that
   the module is named `form_adv` because `ADV` already means *average daily volume* here, that it
   feeds `fund_addresses` rather than creating a rival store, and the two bugs found along the way.

A future session can pick it up cold. The earlier version had none of those three, which is
precisely why it vanished.
