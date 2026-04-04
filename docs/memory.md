# C△ Memory Model

<p align="center">
  <img src="../assets/logo.png" alt="C△ Logo" width="120"/>
</p>

C△ gives you full control over memory while adding safer, more expressive tools on top of raw C heap management.

---

## Stack vs Heap

| Location | How                         | Notes                                      |
| -------- | --------------------------- | ------------------------------------------ |
| Stack    | Normal variable declaration | Freed automatically on scope exit          |
| Heap     | `allocate` keyword          | Must be freed manually or via `autoremove` |

---

## `allocate` — Heap Allocation

```c
// Allocate a single value
allocate int counter;

// Allocate an array of N elements
allocate int buffer[256];
allocate string names[10];
```

> `allocate type name(size)` — size is optional for single values. It reassigns their byte size.

---

## `free` — Manual Deallocation

```c
allocate int x;
x = 42;
free x;   // manually release
```

> Forgetting to `free` heap memory is a memory leak. Use `autoremove` to avoid this.

---

## `autoremove` — Automatic Heap Deallocation

`autoremove` allocates on the heap but the **simulation pass** tracks the last use of the variable and inserts a `free` automatically.

```c
autoremove allocate int buf[512];
// ... use buf ...
// free is inserted automatically after last use
```

> No runtime overhead — the free is inserted at compile time via static analysis.

---

## Robbery — Ownership Transfer

If an `autoremove` pointer **drops** and another pointer **takes its address**, the new pointer becomes a plain variable with no `free` needed.

```c
autoremove allocate int data[100];

// data is about to drop — 'backup' steals its memory
int* backup = &data;

// backup is now a plain heap variable
// data is gone — no double-free risk
```

> The compiler's simulation pass validates robbery to prevent use-after-free and double-free.

---

## Lifecycle Summary

```txt
[allocate]  →  [use]  →  [free]          ← manual
[autoremove allocate]  →  [use]  →  [auto-free at last use]  ← simulation pass
[autoremove]  →  [robbery]  →  [plain heap variable]  ← ownership transfer
```

---

## Rules & Gotchas

- Do not `free` an `autoremove` variable — the compiler handles it
- Do not access a pointer after its `autoremove` drop without robbery
- Robbery is validated at compile time — invalid transfers are caught
- The simulation pass runs before code generation — no runtime cost
