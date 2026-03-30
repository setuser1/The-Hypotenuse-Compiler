# C△ Keyword Reference

<p align="center">
  <img src="../assets/logo.png" alt="C△ Logo" width="120"/>
</p>

This document lists all keywords in C△, their purpose, and basic usage. Keywords marked "*Removed*" are **deprecated** from C11 and will cause a compiler error if used.

---

## Type Keywords

| Keyword | Description |
|---|---|
| `int` | Signed integer |
| `char` | Single character / byte |
| `float` | Single-precision float |
| `double` | Double-precision float |
| `void` | No type / no return |
| `short` | Short integer |
| `long` | Long integer |
| `signed` | Explicitly signed integer |
| `unsigned` | Unsigned integer |
| `string` | *NEW* First-class string type |
| `auto` | *NEW* Dynamic / inferred type |
| `dynam` | *NEW* Dynamic array |
| `tuple` | *NEW* Dynamic heterogeneous list |

---

## Structure Keywords

| Keyword | Description |
|---|---|
| `struct` | Plain struct (no inheritance) |
| `space` | *NEW* Library namespace declaration |
| `typedef` | C11 type alias |
| `union` | C11 union |
| `enum` | C11 enumeration |

---

## Control Flow

| Keyword | Description |
|---|---|
| `if` / `else` | Conditional branching |
| `while` | While loop |
| `for` | For loop |
| `do` | Do-while loop |
| `switch` / `case` / `default` | Switch statement |
| `break` | Break out of loop/switch |
| `continue` | Skip to next iteration |
| `return` | Return from function |
| `goto` | C11 goto |

---

## Memory Keywords

| Keyword | Description |
|---|---|
| `allocate` | *NEW* Heap allocation (`allocate type name [size]`) |
| `free` | Manual heap deallocation |
| `autoremove` | *NEW* Heap alloc freed at last use (simulation pass) |

---

## Module / Import Keywords

| Keyword | Description |
|---|---|
| `using` | *NEW* Import a symbol from a library |
| `show` | *NEW* Globalize a library or namespace |
| `lib:` | *NEW* Explicit plstd access prefix |

---

## Other Keywords

| Keyword | Description |
|---|---|
| `asm` | *NEW* Inline assembly block |
| `lamb` | *NEW* Named lambda |
| `self` | *NEW* Optional struct self-reference |
| `init` | *NEW* Struct constructor lifecycle function |
| `end` | *NEW* Struct destructor lifecycle function |
| `sizeof` | C11 size operator |
| `const` | Constant qualifier |
| `volatile` | Volatile qualifier |
| `static` | Static storage |
| `extern` | External linkage |
| `inline` | Inline hint |
| `register` | Register hint |

---

## Deprecated Keywords

These C11 keywords are **not supported** in C△ and will raise a `SyntaxError`:

| Keyword | Reason |
|---|---|
| `auto` *(C11 meaning)* | Repurposed as dynamic type |
| `restrict` | *Removed* |
| `_Bool` | *Removed* |
| `_Complex` | *Removed* |
| `_Imaginary` | *Removed* |
