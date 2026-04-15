import argparse


import lexer
import parser as p
import structure
import codegen


def parse_args():
    """Parse command-line arguments using argparse."""
    parser = argparse.ArgumentParser(
        prog="hypotenuse",
        description="C triangle compiler.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument("files", nargs="*", help="Source file(s) to compile")

    parser.add_argument(
        "-t", "--tokens", action="store_true", help="Print lexical tokens and exit"
    )

    parser.add_argument(
        "-p",
        "--print",
        action="store_true",
        help="Print structure graph instead of compiling",
    )

    parser.add_argument(
        "-o", "--output", metavar="PATH", help="Write compiled output to PATH"
    )

    parser.add_argument(
        "-a", "--asm", action="store_true", help="Show generated assembly (WIP)"
    )

    parser.add_argument(
        "-T",
        "--target",
        metavar="ARCH",
        choices=["x86_64", "arm64"],
        help="Target architecture for asm blocks: x86_64 or arm64 (default: auto-detect)",
    )

    parser.add_argument(
        "-F",
        "--format",
        metavar="FORMAT",
        choices=["macho", "elf"],
        help="Object file format: macho (ARM64 macOS), elf (Linux). "
        "Overrides auto-detection. Note: NASM does not support ARM64 Mach-O; "
        "use auto-detection on Apple Silicon.",
    )

    parser.add_argument(
        "-c", "--compile", action="store_true", help="Compile with gcc to executable"
    )

    parser.add_argument(
        "-C",
        "--cflags",
        metavar="FLAGS",
        help="Pass extra flags to gcc (e.g., '$(sdl2-config --cflags --libs)')",
    )

    parser.add_argument(
        "-i",
        "--install",
        metavar="PATH",
        help="Install file to PLIBS folder (system or user)",
    )

    parser.add_argument(
        "-r",
        "--remove",
        metavar="NAME",
        help="Remove a .plib file from PLIBS folder by name",
    )

    return parser.parse_args()


def print_tokens(tokens):
    """Pretty-print a token list."""
    if not tokens:
        print("\u250c\u2500 Tokens (none) \u2510")
        print("\u2514\u2500\u2500\u2500\u2500\u2500\u2500\u2518")
        return
    width = max(len(t[0]) for t in tokens)
    print("\u250c\u2500 Tokens " + "\u2500" * (width + 24) + "\u2510")
    for t in tokens:
        typ, val = t[0], t[1]
        line = t[2] if len(t) > 2 else 0
        col = t[3] if len(t) > 3 else 0
        pos = f" @ {line}:{col}" if line > 0 else ""
        print(f"\u2502  {typ:<{width}}  {val!r}{pos}")
    print("\u2514" + "\u2500" * (width + 26) + "\u2518")


def print_objects(objects):
    """Pretty-print the Callee/Caller graph objects grouped by scope."""
    from structure import Callee, Caller, callee_value_display_parts

    by_scope = {}
    for obj in objects:
        scope_name = obj.scope.name
        by_scope.setdefault(scope_name, []).append(obj)

    print("\n\u250c\u2500 Scope Graph " + "\u2500" * 40 + "\u2510")
    for scope_name, nodes in by_scope.items():
        parent = nodes[0].scope.parent
        parent_str = f"  (parent: {parent.name})" if parent else ""
        print("\u2502")
        print(f"\u2502  scope: {scope_name}{parent_str}")

        for node in nodes:
            if isinstance(node, Callee):
                if node.var_type and "*" in node.var_type:
                    kind = node.var_type
                elif node.is_library:
                    kind = "library"
                elif not node.is_variable:
                    kind = "function"
                else:
                    kind, _ = callee_value_display_parts(node.value)

                print(
                    f"\u2502    Callee  {node.name!r:<20} "
                    f"kind={kind:<12} value={repr(node.value)}"
                )

            elif isinstance(node, Caller):
                callee_name = node.dependencies[0][0].name if node.dependencies else "?"
                args = node.dependencies[0][1] if node.dependencies else []
                args_str = ", ".join(repr(a) for a in args)

                print(
                    f"\u2502    Caller  {node.name!r:<20} -> {callee_name}({args_str})"
                )

    print("\u2502")
    print("\u2514" + "\u2500" * 54 + "\u2518")


def compile_file(path):
    """Lex, parse, structure, and generate code for a file."""
    with open(path, "r") as f:
        content = f.read()

    tokens = lexer.Lexer(content).lex()
    tokens.append(("EOF", "EOF", 0, 0))

    ast = p.Parser(tokens).parse_program()
    structor = structure.Structor(ast, content)
    objects = structor.build_from_ast()

    # 🔥 ACTUAL COMPILATION
    codegen_obj = codegen.CodeGen(ast, structor, source_path=path)
    output = codegen_obj.generate()
    asm_blocks = codegen_obj._asm_blocks

    return tokens, output, objects, asm_blocks


def write_output(path, data):
    with open(path, "w") as f:
        f.write(data)


def compile_with_gcc(c_path, output_path=None, extra_flags=None, asm_objects=None):
    """Compile C file to executable with gcc."""
    import subprocess
    import shutil
    import os

    if not shutil.which("gcc"):
        raise RuntimeError("gcc not found in PATH. Install GCC to use --compile.")

    if output_path is None:
        output_path = os.path.splitext(c_path)[0]
    # else: output_path is already set correctly, no need for reassignment

    cmd = ["gcc", c_path, "-o", output_path]
    # Add asm object files
    if asm_objects:
        cmd.extend(asm_objects)
    # Basic validation for extra_flags to prevent obvious injection attempts
    if extra_flags:
        # Split and filter out any empty strings or potentially dangerous flags
        flags = [flag for flag in extra_flags.split() if flag.strip()]
        # Additional safety: reject flags that try to change output file or perform dangerous operations
        safe_flags = []
        skip_next = False
        for i, flag in enumerate(flags):
            if skip_next:
                skip_next = False
                continue
            # Skip -o and its argument as we control the output file
            if flag == "-o":
                skip_next = True  # Skip the next argument (output file)
                continue
            # Allow library/include/linker flags
            if (
                flag.startswith("-l")
                or flag.startswith("-L")
                or flag.startswith("-I")
                or flag.startswith("-D")
            ):
                safe_flags.append(flag)
            # Allow linker flags
            elif flag.startswith("-Wl,"):
                safe_flags.append(flag)
            # Allow common warning/optimization/debug flags
            elif (
                flag in ["-Wall", "-Wextra", "-Werror", "-pedantic"]
                or flag.startswith("-std=")
                or flag in ["-O0", "-O1", "-O2", "-O3", "-Os", "-Ofast"]
                or flag == "-g"
            ):
                safe_flags.append(flag)
            # Ignore other flags for safety

        cmd.extend(safe_flags)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"gcc failed: {result.stderr}")

    return output_path


