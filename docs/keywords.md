# C△ Keyword Reference

<p align="center">
  <img src="../assets/logo.png" alt="C△ Logo" width="120"/>
</p>

This document lists all keywords in C△, their purpose, and basic usage. Keywords marked "_Removed_" are **deprecated** from C11 and will cause a compiler error if used.

---

## Type Keywords

| Keyword    | Description                      |
| ---------- | -------------------------------- |
| `int`      | Signed integer                   |
| `char`     | Single character / byte          |
| `float`    | Single-precision float           |
| `double`   | Double-precision float           |
| `void`     | No type / no return              |
| `short`    | Short integer                    |
| `long`     | Long integer                     |
| `signed`   | Explicitly signed integer        |
| `unsigned` | Unsigned integer                 |
| `string`   | _NEW_ First-class string type    |
| `auto`     | _NEW_ Dynamic / inferred type    |
| `dynam`    | _NEW_ Dynamic array              |
| `tuple`    | _NEW_ Dynamic heterogeneous list |

---

## Structure Keywords

| Keyword   | Description                         |
| --------- | ----------------------------------- |
| `struct`  | Plain struct (no inheritance)       |
| `space`   | _NEW_ Library namespace declaration |
| `typed`   | Typed struct (with inheritance)     |
| `typedef` | C11 type alias                      |
| `union`   | C11 union                           |
| `enum`    | C11 enumeration                     |

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
| `allocate`   | _NEW_ Heap allocation (`allocate type name [size]`)  |
| `free`       | Manual heap deallocation                             |
| `autoremove` | _NEW_ Heap alloc freed at last use (simulation pass) |

---

## Module / Import Keywords

| Keyword | Description                            |
| ------- | -------------------------------------- |
| `using` | _NEW_ Import a symbol from a library   |
| `show`  | _NEW_ Globalize a library or namespace |
| `lib:`  | _NEW_ Explicit plstd access prefix     |

---

## Other Keywords

| Keyword    | Description                                 |
| ---------- | ------------------------------------------- |
| `asm`      | _NEW_ Inline assembly block                 |
| `lamb`     | _NEW_ Named lambda                          |
| `self`     | _NEW_ Optional struct self-reference        |
| `init`     | _NEW_ Struct constructor lifecycle function |
| `end`      | _NEW_ Struct destructor lifecycle function  |
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
| `restrict`             | _Removed_                  |
| `_Bool`                | _Removed_                  |
| `_Complex`             | _Removed_                  |
| `_Imaginary`           | _Removed_                  |
