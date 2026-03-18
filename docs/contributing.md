# Contributing to the Hypotenuse Compiler

Thank you for your interest in contributing. This document explains the project structure, development workflow, branch conventions, and what kinds of contributions are most useful right now.

---

## Project Status

The compiler is in **Stage 1** of a seven-stage development plan. The team of four is actively working on `parser.py` and `structure.py`. The most impactful contributions right now are:

- Test cases that expose parser or structurer edge cases
- Documentation improvements and corrections

---

## Repository Layout

```
/
├── src/             Compiler source
│   ├── main.py      Driver
│   ├── lexer.py     Lexer
│   ├── parser.py    Parser (active development)
│   └── structure.py Structor (active development)
├── docs/            Language and compiler documentation
├── test/            Test suite
├── makefile         Build system
└── LICENSE          GPL-3.0
```

---

## Getting Started

### Requirements

- Linux (x86_64)
- Python 3.10 or later
- GCC
- NASM
- GNU Make
- Git

### Setup

```bash
git clone https://github.com/setuser1/The-Hypotenuse-Compiler
cd The-Hypotenuse-Compiler
make
```

### Running the compiler

```bash
python src/main.py yourfile.ctri
python src/main.py -t yourfile.ctri    # print token stream
```

---

## Branch Conventions

| Branch pattern | Purpose |
|---|---|
| `main` | Stable, finalized code only |

All work happens on a feature or fix branch. Open a pull request against `main` when the work is ready for review. After a branch is merged, it will be deleted.

---

## Making a Contribution

1. Check the [issue tracker](https://github.com/setuser1/The-Hypotenuse-Compiler/issues) for open issues.
2. Comment on the issue you want to work on so others know it is taken.
3. Create a fork from `main` following the branch naming conventions above if you are a non-contributor.
4. Make your changes. Write or update tests in `test/` if applicable.
5. Run the test suite before opening a PR:
   ```bash
   make test
   ```
6. Open a pull request against `main` with a clear title and description.
   - Reference any issues the PR closes: `Closes #61`
   - Describe what changed and why.
7. A maintainer/contributor will review. Address review comments and push updates to the same branch.

---

## Code Style

- Python files use 4-space indentation.
- Follow the existing naming style — `snake_case` for variables and functions, `PascalCase` for classes.
- Keep functions focused — one responsibility per function.
- Comment non-obvious logic.
---

## Writing Tests

Tests live in `test/`. Each test is a `.ctri` source file containing the expected output of `python src/main.py -t <file>`.

```
test/
├── basic_vars.ctri
├── negative_numbers.ctri 
```

When fixing a bug, always add a test case that would have caught it.

---

## Reporting Bugs

Open an issue on GitHub with:

- A minimal `.ctri` file that reproduces the problem
- The exact command you ran
- The output you got
- The output you expected

Label the issue `bug`.

---

## License

By contributing you agree that your contributions are licensed under the same GPL-3.0 license as the rest of the project.