def assemble_asm_blocks(asm_blocks, source_path, target_arch=None, output_format=None):
    """Generate .asm files from asm blocks and assemble with NASM.

    Args:
        asm_blocks: List of AsmBlock nodes
        source_path: Path to source file
        target_arch: Override target architecture ('x86_64' or 'arm64').
                    Defaults to auto-detect from platform.
        output_format: Override object file format ('macho', 'elf', 'win64').
                      Defaults to auto-detect from platform.
    """
    import subprocess
    import shutil
    import os
    import platform

    if not asm_blocks:
        return []

    base_dir = os.path.dirname(source_path) or "."
    object_files = []

    # Determine if we're on macOS (for symbol naming)
    is_macos = platform.system() == "Darwin"
    current_arch = platform.machine()

    def get_asm_config(asm_block):
        """Determine architecture and format for an asm block.

        Priority:
        1. asm block's explicit syntax (syntax x86_64_elf or syntax arm64_macho)
        2. command-line --target flag
        3. command-line --format flag
        4. auto-detect from platform
        """
        # Check for explicit syntax in asm block
        if asm_block.syntax:
            syntax = asm_block.syntax.lower()
            if "x86_64" in syntax and "elf" in syntax:
                return False, "elf64"
            elif "arm64" in syntax and "macho" in syntax:
                return True, "macho64"
            elif "x86_64" in syntax and "macho" in syntax:
                return False, "macho64"
            elif "arm64" in syntax:
                return True, "macho64"
            elif "elf" in syntax:
                return False, "elf64"

        # Check command-line flags
        if target_arch == "x86_64":
            return False, "macho64" if is_macos else "elf64"
        elif target_arch == "arm64":
            return True, "macho64"
        elif output_format == "macho":
            return True, "macho64"
        elif output_format == "elf":
            return False, "elf64"

        # Auto-detect from platform
        if is_macos and current_arch == "arm64":
            return True, "macho64"
        elif is_macos and current_arch == "x86_64":
            return False, "macho64"
        else:
            return False, "elf64"

    for asm_block in asm_blocks:
        # Skip bare asm blocks - they don't have a function to assemble
        if not asm_block.is_function:
            continue

        # Determine config for this asm block
        is_arm64, asm_format = get_asm_config(asm_block)

        asm_path = os.path.join(base_dir, f"{asm_block.name}.s")
        obj_path = os.path.join(base_dir, f"{asm_block.name}.o")

        import re

        if is_arm64:
            # ARM64: Use Apple as
            # AAPCS64: integer params in x0-x7, float params in v0-v7
            arm64_int_regs = ["x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7"]
            arm64_float_regs = ["v0", "v1", "v2", "v3", "v4", "v5", "v6", "v7"]

            # Collect directives and instructions
            directives = []
            instructions = []
            for line in asm_block.lines:
                stripped = line.strip()
                # Skip syntax declaration and empty lines
                if not stripped or stripped.startswith("syntax"):
                    continue
                if (
                    stripped.startswith("section")
                    or stripped.startswith(".")
                    or stripped.startswith("global")
                ):
                    directives.append(stripped)
                else:
                    instructions.append(stripped)

            # Generate parameter mapping based on type
            param_map = {}
            int_reg_idx = 0
            float_reg_idx = 0
            offset = 0
            for param_type, param_name in asm_block.params:
                # Determine register based on type
                if param_type in ("float", "double"):
                    if float_reg_idx < len(arm64_float_regs):
                        # Float params go in float registers
                        param_map[param_name] = arm64_float_regs[float_reg_idx]
                        float_reg_idx += 1
                    else:
                        # 溢出 to stack
                        param_map[param_name] = f"[sp, #{offset}]"
                        offset += 8
                else:
                    # Integer params go in integer registers
                    if int_reg_idx < len(arm64_int_regs):
                        param_map[param_name] = arm64_int_regs[int_reg_idx]
                        int_reg_idx += 1
                    else:
                        # 溢出 to stack
                        param_map[param_name] = f"[sp, #{offset}]"
                        offset += 8

            # Update instructions to use register names or stack offsets
            updated_instructions = []
            for instr in instructions:
                updated_instr = instr
                for param_name, addr in param_map.items():
                    pattern = r"\b" + re.escape(param_name) + r"\b"
                    updated_instr = re.sub(pattern, addr, updated_instr)
                updated_instructions.append(updated_instr)

            # Generate .s file for Apple as
            with open(asm_path, "w") as f:
                f.write("// Generated by Hypotenuse Compiler\n")
                # Write data section variables first if any
                if asm_block.data_lines:
                    f.write(".section __DATA,__data\n")
                    for data_line in asm_block.data_lines:
                        f.write(f"{data_line}\n")
                # Section directives (text section)
                has_text_section = any(
                    "__TEXT" in d or ".text" in d for d in directives
                )
                if not has_text_section:
                    f.write(".section __TEXT,__text\n")
                for directive in directives:
                    if not directive.startswith("syntax"):
                        f.write(f"{directive}\n")
                # On macOS, C compiler adds underscore to all symbols
                # So _add becomes __add in the final binary
                global_name = f"__{asm_block.name}"
                f.write(f".global {global_name}\n")
                f.write(f"{global_name}:\n")
                # Save frame pointer and link register
                f.write("    stp x29, x30, [sp, #-16]!\n")
                f.write("    mov x29, sp\n")
                # Write instructions (skip user's ret, we add our own)
                for instr in updated_instructions:
                    instr_lower = instr.strip().lower()
                    if instr_lower == "ret":
                        continue  # Skip user's ret, we add our own
                    f.write(f"    {instr}\n")
                # Handle return expression
                if asm_block.return_expr:
                    # Use appropriate register based on return type
                    if asm_block.ret_type in ("float", "double"):
                        f.write(f"    fmov v0, {asm_block.return_expr}\n")
                    else:
                        f.write(f"    mov x0, {asm_block.return_expr}\n")
                # Epilogue (always needed to restore x29/x30)
                f.write("    ldp x29, x30, [sp], #16\n")
                f.write("    ret\n")

            # Assemble with Apple as
            result = subprocess.run(
                ["as", "-arch", "arm64", asm_path, "-o", obj_path],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"as failed: {result.stderr}")
        else:
            # x86_64: Use NASM
            if not shutil.which("nasm"):
                raise RuntimeError(
                    "nasm not found in PATH. Install NASM to use inline assembly."
                )

            # x86_64 System V ABI: integer and float parameter registers
            x86_int_regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
            x86_float_regs = [
                "xmm0",
                "xmm1",
                "xmm2",
                "xmm3",
                "xmm4",
                "xmm5",
                "xmm6",
                "xmm7",
            ]

            # Collect directives and instructions
            directives = []
            instructions = []
            for line in asm_block.lines:
                stripped = line.strip()
                # Skip syntax declaration and empty lines
                if not stripped or stripped.startswith("syntax"):
                    continue
                if stripped.startswith("section ") or stripped.startswith("."):
                    directives.append(stripped)
                else:
                    instructions.append(stripped)

            # Generate parameter mapping based on type
            param_map = {}
            int_reg_idx = 0
            float_reg_idx = 0
            offset = 8
            for param_type, param_name in asm_block.params:
                # Determine register based on type
                if param_type in ("float", "double"):
                    if float_reg_idx < len(x86_float_regs):
                        # Float params go in xmm registers
                        param_map[param_name] = x86_float_regs[float_reg_idx]
                        float_reg_idx += 1
                    else:
                        # 溢出 to stack
                        param_map[param_name] = f"[rbp-{offset}]"
                        offset += 8
                else:
                    # Integer params go in integer registers
                    if int_reg_idx < len(x86_int_regs):
                        param_map[param_name] = x86_int_regs[int_reg_idx]
                        int_reg_idx += 1
                    else:
                        # 溢出 to stack
                        param_map[param_name] = f"[rbp-{offset}]"
                        offset += 8

            # Update instructions to use register names
            updated_instructions = []
            for instr in instructions:
                updated_instr = instr
                for param_name, addr in param_map.items():
                    pattern = r"\b" + re.escape(param_name) + r"\b"
                    updated_instr = re.sub(pattern, addr, updated_instr)
                updated_instructions.append(updated_instr)

            # Generate .asm file
            with open(asm_path, "w") as f:
                f.write("; Generated by Hypotenuse Compiler\n")
                # Write data section variables first if any
                if asm_block.data_lines:
                    # Check if there's already a .data section in directives
                    has_data_section = any(".data" in d for d in directives)
                    if not has_data_section:
                        f.write("section .data\n")
                    for data_line in asm_block.data_lines:
                        f.write(f"{data_line}\n")
                # Write section directives (skip data, we already handled it)
                for directive in directives:
                    if ".data" not in directive:
                        f.write(f"{directive}\n")
                # Ensure we have a text section
                has_text_section = any(
                    ".text" in d or ".section" in d for d in directives
                )
                if not has_text_section:
                    f.write("section .text\n")
                # Global declaration and function label
                # On macOS, C compiler adds underscore to all symbols
                global_name = f"__{asm_block.name}" if is_macos else asm_block.name
                f.write(f"global {global_name}\n")
                f.write(f"{global_name}:\n")
                # Add prologue
                f.write("    push rbp\n")
                f.write("    mov rbp, rsp\n")
                # Save float registers that will be used (if any float params)
                for param_type, param_name in asm_block.params:
                    if param_type in ("float", "double"):
                        # Get the register for this param
                        reg = param_map.get(param_name, "")
                        if reg.startswith("xmm"):
                            f.write("    sub rsp, 8\n")
                            f.write(f"    movsd [rsp], {reg}\n")
                # Write instructions (skip user's ret, we add our own)
                for instr in updated_instructions:
                    instr_lower = instr.strip().lower()
                    if instr_lower == "ret":
                        continue  # Skip user's ret, we add our own
                    f.write(f"    {instr}\n")
                # Handle return expression if provided
                if asm_block.return_expr:
                    if asm_block.ret_type in ("float", "double"):
                        f.write(f"    movq xmm0, {asm_block.return_expr}\n")
                    else:
                        f.write(f"    mov rax, {asm_block.return_expr}\n")
                # Epilogue (always needed)
                f.write("    pop rbp\n")
                f.write("    ret\n")

            # Assemble with NASM
            result = subprocess.run(
                ["nasm", "-f", asm_format, asm_path, "-o", obj_path],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"nasm failed: {result.stderr}")

        object_files.append(obj_path)

    return object_files


