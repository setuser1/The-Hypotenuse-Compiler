# AGENTS-CHAT.md – Agent Communication Guidelines

---

## Purpose

This file defines the conventions for **inter‑agent chat** within the _Hypotenuse Compiler_ repository. It is consulted by any LLM‑driven tool (including this assistant) when collaborating with other agents that may be running in the same workspace.

## General Rules

1. **Plain language, no markup fluff** – keep messages concise and focused on the task. Use GitHub‑flavored Markdown only for code blocks or lists.
2. **One responsibility per turn** – an agent should either ask a clarification, perform a single logical action (e.g., run a command, edit a file), or summarise a result. Do not combine unrelated actions.
3. **Explicit state** – always state what you are about to do before invoking a tool (e.g., "Running `make lint` to verify the code style").
4. **Error handling** – if a tool returns an error, report the error verbatim and propose the next step rather than silently retrying.
5. **No hidden side‑effects** – never modify files, run git commands, or push commits unless the user explicitly asks for it.
6. **Tool‑first mindset** – prefer `read`, `glob`, `grep`, `edit`, `write`, `bash` before any speculative reasoning.
7. **Parallelism** – when multiple independent reads/searches are needed, issue them in a single parallel call.
8. **Ask before assuming** – if a request is ambiguous (e.g., missing file name, unclear behaviour), ask a short clarification question instead of guessing.

## Conversation Flow

| Phase         | Typical Content                                                                                   |
| ------------- | ------------------------------------------------------------------------------------------------- |
| **Init**      | Agent announces presence, confirms the repository root, and checks for existing `AGENTS-CHAT.md`. |
| **Clarify**   | Ask for missing details (file paths, expected behaviour, commit intent, etc.).                    |
| **Act**       | Perform a single well‑defined action (read, edit, run command, etc.).                             |
| **Validate**  | Run `make lint`/`make test` or appropriate checks, then report success or failure.                |
| **Summarise** | Provide a brief recap of what changed, why, and any remaining open questions.                     |

## Naming Conventions for Chat Files

- `AGENTS.md` – repository‑wide guidelines (already present).
- `AGENTS-CHAT.md` – this file, describing chat protocol.
- `AGENT-NOTE.md` - this file is where all the chats happen.
- `TODO.md` – optional informal task list (not used by default).

## Example Interaction

```
**Agent A**: I need to add a helper function to `src/utils.py`.  Do you want me to create the file?
**Agent B**: Yes, create `src/utils.py` with a `def hello() -> str:` placeholder and run `make lint`.
**Agent A**: ... (writes file, runs lint) ...
**Agent B**: The lint passed.  Commit is ready when the user asks.
```

---

_These guidelines are version‑controlled; update the file if the collaboration model evolves._
