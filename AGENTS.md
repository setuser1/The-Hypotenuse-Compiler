# AGENTS.md – Repository Guide for the Hypotenuse Compiler

---

## 1️⃣ Build / Lint / Test Commands

| Action                           | Command                                   | Description                                                                                                                            |
| -------------------------------- | ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Install dependencies             | `make install`                            | Installs the minimal Python packages (`pytest`, `pyflakes`).                                                                           |
| Run baseline                     | `make run`                                | Compiles `test/baseline.ctri` and prints the object graph.                                                                             |
| Lint                             | `make lint`                               | Runs **pyflakes** against all source files (`src/*.py`).                                                                               |
| Type‑check / regression          | `make typecheck`                          | Executes the compiler on every `.ctri` test file (currently only `baseline.ctri`). Fails on non‑zero exit.                             |
| Full test suite                  | `make test`                               | Installs deps → lint → type‑check → runs regression checks (scope tracking, value parsing, caller info, lexer/parser stability, etc.). |
| Run a single test file           | `python3 src/main.py -t test/<file>.ctri` | Use the CLI directly; replace `<file>` with any `.ctri` fixture under `test/`.                                                         |
| Run pytest (future Python tests) | `pytest -q test/`                         | Available if pure‑Python tests are added.                                                                                              |
| Clean CI build                   | `make all`                                | Alias for `install → lint → test`; used by GitHub CI.                                                                                  |

---

### 2️⃣ Code‑Style Guidelines

#### 📦 Project Layout

- **src/** – Python source (`lexer.py`, `parser.py`, `structure.py`, `main.py`).
- **test/** – `.ctri` fixtures and integration checks.
- **docs/** – Markdown documentation.
- **Makefile** – Orchestrates build, lint, and test steps.

#### 🧩 Imports

- Use **absolute imports** inside `src` (e.g., `import lexer`).
- Do **not** use relative imports (`from . import …`).
- For one‑off scripts in the Makefile, prepend `src` to `sys.path` **only** in that script.
- Avoid wildcard imports (`from module import *`).

#### 🎨 Formatting

- Indentation: 4 spaces, no tabs.
- Maximum line length: 120 characters.
- No trailing whitespace.
- Blank lines: two before top‑level definitions, one between class methods.
- End every file with a newline.

#### 🏷️ Naming Conventions

| Element             | Convention                                                    |
| ------------------- | ------------------------------------------------------------- |
| Modules / files     | `snake_case.py`                                               |
| Classes             | `PascalCase`                                                  |
| Functions / methods | `snake_case`                                                  |
| Constants           | `UPPER_SNAKE_CASE`                                            |
| Variables           | `snake_case` (short names like `i`, `t` allowed when obvious) |
| Private helpers     | Prefix with a single underscore (`_helper`).                  |

#### 📚 Types & Type Hints

- Keep type hints minimal but use **PEP 484** style where they improve clarity.
- Example:

  ```python
  def lex(self, source: str) -> List[Tuple[str, str]]:
      ...
  ```

- Avoid `Any` unless absolutely necessary.

#### ⚙️ Error Handling

- The CLI catches these, prints a concise message to `stderr`, and exits with a non‑zero status.
- Prefer specific exception catches; avoid bare `except:`.

#### 🧪 Testing Philosophy

- Current harness is shell‑based via the Makefile; new pure‑Python tests can be added under `test/` and run with `pytest`.
- Tests must be **idempotent** and must not rely on mutable global state.
- Use explicit `assert` statements with helpful messages.
- When checking compiler output, assert on stable substrings rather than exact formatting.

#### 🛠️ Linting & Static Analysis

- Run `make lint` before committing.
- The lint step uses **pyflakes**; it flags undefined names, unused imports, and syntax errors.
- Additional linters (Black, Flake8) may be added later but should not be enforced without consensus.

#### 📦 Packaging & Distribution

- The repository is not a pip‑installable package; it is invoked via `src/main.py`.
- If a library distribution becomes necessary, introduce a `setup.py` using the terminal.

---

### 3️⃣ Repository‑Specific Rules & Files

- **Cursor rules** – No `.cursor/` or `.cursorrules` directories were found; agents can skip cursor handling.
- **Copilot instructions** – No `.github/copilot‑instructions.md`; default Copilot behavior applies.
- **Labeler configuration** (`.github/labeler.yml`):

```yaml
documentation:
  - "**/*.md"
  - "**/*.txt"

enhancement:
  - "**/*.py"
  - "**/*.ctri"
  - "Makefile"

update/addition:
  - "**/*.py"
  - "**/*.txt"
  - "**/*.ctri"
  - "Makefile"
  - ".gitignore"
  - ".gitattributes"
  - ".github/workflows/**/*.yml"
