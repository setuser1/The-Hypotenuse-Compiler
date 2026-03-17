# C△ Memory Model

This document describes every memory management mechanism in C△: stack allocation, heap allocation via `allocate`, automatic deallocation via `autoremove`, manual deallocation via `free`, and the robbery ownership-transfer pattern.

---

## Stack Allocation

Ordinary variable declarations allocate on the stack. This is identical to C11 behaviour.

```c
int x = 5;             // stack
char[64] buffer;       // stack, fixed size
Vec3 v(1.0, 2.0, 3.0); // stack, typed struct
```

Stack variables are valid for the lifetime of their enclosing scope. No explicit deallocation is needed or possible.

---

## Heap Allocation — `allocate`

`allocate` requests memory from the heap. It replaces `malloc`/`calloc` for the common case and produces a typed pointer.

### Syntax

```
allocate type name
allocate type name [size]
```

| Form | Description |
|---|---|
| `allocate int x` | Allocate one `int` on the heap |
| `allocate int buf [256]` | Allocate 256 `int`s on the heap |
| `allocate string msg` | Allocate one `string` on the heap |

### Examples

```c
allocate int counter;
counter = 0;

allocate float matrix [16];
matrix[0] = 1.0;
```

The allocated variable is a typed pointer. All pointer operations (`*`, `->`, `[]`) apply.

---

## Manual Deallocation — `free`

`free` releases heap memory previously created with `allocate`. It is the programmer's responsibility to call `free` before the pointer goes out of scope whenever `autoremove` is not used.

```c
allocate int buf [256];
buf[0] = 42;
free buf;
```

Calling `free` on a stack variable is a compiler error. Calling `free` on an `autoremove` variable is also a compiler error — the simulation pass manages its lifetime.

---

## Automatic Deallocation — `autoremove`

`autoremove` marks a heap-allocated pointer for automatic deallocation. The compiler's simulation pass identifies the last use of the pointer in the control flow and inserts a `free` immediately after that point. The programmer writes no explicit `free`.

### Syntax

```
autoremove allocate type* name = &existing
```

### Example

```c
int x = 10;
autoremove allocate int* ptr = &x;

printf("%d\n", *ptr);    // use 1
int y = *ptr + 5;        // use 2 — last use, free inserted here by compiler

// ptr is no longer valid below this point
```

### Rules

- `autoremove` is only valid on variables created with `allocate`.
- The simulation pass performs a single forward scan over the Callee/Caller graph to find last use.
- If a pointer is conditionally used inside a branch, the `free` is inserted after the outermost enclosing statement that could be the last use — conservatively late.
- `autoremove` pointers must not be assigned to another variable without using the robbery pattern (see below). Doing so would leave two names referring to the same allocation after one of them is freed.

---

## Robbery — Ownership Transfer

Robbery is C△'s mechanism for transferring ownership of an `autoremove` pointer to another variable. The receiving variable "robs" the pointer of its allocation and takes over its memory.

### Syntax

```c
allocate type* receiver = &donor;
```

When `donor` is an `autoremove` pointer, assigning its address to a new variable via `&donor` transfers ownership:

- `donor` is invalidated — it no longer owns the allocation.
- `receiver` becomes a plain (non-`autoremove`) variable holding the same heap address.
- No `free` is inserted for `donor` at its last use because ownership has moved.
- No `free` is needed for `receiver` — it is now a plain variable and its lifetime is managed manually if needed, or it simply goes out of scope.

### Example

```c
int x = 42;
autoremove allocate int* ptr = &x;

// ptr owns the allocation
allocate int* keeper = &ptr;    // robbery — keeper takes ownership

// ptr is now invalid
// keeper holds the allocation as a plain variable — no free needed
printf("%d\n", *keeper);
```

### Why Robbery Exists

Robbery solves the problem of moving heap data across scope boundaries without forcing the programmer to drop down to manual `free` everywhere. It is a deliberate, visible ownership transfer — explicit over implicit, in the spirit of C△'s design principles.

---

## Summary Table

| Pattern | Allocation | Deallocation |
|---|---|---|
| Plain variable | Stack | Automatic at scope exit |
| `allocate` | Heap | Manual via `free` |
| `autoremove allocate` | Heap | Automatic via simulation pass at last use |
| Robbery (`&ptr`) | Inherited heap | None — plain variable after transfer |

---

## Memory Safety Notes

- The compiler does not currently perform use-after-free detection beyond what the simulation pass enforces for `autoremove` variables. Treat `free`d pointers as immediately invalid.
- Double-free on an `autoremove` pointer is a compiler error.
- Robbery from a non-`autoremove` pointer is undefined — only rob `autoremove` allocations.
- C `malloc` / `calloc` / `free` are available for low-level code that needs them. C△ memory keywords and raw C memory functions can coexist in the same file.
