# The Hypotenuse Compiler

<p align="center">
  <img src="assets/logo.png" alt="C△ Logo"/>
</p>

## What is C△?

Hypotenuse is the compiler for **C△ (C Triangle)** — a new systems programming language born out of frustration with C's lack of features and C++'s overwhelming complexity.

C△ compiles to **C + assembly**, uses **GCC and NASM**, and targets **Linux ELF x86_64** natively. It's C-compatible, kinda modern? And designed to be learnable.

> _The future of C and the end of C++_

---

## Supported Architectures

The C△ compiler and standard library support multiple architectures:

| Architecture | Platform | Format   | Status  |
| ------------ | -------- | -------- | ------- |
| **x86_64**   | Linux    | ELF64    | Partial |

---

### Standard Library (plstd) Architecture Support

- **printd.plib** — Type-aware printing with conditional compilation for both x86_64 Linux
- **string.plib** — String operations (strcmp, strcpy, strcat, etc.) optimized for each architecture
- **streamer.plib** — File I/O and syscall wrappers supporting both architectures
- **Syscalls** — All syscalls use platform-specific conventions:
  - x86_64: Linux syscall ABI (`mov rax, N; syscall`)

---

## Install Guide

1. Make sure you have **Linux** and **Python 3.14+**
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

### Using Apple's `container` CLI on macOS (ARM64)

For macOS users with Apple Silicon, you can use Apple's native `container` CLI instead of Docker to build and run the C△ compiler. The `container` tool is optimized for Apple Silicon and provides native virtualization.

#### Installation

Install the `container` CLI by downloading the latest signed installer package from the [GitHub release page](https://github.com/apple/container/releases). After installation, start the system service:

```bash
container system start
```

#### Building the Compiler

Use `make container-build` to build the compiler using Apple's `container` CLI:

```bash
make container-build
```

This will create `hypotenuse-container` in the `dist/` directory.

#### Running the Compiler

Use `make container-run` to run the compiler inside the container:

```bash
make container-run test/baseline.ctri
```

Or run a specific test file:

```bash
make container-run test/baseline.ctri -p
```

#### Running Tests

Use `make container-test` to run the full test suite inside the container:

```bash
make container-test
```

#### Linting

Use `make container-lint` to run linting checks inside the container:

```bash
make container-lint
```

---

## Documentation

Full language and compiler documentation lives in the [`docs/`](docs/) folder.

Detailed online documentation is available at:
<https://hypotenuse.mintlify.app>

---

## Contributing

See [`contributing.md`](contributing.md) to get involved!
