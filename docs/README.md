# C△ Language Reference

<p align="center">
  <img src="../assets/logo.png" alt="C△ Logo" width="180"/>
</p>

Welcome to the official documentation for the **C△ (C Triangle)** programming language and the **Hypotenuse Compiler**. 🔺

---

## Documents

| File | Description |
|---|---|
| [keywords.md](keywords.md) | Full keyword and operator reference |
| [syntax.md](syntax.md) | Complete syntax guide with examples |
| [types.md](types.md) | Type system — primitives, auto, string, dynam, tuple, structs |
| [memory.md](memory.md) | Memory model — allocate, free, autoremove, robbery |
| [assembly.md](assembly.md) | Inline assembly — asm blocks, syntax targets, rules |
| [stdlib.md](stdlib.md) | Standard library (plstd) — printd, printfs, len, error handling |
| [compiler.md](compiler.md) | Compiler architecture, pipeline stages, and CLI reference |
| [errors.md](errors.md) | Error reference — all compiler and runtime errors |
| [contributing.md](contributing.md) | Contributing guide — workflow, style, tests, error personalities |

---

## About C△

C△ is a systems programming language that extends C11 with modern features while maintaining 100% C11 compatibility (minus a small deprecated list). It compiles to C and assembly, using GCC and NASM to produce native Linux ELF x86_64 binaries.

C△ is designed around three principles:

- **Explicit over implicit** — nothing happens without you knowing about it
- **Simple over clever** — clean syntax that stays close to C's spirit
- **Extensible over fixed** — the language can grow itself through libraries

The compiler is called **The Hypotenuse Compiler** and is available at:
https://github.com/setuser1/The-Hypotenuse-Compiler