def install_to_plibs(source_path):
    """Install a file to the PLIBS folder (system or user)."""
    import shutil
    import os

    if not os.path.exists(source_path):
        print(f"Error: file not found: {source_path}")
        return

    filename = os.path.basename(source_path)
    if not filename.endswith(".plib"):
        print(f"Error: only .plib files can be installed, got '{filename}'")
        return

    # Try system location first, then user location
    system_plibs = "/usr/lib/PLIBS"
    user_plibs = os.path.expanduser("~/.local/lib/PLIBS")

    # Try system location first
    if os.path.exists(system_plibs) and os.access(system_plibs, os.W_OK):
        dest = os.path.join(system_plibs, filename)
        shutil.copy2(source_path, dest)
        print(f"Installed to {dest}")
        return

    # Try user location
    try:
        os.makedirs(user_plibs, exist_ok=True)
        if os.access(user_plibs, os.W_OK):
            dest = os.path.join(user_plibs, filename)
            shutil.copy2(source_path, dest)
            print(f"Installed to {dest}")
            return
        else:
            print(f"Error: no write access to PLIBS folder: {user_plibs}")
    except OSError as e:
        print(f"Error: could not create PLIBS folder {user_plibs}: {e}")

    print("Error: no writable PLIBS folder found")


def remove_from_plibs(name):
    """Remove a .plib file from PLIBS folder by name."""
    import os

    if not name.endswith(".plib"):
        name = name + ".plib"

    # Try both locations
    system_plibs = "/usr/lib/PLIBS"
    user_plibs = os.path.expanduser("~/.local/lib/PLIBS")

    removed = False
    for plibs_dir in [system_plibs, user_plibs]:
        path = os.path.join(plibs_dir, name)
        if os.path.exists(path):
            os.remove(path)
            print(f"Removed from {path}")
            removed = True
            break

    if not removed:
        print(f"Error: '{name}' not found in any PLIBS folder")


