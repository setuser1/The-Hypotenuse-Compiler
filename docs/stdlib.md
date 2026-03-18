# C△ Standard Library/Plus Standard (`plstd`)

This document describes the C△ standard library, referred to as `plstd`. It covers how to access the library, what modules it contains, and the API of every provided function.

---

## Overview

`plstd` is the C△ standard library. It is implemented entirely in C△ using `asm` blocks for syscalls and hardware primitives. It is a single flat library — not split into separately compiled modules — but its internal code is organised into logical sections.

`plstd` is linked automatically whenever a symbol it defines is used. No explicit `-l` flag or `using` statement is required, though `using` is available as an optional style choice.

---

## Accessing `plstd`

### Explicit access via `lib:` prefix

```c
lib:printd("hello");
lib:printfs("x is {x}");
```

### Optional explicit import

```c
using printd from <plstd>;
lib:printd("hello");
```

### Globalize all of `plstd`

```c
show plstd;
printd("hello");    // no prefix needed
```

### Globalize one symbol

```c
show lib:printd;
printd("hello");
```

Once `show plstd` is written, all `plstd` symbols are available without a prefix for the remainder of the file.

---

## Output Functions

### `printd`

Type-aware print. Accepts any C△ type and prints a human-readable representation followed by a newline. No format string is required.

```
void printd(auto value)
```

| Argument type | Output |
|---|---|
| `int`, `short`, `long` | Decimal integer |
| `float`, `double` | Decimal float |
| `char` | Single character |
| `string` | String contents |
| `dynam` | `[element, element, …]` |
| `tuple` | `(element, element, …)` |
| `auto` | Resolved at runtime via type tag |

**Examples:**

```c
printd(42);                 // 42
printd(3.14);               // 3.14
printd("hello");            // hello
printd([1, 2, 3]);          // [1, 2, 3]
printd((1, "a", 2.0));      // (1, a, 2.0)
```

---

### `printfs`

F-string print. Expressions inside `{}` are evaluated at the call site and interpolated into the output string. A newline is appended.

```
void printfs(string template)
```

```c
string name = "world";
int x = 42;
printfs("Hello {name}!");          // Hello world!
printfs("x squared is {x * x}");   // x squared is 1764
printfs("type: {auto_var}");        // type: <runtime resolved>
```

Any valid C△ expression is permitted inside `{}`. The expression is evaluated in the scope where `printfs` is called.

---

## Length Function

### `len()`

Built-in function returning the logical length of a collection or string. Implemented as a compiler intrinsic backed by `plstd` for types that carry runtime metadata.

```
int len(string s)
int len(dynam arr)
int len(tuple t)
int len(char[n] buf)     // returns n
int len(int x)           // number of decimal digits
```

```c
len("hello")            // 5
len([1, 2, 3])          // 3
len(42)                 // 2
len(1000)               // 4
```

---

## Error Handling

Runtime errors produced by `plstd` are printed to stderr with a message drawn from the active error personality. Error personalities are community-contributed text files stored in the `errors/` folder of the compiler repository.

Each error type has its own personality file. When the compiler is built, the personality set is compiled in. At runtime, a random personality message is selected for each error type.

**Error types include:**

| Error | Trigger |
|---|---|
| Out-of-bounds access | `dynam` or `tuple` index ≥ `len` |
| Null dereference | Accessing a `NULL` pointer |
| Type mismatch | Runtime `auto` type check failure |
| Allocation failure | `allocate` returns `NULL` |
| Free of non-heap | `free` called on stack variable |

See `errors.md` for the full error reference.

---

## Planned `plstd` Additions (LAST STAGES WHEN COMPLETE)

The following are planned for future development stages.

| Symbol | Description |
|---|---|
| `readln()` | Read a line from stdin into a `string` |
| `itoa(int)` | Convert integer to `string` |
| `atoi(string)` | Convert `string` to integer |
| `open(string, string)` | Open a file — wrapper around `sys_open` |
| `close(int)` | Close a file descriptor |
| `read(int, auto, int)` | Read from file descriptor |
| `write(int, auto, int)` | Write to file descriptor |
| `exit(int)` | Exit the process with a status code |

All future `plstd` functions are implemented in C△ with `asm` blocks only where a syscall is required — no C code inside the standard library.
