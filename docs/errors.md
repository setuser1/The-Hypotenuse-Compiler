# C△ Error Reference

<p align="center">
  <img src="../assets/logo.png" alt="C△ Logo" width="120"/>
</p>

This document covers all compiler and runtime errors produced by the Hypotenuse Compiler. C△ errors include **personality messages** — randomized, community-contributed flavor text that makes errors a little more human.

---

## Syntax Errors

Raised by the **parser** when the token stream doesn't match expected grammar.

| Error | Cause | Example |
|---|---|---|
| `Unexpected token at top-level` | Unknown token outside a function | `@foo` at file root |
| `Expected IDENTIFIER` | Type keyword not followed by a name | `int 42` |
| `Expected RPAREN` | Unclosed function call or for-loop header | `foo(1, 2` |
| `Expected SEMICOLON` | Missing `;` | `int x = 5` |
| `Unexpected end of file` | Unclosed `{` block | Missing `}` |
| `Unexpected token in primary expression` | Invalid token in an expression | `int + 3` |

---

## Deprecated Keyword Errors

Raised immediately when a deprecated C11 keyword is encountered.

| Keyword | Message |
|---|---|
| `restrict` | `Deprecated keyword used! Please remove or replace the keyword. Found 'RESTRICT'.` |
| `_Bool` | `Deprecated keyword used! Please remove or replace the keyword. Found 'BOOLEAN'.` |

---

## Scope Errors

Raised by the **structurer** when the scope graph detects conflicts.

| Error | Cause |
|---|---|
| `Child named X already exists in scope Y` | Duplicate variable/function declaration in the same scope |

---

## Memory Errors

Raised by the **simulation pass**.

| Error | Cause |
|---|---|
| `callee not found` | A function call references an undefined callee |
| `Use after autoremove drop` | Accessing a pointer after its `autoremove` free |
| `Invalid robbery` | Robbery target is not a valid `autoremove` pointer |

---

## File Errors

| Error | Cause |
|---|---|
| `Error: file not found <path>` | Source file does not exist |
| `Error reading file: <details>` | OS-level file read failure |

---

## Debugging Tips

- Run with `-t` to see the full token stream and scope graph before errors hit.
- Check for unclosed `{` braces — the most common cause of EOF errors.
- Remember that `for` loop init declarations are scoped to the loop, not the enclosing function.