def main():
    args = parse_args()

    # -----------------------------
    # Install mode
    # -----------------------------
    if args.install:
        install_to_plibs(args.install)
        return

    # -----------------------------
    # Remove mode
    # -----------------------------
    if args.remove:
        remove_from_plibs(args.remove)
        return

    for path in args.files:
        if not path.endswith((".ctri", ".plib")):
            print(f"Error: Only .ctri/.plib files are supported, got '{path}'")
            continue
        try:
            tokens, output, objects, asm_blocks = compile_file(path)

            # -----------------------------
            # Print mode
            # -----------------------------
            if args.print:
                print_objects(objects)
                continue

            # -----------------------------
            # ASM mode
            # -----------------------------
            if args.asm:
                for asm_block in asm_blocks:
                    if asm_block.is_function:
                        # Asm function - generate as callable function
                        directives = [
                            line
                            for line in asm_block.lines
                            if line.startswith("section ")
                            or line.startswith(".")
                            or line.startswith("syntax")
                        ]
                        instructions = [
                            line
                            for line in asm_block.lines
                            if not (
                                line.startswith("section ")
                                or line.startswith(".")
                                or line.startswith("syntax")
                            )
                        ]
                        # Print data section with variables
                        if asm_block.data_lines:
                            # For ARM64: .section __DATA,__data
                            # For x86_64: section .data
                            for directive in directives:
                                if (
                                    "data" in directive.lower()
                                    and not directive.startswith("syntax")
                                ):
                                    print(directive)
                            for data_line in asm_block.data_lines:
                                print(data_line)
                        # Print text section directives
                        for directive in directives:
                            if "text" in directive.lower() and not directive.startswith(
                                "syntax"
                            ):
                                print(directive)
                            elif not (
                                "data" in directive.lower()
                                or "text" in directive.lower()
                            ) and not directive.startswith("syntax"):
                                print(directive)
                        # Print global and label
                        print(f"global {asm_block.name}")
                        print(f"{asm_block.name}:")
                        # Filter out user's ret, we add our own
                        for instr in instructions:
                            if instr.strip().lower() == "ret":
                                continue
                            print(f"    {instr}")
                        print("    ret")
                    else:
                        # Bare asm block - section directives, data variables, then code
                        directives = [
                            line
                            for line in asm_block.lines
                            if line.startswith("section ")
                            or line.startswith(".")
                            or line.startswith("syntax")
                        ]
                        code_lines = [
                            line
                            for line in asm_block.lines
                            if not (line.startswith("section ") or line.startswith("."))
                        ]
                        # Print data section with variables
                        if asm_block.data_lines:
                            for directive in directives:
                                if (
                                    "data" in directive.lower()
                                    and not directive.startswith("syntax")
                                ):
                                    print(directive)
                            for data_line in asm_block.data_lines:
                                print(data_line)
                        # Print other directives
                        for directive in directives:
                            if not (
                                "data" in directive.lower()
                            ) and not directive.startswith("syntax"):
                                print(directive)
                        # Print code
                        for line in code_lines:
                            print(line)
                continue

            # -----------------------------
            # Default: compiled output
            # -----------------------------
            if args.output:
                c_path = args.output
                if not c_path.endswith(".c"):
                    c_path = c_path + ".c"
                write_output(c_path, output)
            else:
                print(output)
                # Handle both .ctri and .plib file extensions
                if path.endswith(".ctri"):
                    c_path = path.replace(".ctri", ".c")
                elif path.endswith(".plib"):
                    c_path = path.replace(".plib", ".c")
                else:
                    # Fallback - should not happen due to earlier check
                    c_path = path + ".c"

            if args.compile:
                write_output(c_path, output)
                # Generate and assemble asm blocks
                asm_object_files = assemble_asm_blocks(
                    asm_blocks,
                    path,
                    getattr(args, "target", None),
                    getattr(args, "format", None),
                )
                exe_path = compile_with_gcc(
                    c_path, args.output, args.cflags, asm_object_files
                )
                print(f"Compiled to: {exe_path}")

        except FileNotFoundError:
            print(f"Error: file not found {path}")
        except OSError as error:
            print(f"Error reading file: {error}")
        except SyntaxError as error:
            print(f"Syntax error: {error}")
        except RuntimeError as error:
            print(f"Compilation error: {error}")
        except Exception as error:
            # Re-raise unexpected exceptions for debugging while still providing user feedback
            print(f"Unexpected error: {error}")
            raise


if __name__ == "__main__":
    main()
