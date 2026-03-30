# C△ Inline Assembly

<p align="center">
  <img src="../assets/logo.png" alt="C△ Logo" width="120"/>
</p>

C△ supports **inline assembly blocks** via the `asm` keyword. Each `asm` block is compiled to a separate `.asm` file, assembled with NASM, and linked into the final binary.

---

## Syntax

```c
asm functionName(params) {
    // x86_64 Linux assembly
    syntax x86_64_linux
}
```

- The **function name** is the label.
- **Parameters** use native C△ type declarations instead of assembler directives.
- syntax describes what syntax is being used
- `return` replaces `ret` — implicit return defaults to `rax` on x86_64.
- Each `asm` block becomes its **own `.asm` file**.

---

## Example — Add Two Integers

```c
asm int addInts(int a, int b) {
    syntax x86_64_linux
    section .text
    mov rax, a
    mov rbx, b
    add rax, rbx
    return       // returns rax
}
```

Call it just like a normal function:

```c
int result = addInts(3, 7);   // result = 10
```

---

## Example — Raw Syscall

```c
asm void exitProcess(int code) {
    mov rax, 60    // sys_exit
    mov rdi, code
    syscall
}
```

---

## Target

| Property | Value |
|---|---|
| Architecture | x86_64 |
| Platform | Linux |
| Syntax | NASM (Intel syntax) |
| Output | ELF object file per asm block |

---

## Rules

- `asm` blocks are **opaque** to the simulation pass — no last-use analysis inside them
- The function name becomes the **global label** in the `.asm` file
- Do not use assembler directives (`db`, `dw`, `section`, etc.) — use C△ declarations instead
- Use `return` instead of `ret`
- `asm` functions are assembled with NASM and linked by GCC

---

## Linking

The compiler pipeline handles everything automatically:

```
.ctri source
  └──▶ code gen  ──▶  .c file  ──▶  GCC
  └──▶ asm blocks ──▶  .asm files  ──▶  NASM  ──▶  GCC linker  ──▶  binary
```
