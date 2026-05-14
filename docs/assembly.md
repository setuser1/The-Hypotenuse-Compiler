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
    section .text
}
```

- The **function name** is the label.
- **Parameters** use native C△ type declarations instead of assembler directives.
- syntax describes what syntax is being used
- Every `asm` block must explicitly declare its text section for the selected syntax.
  Use `section .text` for x86_64 NASM targets and `.section __TEXT,__text` for `arm64_macho`.
- `return;` emits `ret`; `return expr;` moves the expression result to `rax` on x86_64 or `x0` on ARM64 before returning.
- Variable declarations inside `asm` blocks may omit semicolons; newlines terminate ASM declarations and instructions.
- Each `asm` block becomes its **own `.asm` file**.

---

## Example — Add Two Integers

```c
asm int addInts(int a, int b) {
    syntax x86_64_linux
    section .text
    int scratch = 0
    return a + b
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
    syntax x86_64_elf
    section .text
    mov rax, 60    // sys_exit
    mov rdi, code
    syscall
}
```

---

## Target

| Property     | Value                         |
| ------------ | ----------------------------- |
| Architecture | x86_64                        |
| Platform     | Linux                         |
| Syntax       | NASM (Intel syntax)           |
| Output       | ELF object file per asm block |

---

## Rules

- `asm` blocks are **opaque** to the simulation pass — no last-use analysis inside them
- The function name becomes the **global label** in the `.asm` file
- Do not use assembler data directives (`db`, `dw`, etc.) — use C△ declarations instead
- Text section directives are mandatory; data storage can still be represented with C△ variable declarations
- Use `return;` instead of `ret`, or `return expr;` for simple integer and floating-point return values
- Variables declared in bare `asm { }` blocks are registered in the surrounding scope; variables declared in `asm` functions are registered for import access and in the function scope
- `asm` functions are assembled with NASM and linked by GCC

---

## Linking

The compiler pipeline handles everything automatically:

```
.ctri source
  └──▶ code gen  ──▶  .c file  ──▶  GCC
  └──▶ asm blocks ──▶  .asm files  ──▶  NASM  ──▶  GCC linker  ──▶  binary
```
