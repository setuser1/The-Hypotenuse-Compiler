# 🤝 Contributing to C△ and The Hypotenuse Compiler

<p align="center">
  <img src="assets/logo.png" alt="C△ Logo" width="120"/>
</p>

Thank you for your interest in contributing! 🎉 Whether you're fixing bugs, adding features, improving docs, or adding error personality messages — all contributions are welcome.

---

## 🔀 Workflow

1. 🍴 Fork the repository or create a branch from `main`
2. 🔨 Make your changes on a feature branch (e.g. `fix/my-bug`, `feat/new-feature`)
3. ✅ Make sure all tests pass: `make test`
4. 📝 Open a **Pull Request** targeting `main`
5. 👀 Request review from a maintainer
6. 🎉 Merge after approval!

> ⚠️ `main` is a **protected branch** — direct pushes are not allowed. Always use a PR.

---

## 🌿 Branch Naming

| Prefix      | Purpose                          |
| ----------- | -------------------------------- |
| `fix/`      | Bug fixes 🐛                     |
| `feat/`     | New features ✨                  |
| `refactor/` | Code restructuring 🔧            |
| `docs/`     | Documentation updates 📝         |
| `assets/`   | Images, logos, media 🖼️          |
| `test/`     | Tests and test infrastructure 🧪 |
| `patch/`    | Hotfixes and patches 🩹          |

---

## 🧪 Tests

```bash
make test
```

Tests live in the `test/` directory. Add a test for any bug you fix or feature you add. 🧰

---

## ✍️ Code Style

- 🐍 Python 3 — follow PEP 8
- 📝 Document new functions and classes with docstrings
- 🧹 Keep functions focused — one responsibility per function
- 🔑 Use descriptive variable names
- 💬 Leave comments for non-obvious logic

---

## 📦 Project Structure

```
📁 The-Hypotenuse-Compiler/
├── 📂 src/          ← compiler source (lexer, parser, structurer, main)
├── 📂 docs/         ← language and compiler documentation
├── 📂 test/         ← test files
├── 📂 errors/       ← error personality messages
├── 📂 assets/       ← logo and media
├── 📄 makefile      ← build and test targets
└── 📄 README.MD     ← project overview
```

---

## 💬 Questions?

Open an **issue** on GitHub and tag it with `question`. We're happy to help! 🙌