```

- Used by GitHub automation to apply appropriate labels.

---

### 4️⃣ CI / GitHub‑Actions Overview

There are five github actions. The main one used here is build CI where it automates building and compiling a test file.

---

## 5️⃣ C△ (C Triangle) Language Documentation

### The Language: C△ (C Triangle)

C△ source files use the `.ctri` extension. Library files use `.plib`.

### Type System

#### C11 primitive types (inherited)

`int`, `char`, `void`, `float`, `double`, `short`, `long`, `signed`, `unsigned`, `struct`, `union`, `enum`, `typedef`

#### C△-specific types (new)

- `string` — first‑class string type; supports `+` concatenation and `{expr}` f‑string interpolation via `printfs`
- `auto` — dynamic/inferred type; resolved at runtime via the simulation pass; format specifier `%k`
- `dynam` — dynamic array; methods: `.push()`, `.pop()`, `.remove(index)`, `len()`; can be initialized: `dynam int x = [1, 2, 3];`
- `tuple` — heterogeneous list declared with `[]`; e.g. `tuple t = [1, "hello", 3.14];`
- `typed` — typed struct keyword; adds native‑type status and inheritance to a struct

### Structs

**Plain struct** — constructors and member functions; no inheritance; not a native type:

```ctri
struct Point(int x, int y) {
    init() { self.x = x; self.y = y; }
    end { }
    int distanceTo(Point other) { ... }
}
```

**Typed struct** — native type, supports single and multiple inheritance via `&`:

```ctri
typed struct Animal(string name) {
    init() { ... }
    string speak() { return "..."; }
    end { ... }
}
typed struct Dog&Animal(string name) { ... }
typed struct PoliceDog&Dog&Animal(string name, int badge) { ... }
// Conflict resolution: obj.Dog.speak(), obj.Animal.speak()
```

## Keywords

### Control flow

`if`, `else`, `while`, `for`, `do`, `switch`, `case`, `default`, `break`, `continue`, `return`, `goto`

### Storage modifiers

`const`, `volatile`, `static`, `extern`, `inline`, `register`, `sizeof`

### C△-specific keywords

- `using` — import: `using random from <math>`, `using helper from "utils"`, `using scope&myVar`
- `show` — globalize a library/namespace: `show plstd`, `show lib:io`
- `lib:` — explicit plstd access without globalizing: `lib:printd(42)`
- `space` — namespace declaration (in `.plib` files)
- `allocate` — heap allocation: `allocate int buf[256]`, `allocate int x(200) = val`
- `free` — manual heap deallocation
- `autoremove` — heap allocation freed automatically at last use via the simulation pass
- `asm` — inline assembly block (see Assembly section)
- `lamb` — named lambda, expression form: `lamb double(int num) = num * 2;`
- `self` — optional self‑reference in struct member functions
- `init()` — struct constructor lifecycle
- `end()` — struct destructor lifecycle
- `auto` — dynamic/inferred type (repurposed from C11)
- `len()` - calculates the character length of strings or the digits/decimal places of an integer.

#### Deprecated keywords (raise SyntaxError immediately)

`restrict`, `_Bool`, `_Complex`, `_Imaginary`

## Memory Model

- **Stack**: normal variable declaration; freed on scope exit
- **Heap**: `allocate type name[size]` or `allocate type name(bytesize)`; must be freed manually or via `autoremove`
- **`autoremove`**: simulation pass inserts `free` at last use — compile‑time, zero runtime cost
- **Robbery**: if another pointer takes the address of an `autoremove` variable before it drops (`int* q = &p`), ownership transfers; the new pointer becomes a plain heap variable; no `free` needed; validated by the simulation pass

## Inline Assembly (`asm` blocks)

```ctri
asm int addInts(int a, int b) {
    syntax x86_64_linux
    .section .text
    mov rax, a
    mov rbx, b
    add rax, rbx
    return       // replaces ret; implicit return value is rax; explicit can be anything.
}
```

- Each `asm` block compiles to a separate `.asm` file, assembled by NASM, linked by GCC
- `syntax x86_64_linux` declares the target inside the block
- Use C△ type declarations for parameters — not assembler directives
- `return` replaces `ret`; implicit return value is `rax`
- `asm` blocks are opaque to the simulation pass

## Standard Library (plstd)

Written in C△ itself with `asm` blocks for syscalls. Located at `/usr/lib/PLIBS/` (system) and `~/.local/lib/PLIBS/` (user).

Key functions:

- `printd(value)` — type‑aware print; auto‑detects type at runtime
- `printfs(format, ...)` — formatted print with `{expr}` f‑string interpolation and `%`‑style specifiers

---

### 5️⃣ 🤖 AI Agent Guidelines

- **`.github/workflows/makefile.yml`** – Executes `make all` on every push/PR (install, lint, full test suite).
- **`.github/workflows/summary.yml`** – Aggregates job results and posts a PR comment.
- **`.github/workflows/label.yml`** – Auto‑adds labels based on `labeler.yml`.
- **Tool‑first mindset**: always use the provided `read`, `glob`, `grep`, `edit`, `write`, `bash`, and `todo` tools to explore or modify the repository. Never edit a file without first reading it.
- **Commit policy**: create a git commit only when the user explicitly asks. Run `make lint` and the relevant tests (`make test` or the single‑test command) before committing to keep the repo green.
- **No destructive git actions**: never run `git reset --hard`, `git checkout --`, or force‑push unless the user explicitly authorises it.
- **Parallelism**: when multiple independent reads or searches are needed, issue them in parallel using the multi‑tool call pattern to minimise latency.
- **Clarify ambiguities**: if a request is underspecified (missing file name, unclear behaviour, etc.), ask a concise clarification question before proceeding.
- **Todo lists for multi‑step work**: for any task requiring three or more distinct actions, create a `todo` list, mark the current step `in_progress`, and update it as you go. Only one item should be `in_progress` at any time.
- **Respect the style guide**: any new code must follow the naming, import, formatting, typing, and error‑handling conventions described above.
- **Run lint & tests after changes**: automatically execute `make lint` and `make test` (or the appropriate single‑test command) after modifications to catch regressions early.
- **Report findings before fixing**: when reviewing code, first enumerate bugs or risks with file/line references, then propose a fix. Apply the fix only after the user approves or when the issue is unambiguous.
- **Do not touch unrelated files**: modify only files relevant to the current task; never delete code unless explicitly requested.
- **Documentation updates**: if you add or change functionality, update the relevant `docs/*.md` files to keep the language reference consistent.
- **Feedback loop**: after each substantial change, provide a concise summary of what was done, why, and any remaining open questions.

---

## End of AGENTS.md
