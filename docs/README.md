# C△ Language Reference

This folder contains the official documentation for the C△ (C Triangle) programming language.

---

## Documents

| File | Description |
|---|---|
| [keywords.md](keywords.md) | Full keyword and operator reference |
| [syntax.md](syntax.md) | Complete syntax guide with examples |
| [memory.md](memory.md) | Memory model, allocate, autoremove, and robbery |
| [structs.md](structs.md) | Structs, typed structs, constructors, and inheritance |
| [assembly.md](assembly.md) | Native assembly blocks and functions |
| [imports.md](imports.md) | Import system, using, show, namespaces, and plstd |
| [stdlib.md](stdlib.md) | Standard library (plstd) reference |
| [compiler.md](compiler.md) | Compiler pipeline and internals |

---

## About C△

C△ is a systems programming language that extends C11 with modern features while maintaining 100% C11 compatibility (minus a small deprecated list). It compiles to C and assembly, using GCC and NASM to produce native Linux ELF x86_64 binaries.

C△ is designed around three principles:

- **Explicit over implicit** — nothing happens without you knowing about it
- **Simple over clever** — clean syntax that stays close to C's spirit
- **Extensible over fixed** — the language can grow itself through libraries

The compiler is called **The Hypotenuse Compiler** and is available at:
https://github.com/setuser1/The-Hypotenuse-Compiler
