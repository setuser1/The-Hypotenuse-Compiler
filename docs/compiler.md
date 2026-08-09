# The Hypotenuse Compiler

<p align="center">
  <img src="../assets/logo.png" alt="C△ Logo" width="120"/>
</p>

The Hypotenuse Compiler transforms C△ source files into native Linux ELF x86_64 binaries through a multi-stage pipeline.

---

## Compiler Pipeline

```
.ctri source
     │
     ▼
  1 Lexer          (lexer.py)       ──▶  token stream
     │
     ▼
  2 Parser         (parser.py)      ──▶  AST (expressions only)
     │
     ▼
  3 Structurer     (structure.py)   ──▶  Callee/Caller/Scope graph
     │
     ▼
  4 Simulation Pass                 ──▶  constant folding, last-use analysis,
     │                                      robbery validation
     ▼
  5 Code Generation                 ──▶  .c file  +  .asm files
     │
     ▼
  6 GCC + NASM                      ──▶  object files
     │
     ▼
  7 Linker                          ──▶  native ELF binary
```

---

## Stage Details

### 1. Lexer (`lexer.py`)

Tokenizes the source file into a flat `(type, value)` token stream. Handles comments, preprocessor directives, all C△ keywords, operators, and literals.

### 2. Parser (`parser.py`)

Builds an **AST** from the token stream using a recursive-descent parser with full operator precedence. Covers expressions, statements, declarations, functions, structs, for/while/if, and more.

### 3. Structurer (`structure.py`)

Walks the AST and builds a **Callee/Caller/Scope graph** — the internal representation of all variables, functions, and their relationships. Scope rules:

- `program` — root scope
- `Function` — named child scope
- `For` — anonymous `for_N` child scope (init declaration scoped to loop)
- `If` / `While` / `Compound` — share enclosing scope

### 4. Simulation Pass

A static analysis pass that performs:

- Constant folding
- Last-use analysis (for `autoremove`)
- Robbery validation

### 5. Code Generation

Emits `.c` files from the AST and `.asm` files from `asm` blocks.

### 6. GCC + NASM

- GCC compiles the `.c` output
- NASM assembles each `.asm` block into an object file

### 7. Linker

GCC links all objects into the final native ELF binary. 🎉

---

## CLI Reference

```bash
python3 src/main.py [options] <file>
```

| Flag              | Description                                   |
| ----------------- | --------------------------------------------- |
| `-t` / `--tokens` | Print lexed tokens and scope graph, then exit |
| `-p` / `--print`  | Print structure graph instead of compiling    |
| `-o PATH`         | Write compiled output to PATH                 |
| `-a` / `--asm`    | Show generated assembly (WIP)                 |
| `-c` / `--compile` | Compile with gcc to executable               |
| `-C` / `--cflags` | Pass extra flags to gcc                       |
| `-i` / `--install` | Install file to PLIBS folder                 |
| `-r` / `--remove` | Remove a .plib file from PLIBS folder        |

### Example

```bash
# Compile a file
python3 src/main.py hello.ctri

# Debug tokens and scope graph
python3 src/main.py -t hello.ctri

# Print structure graph
python3 src/main.py -p hello.ctri

# Compile with gcc and extra flags
python3 src/main.py -c -C "$(sdl2-config --cflags --libs)" graphics.ctri

# Install a library
python3 src/main.py -i mylib.plib
```

---

