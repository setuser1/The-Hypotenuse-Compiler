# C△ Inline Assembly

This document describes the `asm` keyword, the syntax target declaration, supported platforms, and the rules that govern assembly blocks in C△.

---

## Overview

C△ provides first-class assembly support via the `asm` keyword. An `asm` block defines a named assembly function that is compiled to a separate `.asm` file by the code generator, assembled by NASM, and linked into the final binary alongside the C-compiled output.

Assembly blocks are the foundation of `plstd` — every syscall and hardware-level primitive in the standard library is implemented using `asm`.

---

## Declaring an Assembly Function

```c
asm return_type funcname(param_list) {
    syntax_target

    // NASM instructions
    return (return_option if specified)
}
```

### Components

| Component | Description |
|---|---|
| `asm` | Keyword that opens an assembly function block |
| `return_type` | The C△ return type of the function (`int`, `void`, `auto`, etc.) |
| `funcname` | The function name — this becomes the NASM label and the C△ callable name |
| `param_list` | Typed parameters — same syntax as regular C△ functions |
| `syntax_target` | First line inside the block — declares the assembly syntax and ABI target |
| `return` | Replaces `ret` — the code generator inserts the correct return instruction |

---

## Syntax Targets

The syntax target declaration is the first statement inside every `asm` block. It specifies the instruction set, ABI, and object format.

| Target | Platform | Object format | ABI |
|---|---|---|---|
| `syntax_x86_64_linux` | Linux | ELF64 | System V AMD64 |
| `syntax_x86_64_windows` | Windows | PE64 | Microsoft x64 |
| `syntax_x86_64_macos` | macOS | Mach-O 64 | System V AMD64 |

Currently only `syntax_x86_64_linux` is a production target. The others are declared for future support.

---

## Examples

### Simple arithmetic

```c
asm int add_one(int x) {
    syntax_x86_64_linux

    .section text
    mov rax, x
    add rax, 1
    return
}
```

`return` at the end of the block causes the code generator to emit `ret`. The implicit return register on x86_64 is `rax`.

### Syscall wrapper

```c
asm void sys_write(int fd, string buf, int len) {
    syntax_x86_64_linux

    .section text
    mov rax, 1          ; syscall: write
    mov rdi, fd
    mov rsi, buf
    mov rdx, len
    syscall
    return
}
```

### Void function (no return value)

```c
asm void halt() {
    syntax_x86_64_linux

    .section text
    mov rax, 60         ; syscall: exit
    xor rdi, rdi
    syscall
    return
}
```

---

## Parameters

Parameters in `asm` functions follow the same declaration syntax as regular C△ functions — every parameter must have a declared type.

```c
asm int multiply(int a, int b) {
    syntax_x86_64_linux

    .section text
    mov rax, a
    imul rax, b
    return
}
```

The compiler maps each named parameter to its position in the calling convention. Under `syntax_x86_64_linux`, integer arguments arrive in `rdi`, `rsi`, `rdx`, `rcx`, `r8`, `r9` in order. The code generator resolves named parameter references to the appropriate register or stack slot.

---

## Variables Inside Assembly Blocks

Native C△ variable declarations can appear inside an `asm` block instead of assembler directives like `db` or `dq`. The code generator translates them to the appropriate NASM declarations.

```c
asm int example() {
    syntax_x86_64_linux
    .section data
    int local = 0       ; declares a dword in .bss or .data

    .section text
    mov eax, local
    return
}
```

---

## Return Behaviour

- `return` inside an `asm` block emits `ret`.
- If no explicit `return` is written, the block falls off the end — the code generator does **not** insert an implicit `ret`. Always write an explicit `return`.
- The implicit return value is whatever is in `rax` at the point `return` is reached, consistent with the System V AMD64 ABI.

---

## Assembly code blocks

- code blocks act the same as functions but they are blocks of code, lacking the usual return a function would have
```c
asm {
    syntax_x86_64_linux

    .section text
    add x,y // uses variable x and y from the parent scope
}
```

---

## Compilation Pipeline for `asm` Blocks

```
.ctri source
    │
    ▼  (code generator)
 block_funcname.asm       one .asm file per asm block
    │
    ▼  nasm -f elf64 block_funcname.asm -o block_funcname.o
 block_funcname.o
    │
    └──► linked with all other .o files into final binary
```

The function name is the NASM label. No `global` directive is needed in the source — the code generator inserts it automatically.

---

## Rules and Restrictions

- Every `asm` block must begin with a syntax target declaration as its first statement.
- All parameters must have declared types — bare untyped parameters are not allowed.
- `return` replaces `ret` everywhere inside `asm` blocks.
- Each `asm` block is compiled to exactly one `.asm` file. Multiple `asm` blocks in the same `.ctri` file produce multiple `.asm` files.
- `asm` blocks must follow all rules of the declared syntax target — invalid instructions for the target are NASM errors.
- The `asm` keyword can appear at file scope or inside a `namespace`/`space` block but not inside a plain `struct` or `typed struct` body.
