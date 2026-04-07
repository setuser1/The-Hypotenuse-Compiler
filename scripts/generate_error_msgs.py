#!/usr/bin/env python3
"""Generate error_msgs.py from errors.txt."""

import os

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ERRORS_TXT = os.path.join(SRC_DIR, "..", "src", "errors.txt")
OUTPUT_PY = os.path.join(SRC_DIR, "..", "src", "error_msgs.py")


def generate():
    errors = {}
    current_category = None

    with open(ERRORS_TXT, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_category = line[1:-1]
                continue

            if "|" in line and current_category:
                code, msg = line.split("|", 1)
                code = code.strip()
                if code not in errors:
                    errors[code] = []
                errors[code].append(msg.strip())

    with open(OUTPUT_PY, "w") as f:
        f.write('"""Auto-generated error messages from errors.txt."""\n')
        f.write("\n")
        f.write("import os\n")
        f.write("import random\n")
        f.write("\n")
        f.write("_ERRORS = None\n")
        f.write("\n")
        f.write("ERROR_MESSAGES = {\n")
        for code in sorted(errors.keys()):
            messages = errors[code]
            f.write(f'    "{code}": [\n')
            for msg in messages:
                f.write(f"        {repr(msg)},\n")
            f.write(f"    ],\n")
        f.write("}\n")
        f.write("\n")
        f.write("\n")
        f.write("def _load_errors():\n")
        f.write('    """Load errors.txt if present (dev mode) or use embedded."""\n')
        f.write("    global _ERRORS\n")
        f.write("    if _ERRORS is not None:\n")
        f.write("        return\n")
        f.write("    _ERRORS = ERROR_MESSAGES.copy()\n")
        f.write('    path = os.path.join(os.path.dirname(__file__), "errors.txt")\n')
        f.write("    if os.path.exists(path):\n")
        f.write("        current_category = None\n")
        f.write("        with open(path) as fp:\n")
        f.write("            for line in fp:\n")
        f.write("                line = line.strip()\n")
        f.write('                if not line or line.startswith("#"):\n')
        f.write("                    continue\n")
        f.write('                if line.startswith("[") and line.endswith("]"):\n')
        f.write("                    current_category = line[1:-1]\n")
        f.write("                    continue\n")
        f.write('                if "|" in line and current_category:\n')
        f.write('                    code, msg = line.split("|", 1)\n')
        f.write("                    code = code.strip()\n")
        f.write("                    if code not in _ERRORS:\n")
        f.write("                        _ERRORS[code] = []\n")
        f.write("                    _ERRORS[code].append(msg.strip())\n")
        f.write("\n")
        f.write("\n")
        f.write(
            "def get_error_msg(code: str, fallback: str = None, **kwargs) -> str:\n"
        )
        f.write('    """Get random error message for code, format with kwargs."""\n')
        f.write("    _load_errors()\n")
        f.write("    messages = _ERRORS.get(code, [])\n")
        f.write("    if not messages:\n")
        f.write('        return fallback or f"Unknown error: {code}"\n')
        f.write("    msg = random.choice(messages)\n")
        f.write("    try:\n")
        f.write("        return msg.format(**kwargs)\n")
        f.write("    except KeyError:\n")
        f.write("        return msg\n")
        f.write("\n")
        f.write("\n")
        f.write("def has_error_code(code: str) -> bool:\n")
        f.write('    """Check if error code exists."""\n')
        f.write("    _load_errors()\n")
        f.write("    return code in _ERRORS\n")

    print(f"Generated: {OUTPUT_PY}")


if __name__ == "__main__":
    generate()
