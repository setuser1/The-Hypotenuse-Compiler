# C△ Error Reference

This document lists every error the Hypotenuse compiler can emit, the conditions that trigger each one, and how to resolve it.

---

## Compiler Error Format

All compiler errors follow this format:

```
Error: <message>
  --> <file>:<line>:<column>
```

Runtime errors from `plstd` are printed to stderr with a personality message drawn from the `errors/` folder. The format is:

```
[C△ runtime] <personality message> — <error type> at <location>
```

---

## Lexer Errors

| Code | Message | Cause | Fix |
|---|---|---|---|
| L001 | `Unknown token` | A character that matches no token pattern was encountered | Remove or replace the invalid character |
| L002 | `Unterminated string literal` | A `"` was opened but never closed before end of line | Close the string literal |
| L003 | `Unterminated char literal` | A `'` was opened but never closed | Close the char literal |
| L004 | `Unterminated block comment` | `/*` was opened but `*/` was never found | Close the block comment |

---

## Parser Errors

| Code | Message | Cause | Fix |
|---|---|---|---|
| P001 | `Expected identifier` | A declaration keyword was followed by a non-identifier token | Provide a valid name |
| P002 | `Expected '('` | A function declaration had no parameter list | Add `()` after the function name |
| P003 | `Expected ')'` | A parameter list or expression was not closed | Close the parenthesis |
| P004 | `Expected '{'` | A block body was expected but not found | Add `{` |
| P005 | `Expected '}'` | A block body was opened but never closed | Add `}` |
| P006 | `Expected ';'` | A statement was not terminated | Add `;` |
| P007 | `Unexpected EOF` | The token stream ended while parsing an incomplete construct | Complete the construct |
| P008 | `Deprecated keyword` | One of the deprecated C keywords (`restrict`, `_Bool`, `_Complex`, `_Imaginary`, C11 `auto`) was used | Remove or replace the keyword |

---

## Structor Errors

| Code | Message | Cause | Fix |
|---|---|---|---|
| S001 | `Duplicate symbol in scope` | A name is declared twice in the same scope | Rename one of the declarations |
| S002 | `Symbol not found` | A name is referenced but has no matching `Callee` in any parent scope | Declare the variable or function before use |
| S003 | `Invalid scope operation` | A scope was popped below the program scope (internal error) | File a bug report |

---

## Type Errors

| Code | Message | Cause | Fix |
|---|---|---|---|
| T001 | `Type mismatch` | A value of one type was assigned or passed where an incompatible type was expected | Check the types on both sides |
| T002 | `Cannot use plain struct as native type` | A plain `struct` was used as a `dynam` element type, parameter type, or in another native-type position | Use `typed struct` instead |
| T003 | `Untyped parameter` | A function or lambda parameter was declared without a type | Add an explicit type or use `auto` |
| T004 | `Invalid use of deprecated keyword` | `restrict`, `_Bool`, `_Complex`, or `_Imaginary` was used as a type | Remove the deprecated type |
| T005 | `Typed / Worded in source file` | `Typed` or `Worded` appeared in a `.ctri` file outside of a `typedef` context | Move to a `.plib` file, or use `typedef` |

---

## Memory Errors

| Code | Message | Cause | Fix |
|---|---|---|---|
| M001 | `free of non-heap variable` | `free` was called on a stack variable | Remove the `free` |
| M002 | `free of autoremove variable` | `free` was called on an `autoremove`-managed pointer | Remove the `free` — the compiler handles it |
| M003 | `double free` | A pointer was freed more than once | Track ownership carefully; consider `autoremove` |
| M004 | `autoremove on non-allocate variable` | `autoremove` was applied to a stack variable | Only use `autoremove` with `allocate` |
| M005 | `use after free` | An `autoremove` pointer was used after its last-use point (static analysis only) | Move the use before the last-use point, or restructure the code |

---

## Assembly Errors

| Code | Message | Cause | Fix |
|---|---|---|---|
| A001 | `Missing syntax target` | An `asm` block does not begin with a syntax target declaration | Add `syntax_x86_64_linux` (or another valid target) as the first statement |
| A002 | `Unknown syntax target` | The syntax target string is not one of the supported targets | Use a supported target — see `assembly.md` |
| A003 | `asm in disallowed position` | An `asm` block appeared inside a struct body or other disallowed position | Move the `asm` block to file scope or a namespace |
| A004 | `NASM assembly error` | NASM returned an error assembling the emitted `.asm` file | Check the assembly instructions in the `asm` block |

---

## Import and Scope Errors

| Code | Message | Cause | Fix |
|---|---|---|---|
| I001 | `Library not found` | A `using x from <lib>` or `using x from "lib"` could not locate the library | Check the library name and search paths |
| I002 | `Symbol not exported` | A symbol named in `using` does not exist in the target library | Check the library's exported symbols |
| I003 | `Circular import` | Two files import each other | Refactor shared code into a third library |
| I004 | `main in .plib file` | A `.plib` library file defines a `main` function | Remove `main` from the library or rename it |
| I005 | `namespace in .ctri file` | The `namespace`/`space` keyword was used outside a `.plib` file | Move namespace declarations to a `.plib` file |

---

## Runtime Errors (plstd)

These are produced at runtime by the `plstd` runtime. Each has a random personality message selected from `errors/<type>/`.

| Error type | Trigger |
|---|---|
| `out_of_bounds` | Index into `dynam` or `tuple` is ≥ `len` or < 0 |
| `null_deref` | A `NULL` pointer was dereferenced |
| `type_mismatch` | An `auto` runtime type check failed |
| `alloc_fail` | `allocate` returned `NULL` (out of memory) |
| `free_invalid` | `free` reached a pointer with an invalid heap header |

---

## Contributing Error Personalities

Error personality messages are community-contributed. Each error type has a folder in `errors/` containing one or more `.txt` files. Each line in a `.txt` file is a candidate message.

To add new personalities:

1. Find the relevant subfolder in `errors/` (e.g. `errors/out_of_bounds/`).
2. Add a new `.txt` file or append lines to an existing one.
3. One message per line. Keep messages concise — one sentence maximum.
4. Open a pull request against the `main` branch.

See `contributing.md` for the full contribution workflow.
