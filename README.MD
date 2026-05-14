# The Hypotenuse Compiler

<p align="center">
  <img src="assets/logo.png" alt="C△ Logo"/>
</p>

## What is C△?

Hypotenuse is the compiler for **C△ (C Triangle)** — a new systems programming language born out of frustration with C's featurelessness and C++'s overwhelming complexity. A middle ground had to be born!

C△ compiles to **C + assembly**, uses **GCC and NASM**, and targets **Linux ELF x86_64** natively. It's C-compatible, modern, and designed to be learnable.

> *The future of C and the end of C++*

---

## Supported Architectures

The C△ compiler and standard library support multiple architectures:

| Architecture | Platform | Format | Status |
|---|---|---|---|
| **x86_64** | Linux | ELF64 | ✓ Fully Supported |
| **ARM64** | macOS | Mach-O64 | ✓ Fully Supported |

### Standard Library (plstd) Architecture Support

- **printd.plib** — Type-aware printing with conditional compilation for both x86_64 Linux and ARM64 macOS
- **string.plib** — String operations (strcmp, strcpy, strcat, etc.) optimized for each architecture
- **streamer.plib** — File I/O and syscall wrappers supporting both architectures
- **Syscalls** — All syscalls use platform-specific conventions:
  - x86_64: Linux syscall ABI (`mov rax, N; syscall`)
  - ARM64: macOS syscall ABI (`mov x16, N; svc #0x80`)

---

## Install Guide

1. Make sure you have **Linux or MacOS** and **Python 3.14+**
2. Clone the repo and `cd` into it
3. Run `make full-install`

```bash
git clone https://github.com/setuser1/The-Hypotenuse-Compiler
cd The-Hypotenuse-Compiler
make full-install
```

To build the compiler as a Linux x86_64 ELF binary from an ARM64 host, install Docker and run:

```bash
make build-x86_64-elf
make full-install-x86_64-elf
```

---

## Documentation

Full language and compiler documentation lives in the [`docs/`](docs/) folder.

---

## Contributing

See [`contributing.md`](contributing.md) to get involved!
