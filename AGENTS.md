# Apple Container Setup Guide

## Overview

This document describes how to use Apple's native `container` CLI to build and run the C△ (C Triangle) compiler on macOS systems with Apple Silicon. The `container` tool provides lightweight virtual machine virtualization specifically optimized for Apple Silicon, offering a native alternative to Docker.

## Prerequisites

- macOS with Apple Silicon (M1, M2, M3, or newer)
- macOS 26 or later
- The `container` CLI installed from https://github.com/apple/container/releases

After installation, start the system service:

```bash
container system start
```

## Build the Compiler with `container`

The C△ project includes dedicated Makefile targets for using Apple's `container` CLI:

### Build Targets

- `make container-build` — Builds the compiler using the native `container` CLI
- `make container-run` — Runs a compilation command inside the container
- `make container-test` — Runs the full test suite inside the container
- `make container-lint` — Runs linting checks inside the container

### Building the Compiler

Run `make container-build` to create the containerized compiler:

```bash
make container-build
```

This command will:

1. Create a lightweight container VM optimized for Apple Silicon
2. Install the necessary build dependencies (gcc, binutils, nasm, python)
3. Build the PyInstaller executable from the C△ source code
4. Copy the resulting binary to `dist/hypotenuse-container`

### Running Tests

To run the compiler and test suite inside the container:

```bash
make container-test
```

This runs the same tests that `make test` runs on the host, but inside the container environment.

## Usage Examples

### Running a Single Test

To compile and run a specific C△ test file:

```bash
make container-run test/baseline.ctri
```

This runs the baseline test, which prints "x" to stdout.

### Using Command Line Options

You can pass additional arguments to the compiler:

```bash
make container-run test/baseline.ctri -c -C "-Wall -O2"
```

This compiles the baseline test with warning flags and optimization level 2.

### Running the Structure Parser

To see the program's structure graph:

```bash
make container-run test/baseline.ctri -p
```

## Platform Configuration

The C△ compiler targets `linux/amd64` architecture in the container. This is important because:

1. The compiler is designed to produce Linux ELF binaries
2. The container provides the necessary Linux environment
3. Cross-compilation is avoided

To target other architectures, you would need to modify the Makefile to use the `--arch` flag with the `container` CLI.

## Comparing with Docker-based Build

The traditional Docker-based approach is available via `make build-x86_64-elf`, which:

- Requires Docker to be installed
- Uses a standard Linux container image
- Can run on Intel macOS (via Rosetta) or Linux

The `container` CLI approach:

- Is native to macOS
- Optimized for Apple Silicon performance
- Provides better integration with the macOS ecosystem
- Is simpler to set up and use

## Troubleshooting

### `container` CLI Not Found

If `make container-build` reports that the `container` CLI is not found, ensure it's installed and in your PATH:

```bash
which container
```

### System Service Not Running

If the `container` system service is not running, start it:

```bash
container system start
```

### Build Failures

If the container build fails, you can get more details by running the container commands directly:

```bash
container run --platform linux/amd64 python:3.14-slim sh
```

Then inside the container, run the build commands manually.

## Integration with Host Environment

The containerized compiler maintains separation from your host development environment. For collaborative development, you can:

1. Use the standard `make test` on your local machine for development
2. Use `make container-test` for final validation
3. Use `make container-build` for production builds

This ensures that your host environment can have different versions or configurations of tools while the container provides a consistent build environment.

## Future Directions

The C△ project may add additional `container`-specific targets in the future, such as:

- `make container-deploy` — Deploy the compiler to a containerized environment
- `make container-dev` — Start a development container with the compiler and tools
- `make container-bench` — Run performance benchmarks inside the container

## Resources

- [Apple `container` CLI Documentation](https://github.com/apple/container/blob/main/docs/command-reference.md)
- [Apple `container` GitHub Repository](https://github.com/apple/container)
- [C△ Online Documentation](https://hypotenuse.mintlify.app)
