# The Hypotenuse Compiler

This document describes the architecture, compilation pipeline, and command-line interface of the Hypotenuse compiler.

---

## Overview

The Hypotenuse compiler transforms C△ source files into native Linux ELF x86_64 binaries. The compilation pipeline proceeds in seven ordered stages, each implemented as a discrete Python module. Code generation emits both C source and NASM assembly; GCC and NASM then produce object files that the linker combines into the final binary.

```
.ctri / .plib source
        │
        ▼
    [ Lexer ]          src/lexer.py
        │  token stream
        ▼
    [ Parser ]         src/parser.py
        │  parse nodes
        ▼
   [ Structor ]        src/structure.py
        │  Scope / Callee / Caller graph
        ▼
  [ Code generator ]   (planned)
        │  .c  +  .asm files
        ▼
  GCC  ──── NASM
        │  object files
        ▼
     Linker
        │
        ▼
     binary
```

---

## Compilation Stages

### Stage 1 — Lexer (`src/lexer.py`)

The lexer converts raw source text into a flat list of typed tokens. Tokens are matched in priority order using compiled regular expressions. Whitespace and comments are consumed and discarded.

The token stream is a list of `(TYPE, lexeme)` tuples. The final token appended by the driver is always `("EOF", "EOF")`.

**Token categories:**

| Category | Examples |
|---|---|
| Keywords | `INT`, `FLOAT`, `STRUCT`, `AUTO`, `RETURN`, … |
| Literals | `INT_LITERAL`, `FLOAT_LITERAL`, `STRING_LITERAL`, `CHAR_LITERAL` |
| Operators | `PLUS`, `MINUS`, `MULTIPLY`, `ASSIGN`, `INCREMENT`, … |
| Delimiters | `LPAREN`, `RPAREN`, `LBRACE`, `RBRACE`, `SEMICOLON`, … |
| Identifiers | `IDENTIFIER` |
| Discarded | `WHITESPACE`, `COMMENT_LINE`, `COMMENT_MULTI` |

Order within the token table is significant. Tokens defined earlier take priority. `INCREMENT` (`++`) must therefore appear before `PLUS` (`+`).

---

### Stage 2 — Parser (`src/parser.py`)

The parser reads the token stream and validates syntactic structure. It is currently under active development as part of the Stage 1 milestone. Known open issues tracked in the repository:

| Issue | Description |
|---|---|
| #61 | Negative number parsing — fixed in `structure.py` via `_parse_literal_value` |
| #62 | Program scope bug — fixed via scope stack in `build_and_sort` |
| #43 | Add function support |

---

### Stage 3 — Structor (`src/structure.py`)

The Structor builds the program's semantic graph from the token stream. It does not produce a traditional AST. Instead it constructs a graph of three node types within a hierarchy of `Scope` objects.

**Node types:**

| Type | Role |
|---|---|
| `Scope` | Named lexical scope — has `callees`, `callers`, and generic `children` |
| `Callee` | Provides a value or function — analogous to a definition |
| `Caller` | Depends on one or more `Callee` nodes — analogous to a use site |

Scopes form a tree. Name resolution walks up the scope chain: `Scope.called(name)` checks local `children`, `callees`, and `callers`, then recurses into `parent`.

The outermost scope is always named `"program"`. Each function definition opens a child scope named after the function. The scope stack is maintained across the token stream; `LBRACE` after a function signature pushes a new scope and `RBRACE` pops it.

**`Lib`** is a lightweight wrapper that gives a named `Scope` to an external library, enabling node lookups within it.

The `build_and_sort` method returns objects ordered by first-appearance position in the token stream.

---

### Stage 4 — Code Generator *(planned)*

Code generation walks the structured graph and emits:

- A `.c` file for each source file — C11-compatible output fed to GCC.
- One `.asm` file per `asm` block or `asm` function — fed to NASM.

Each `asm` block becomes a standalone NASM source file. The function name in the `asm` declaration is the NASM label. No explicit `global` directive is needed; the code generator inserts it.

---

### Stage 5 — Assembly and Compilation *(planned)*

GCC compiles the emitted `.c` files and NASM assembles each `.asm` file:

```
gcc -c output.c -o output.o
nasm -f elf64 block.asm -o block.o
```

---

### Stage 6 — Linking *(planned)*

All object files are linked into the final binary:

```
gcc output.o block.o -o program
```

Libraries referenced via `using` or `show` are linked automatically based on actual usage — no manual `-l` flags are required.

---

## File Types

| Extension | Description |
|---|---|
| `.ctri` | C△ source file — executable if it contains `main`, library otherwise |
| `.plib` | C△ library file — must not contain `main` |

Executable vs. library status is determined by the presence of a `main` function and the file extension. The compiler enforces that `.plib` files do not define `main`.

---

## Library Search Paths

| Path | Scope |
|---|---|
| `/usr/lib/PLIBS/` | System-wide `.plib` libraries |
| `~/.local/lib/PLIBS/` | User-installed `.plib` libraries |
| Directory of the source file | Local relative imports via `using x from "lib"` |

---

## Command-Line Interface

The compiler is invoked via `src/main.py` (or the installed `hypotenuse` binary after `make`).

```
usage: hypotenuse [-h] [-t] [-o PATH] [-a] [files ...]
```

### Positional Arguments

| Argument | Description |
|---|---|
| `files` | One or more `.ctri` or `.plib` source files to compile |

### Options

| Flag | Long form | Description |
|---|---|---|
| `-h` | `--help` | Show help message and exit |
| `-t` | `--tokens` | Print the lexed token stream for the first file and exit |
| `-o PATH` | `--output PATH` | Write compiled output to PATH *(not yet implemented)* |
| `-a` | `--asm` | Show generated assembly *(not yet implemented)* |

### Examples

```bash
# Compile a source file
hypotenuse hello.ctri

# Print the token stream
hypotenuse -t hello.ctri

# Specify output path (planned)
hypotenuse -o hello hello.ctri

# Show assembly output (planned)
hypotenuse -a hello.ctri
```

---

## Installation

**Requirements:**

- Linux (x86_64)
- Python 3.10 or later
- GCC
- NASM
- GNU Make

**Steps:**

```bash
git clone https://github.com/setuser1/The-Hypotenuse-Compiler
cd The-Hypotenuse-Compiler
make
```

The `make` target installs the `hypotenuse` command to a location on `PATH`. See the `makefile` for details.

---

## Repository Layout

```
/
├── src/
│   ├── main.py          Driver — argument parsing, pipeline entry point
│   ├── lexer.py         Lexer — tokenisation
│   ├── parser.py        Parser — syntactic validation
│   └── structure.py     Structor — Scope/Callee/Caller graph builder
├── docs/                Language and compiler documentation
├── test/                Test suite
├── makefile             Build system
└── LICENSE
```

---

## Development Stages

The compiler is developed across seven self-host milestones.

| Stage | Status | Goal |
|---|---|---|
| 1 | **Active** | Fix `parser.py` and `structure.py`, resolve issues #43 #61 #62 |
| 2 | Planned | Simulation pass — autoremove and type inference |
| 3 | Planned | Code generator — emit `.c` and `.asm` |
| 4 | Planned | GCC + NASM integration |
| 5 | Planned | Linker integration — produce ELF binary |
| 6 | Planned | plstd standard library |
| 7 | Planned | Self-host — compiler compiles itself |
