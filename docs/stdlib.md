# C△ Standard Library (plstd)

<p align="center">
  <img src="../assets/logo.png" alt="C△ Logo" width="120"/>
</p>

**plstd** is the C△ standard library. It is implemented in C△ itself, with `asm` blocks only where syscalls or low-level primitives are needed.

---

## Importing plstd

```c
// Globalize all of plstd
show plstd

// Globalize one module
show lib:io

// Explicit access without globalizing
lib:printd(42);
```

> The compiler auto-imports what you use — manual imports are optional style.

---

## Output Functions

### `printd(value)` — Type-aware Print

Prints any value, auto-detecting its type.

```c
printd(42);           // prints: 42
printd("hello");      // prints: hello
printd(3.14);         // prints: 3.14
printd('A');          // prints: A
```

---

### `printfs(format, ...)` — Formatted / f-string Print

Supports `{expr}` f-string interpolation and `%`-style format specifiers.

```c
string name = "world";
int x = 42;

printfs("Hello, {name}!\n");       // Hello, world!
printfs("x = %d\n", x);           // x = 42
printfs("{x} squared = {x*x}\n"); // 42 squared = 1764
```

---

## Base Functions

### `len(collection)` — Length

Returns the length of strings, `dynam` arrays, and `tuple` collections.

```c
string s = "hello";
int l = len(s);        // l = 5

dynam int arr = [1, 2, 3];
int n = len(arr);      // n = 3

tuple t = [1, "hi", 3.14];
int t_len = len(t);    // t_len = 3
```

> `len()` is a **base function** — built into the language, not part of plstd.

---

## plstd Implementation

- Written entirely in base **C△** + `asm` blocks for syscalls
- Located in `PLIBS/` system path: `/usr/lib/PLIBS/`
- User libraries: `~/.local/lib/PLIBS/`
