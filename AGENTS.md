# AGENTS.md – Repository Guide

> **Source of truth**: https://hypotenuse.mintlify.app supersedes this file for language features, CLI flags, and stdlib reference. When this file conflicts with Mintlify, Mintlify wins.
>
> **⚠ macOS support is being dropped.** The ARM64 macOS (Mach-O) backend is deprecated and will be removed in a future release. All future development targets Linux x86_64 only.

---

## Build / Lint / Test Commands

| Action                      | Command                                          | Description                                                   |
| --------------------------- | ------------------------------------------------ | ------------------------------------------------------------- |
| Install dependencies        | `make install`                                   | Installs `pytest`, `pyflakes`.                                |
| Run baseline (generates C)  | `make run`                                       | Compiles `test/baseline.ctri`, prints generated C to stdout.  |
| Compile with GCC            | `python3 src/main.py -c -C "FLAGS" file.ctri`   | Compile `.ctri` to executable. Use `-C` for extra cflags.     |
| Print tokens (debug)        | `python3 src/main.py -t test/<file>.ctri`        | Lexes the file and prints the token stream.                   |
| Print structure graph       | `python3 src/main.py -p test/<file>.ctri`        | Prints the Callee/Caller/Scope graph.                         |
| Show generated assembly     | `python3 src/main.py -a test/<file>.ctri`        | Shows `.asm` output for `asm` blocks.                         |
| Lint                        | `make lint`                                      | Runs **pyflakes** against `src/*.py`.                         |
| Type-check / regression     | `make typecheck`                                 | Executes the compiler on every `.ctri` test file.             |
| Full test suite             | `make test`                                      | Lint → type-check → regression checks.                        |
| Run a single test           | `python3 src/main.py test/<file>.ctri`           | Compile one `.ctri` fixture directly.                         |
| Clean CI build              | `make all`                                       | `install → lint → test`; used by GitHub CI.                   |
| Build binary                | `make build`                                     | Build PyInstaller executable (`dist/hypotenuse`).             |
| Install binary              | `make full-install`                              | Install to `/usr/local/bin` or `~/.local/bin`.                |

---

## Code-Style Guidelines

- **Imports**: absolute only inside `src` (`import lexer`). No relative imports. No wildcard imports.
- **Formatting**: 4 spaces, no tabs. Max 120 chars. No trailing whitespace. Two blank lines before top-level defs. End every file with a newline.
- **Naming**: `snake_case` for modules/functions/variables. `PascalCase` for classes. `UPPER_SNAKE_CASE` for constants. `_prefix` for private helpers.
- **Type hints**: PEP 484 style, minimal. Avoid `Any`.
- **Error handling**: Specific exception catches (no bare `except`). Error messages from `src/error_msgs.py`.
- **Testing**: Idempotent, no mutable global state. Assert on stable substrings.
- **Lint**: Run `make lint` (pyflakes) before committing.

---

## Project Layout

- **src/** — `lexer.py`, `parser.py`, `structure.py`, `codegen.py`, `optimizer.py`, `struct_layout.py`, `error_msgs.py`, `nasmgen.py`, `assembler.py`, `main.py`
- **plstd/** — Standard library `.plib` files (self-contained, no headers)
- **test/** — `.ctri` fixtures and integration checks
- **docs/** — Markdown documentation
- **Makefile** — Orchestrates build, lint, and test steps

---

## CI / GitHub Actions

- **`makefile.yml`** — Runs `make all` on every push/PR (install, lint, full test suite)
- **`summary.yml`** — Aggregates job results, posts a PR comment
- **`label.yml`** — Auto-adds labels based on `labeler.yml`

---

## Language Quick Reference

> Full reference: https://hypotenuse.mintlify.app

### Types

**C11 primitives** (sizes on x86_64/Linux LP64): `int` (4B), `unsigned int` (4B), `short` (2B), `long` (8B), `char` (1B), `float` (4B), `double` (8B), `void`.

**C△-specific**: `string` (first-class, auto-managed), `auto` (inferred, `%k` specifier), `dynam` (dynamic array: `.push()`, `.pop()`, `.remove()`, `len()`).

**Not yet implemented**: `tuple`, `typed struct` inheritance, `lamb`, `autoremove`, `Robbery`.

### Structs

```ctri
struct Point(int x, int y) {
    init { self.x = x; self.y = y; }
    int distanceTo(Point other) { ... }
    end { }
}
```

> `init`/`end`, member functions, and `typed struct` inheritance are not yet implemented. Plain C-style structs work via C11 baseline.

### Keywords

**Control flow**: `if`, `else`, `while`, `for`, `do`, `switch`, `case`, `default`, `break`, `continue`, `return`, `goto`

**Storage**: `const`, `volatile`, `static`, `extern`, `inline`, `register`, `sizeof`

**C△-specific**: `using`, `expose`, `space`, `allocate`, `free`, `asm`, `self`, `init`, `end`, `auto`, `len()`

**Deprecated** (SyntaxError): `restrict`, `_Bool`, `_Complex`, `_Imaginary`, `_Alignof`, `_Alignas`

### Memory Model

- **Stack**: normal declarations, freed on scope exit
- **Heap**: `allocate int buf[64]` (array) or `allocate int x(64)` (byte-sized). Must `free()` manually.
- `autoremove` and Robbery are not yet implemented.

### Inline Assembly

```ctri
asm int addInts(int a, int b) {
    syntax x86_64_linux
    section .text
    mov rax, a
    mov rbx, b
    add rax, rbx
    return
}
```

- Each `asm` block → separate `.asm` file → NASM → GCC linker
- `syntax`: `x86_64_linux`, `arm64_macho` (deprecated)
- `return` = `ret`; implicit return is `rax` (x86) / `x0` (ARM64). Required for non-`void`.
- `asm` blocks are opaque to the simulation pass
- Text section mandatory: `section .text` (x86), `.section __TEXT,__text` (ARM64)

### Standard Library (plstd)

Located at `/usr/lib/PLIBS/` (system) and `~/.local/lib/PLIBS/` (user). Each `.plib` is self-contained.

- `printd(value)` — type-aware print
- `printfs(format, ...)` — formatted print with `{expr}` interpolation and `%` specifiers
- String library — comparison, copy, concat, search (x86_64 and ARM64)

### Compiler Pipeline

```
.ctri → Lexer → Parser → Structurer → Simulation Pass → Code Gen → GCC + NASM → binary
```

---

## AI Agent Guidelines

- **Never edit without reading first.** Use `read`, `glob`, `grep`, `edit`, `write`, `bash`, `todo` tools.
- **Commit only when asked.** Run `make lint` and `make test` before committing.
- **No destructive git actions** without explicit authorization (`git reset --hard`, force-push, etc.).
- **Parallelize** independent reads/searches using multi-tool calls.
- **Clarify** underspecified requests before proceeding.
- **Todo lists** for 3+ step tasks. One `in_progress` at a time.
- **Respect the style guide.** Follow naming, imports, formatting, and error-handling conventions.
- **Run lint & tests after changes.** Catch regressions early.
- **Report before fixing.** Enumerate bugs/risks with file:line references first. Fix only after approval.
- **Don't touch unrelated files.** Never delete code unless explicitly requested.
- **Update docs.** If you change functionality, update `docs/*.md` and/or the Mintlify docs.
- **Summarize.** After each change: what was done, why, remaining questions.

---

## End of AGENTS.md
