# C△ Keyword Reference

<p align="center">
  <img src="../assets/logo.png" alt="C△ Logo" width="120"/>
</p>

This document lists all keywords in C△, their purpose, and basic usage. Keywords marked "_future_" are planned but not yet implemented.

---

## Type Keywords

| Keyword    | Description                         |
| ---------- | ----------------------------------- |
| `int`      | Signed integer                      |
| `char`     | Single character / byte             |
| `float`    | Single-precision float              |
| `double`   | Double-precision float              |
| `void`     | No type / no return                 |
| `short`    | Short integer                       |
| `long`     | Long integer                        |
| `signed`   | Explicitly signed integer           |
| `unsigned` | Unsigned integer                    |
| `string`   | First-class string type             |
| `auto`     | Dynamic / inferred type             |
| `dynam`    | Dynamic array                       |
| `tuple`    | Dynamic heterogeneous list          |

---

## Structure Keywords

| Keyword   | Description                              |
| --------- | ---------------------------------------- |
| `struct`  | Plain struct (no inheritance)            |
| `space`   | Library namespace declaration            |
| `typed`   | Typed struct (with inheritance)          |
| `typedef` | C11 type alias                           |
| `union`   | C11 union                                |
| `enum`    | C11 enumeration                          |

---

## Control Flow

| Keyword                       | Description              |
| ----------------------------- | ------------------------ |
| `if` / `else`                 | Conditional branching    |
| `while`                       | While loop               |
| `for`                         | For loop                 |
| `do`                          | Do-while loop            |
| `switch` / `case` / `default` | Switch statement         |
| `break`                       | Break out of loop/switch |
| `continue`                    | Skip to next iteration   |
| `return`                      | Return from function     |
| `goto`                        | C11 goto                 |

---

## Memory Keywords

| Keyword      | Description                                          |
| ------------ | ---------------------------------------------------- |
| `allocate`   | Heap allocation (`allocate type name [size]`)        |
| `free`       | Manual heap deallocation                             |
| `autoremove` | Heap alloc freed at last use (simulation pass)       |

---

## Module / Import Keywords

| Keyword     | Description                               |
| ----------- | ----------------------------------------- |
| `using`     | Import a symbol from a library            |
| `expose`    | Globalize a library or namespace          |
| `@`         | Explicit namespace access operator        |
| `overwrite` | Overwrite base syntax with library syntax |

---

## Other Keywords

| Keyword    | Description                                 |
| ---------- | ------------------------------------------- |
| `asm`      | Inline assembly block                       |
| `lamb`     | Named lambda                                |
| `self`     | Optional struct self-reference              |
| `init`     | Struct constructor lifecycle function       |
| `end`      | Struct destructor lifecycle function        |
| `sizeof`   | C11 size operator                           |
| `const`    | Constant qualifier                          |
| `volatile` | Volatile qualifier                          |
| `static`   | Static storage                              |
| `extern`   | External linkage                            |
| `inline`   | Inline hint                                 |
| `register` | Register hint                               |

---

## Deprecated Keywords

These C11 keywords are **not supported** in C△ and will raise a `SyntaxError`:

| Keyword                | Reason                     |
| ---------------------- | -------------------------- |
| `auto` _(C11 meaning)_ | Repurposed as dynamic type |
| `restrict`             | _REMOVED_                  |
| `_Bool`                | _REMOVED_                  |
| `_Complex`             | _REMOVED_                  |
| `_Imaginary`           | _REMOVED_                  |
