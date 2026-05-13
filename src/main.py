import argparse


import lexer
import parser as p
import structure
import codegen
import assembler
import nasmgen


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


def preprocess_source(source, target_arch=None):
    """Preprocess source code handling #define, #ifdef, #ifndef, #if, #else, #elif, #endif.
    
    Args:
        source: Source code string
        target_arch: Target architecture (x86_64, arm64) or None for auto-detect
    
    Returns:
        Preprocessed source code string
    """
    import platform
    import re
    
    # Define architecture macros
    if target_arch is None:
        arch = platform.machine()
    else:
        arch = target_arch
    
    defined_macros = {}
    
    # Add architecture defines
    if arch in ("arm64", "aarch64"):
        defined_macros["__ARM64__"] = "1"
    elif arch in ("x86_64", "amd64"):
        defined_macros["__x86_64__"] = "1"
    
    lines = source.split('\n')
    output_lines = []
    # Stack to track conditional compilation state
    # Each element is (should_include, branch_taken)
    # - should_include: whether the current block should be included
    # - branch_taken: whether any branch in this #if/#elif/#else chain has already been taken
    condition_stack = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        if stripped.startswith('#'):
            # Handle #define
            if stripped.startswith('#define '):
                match = re.match(r'#define\s+(\w+)(?:\s+(.*))?$', stripped)
                if match:
                    macro_name = match.group(1)
                    macro_value = match.group(2) if match.group(2) else ""
                    defined_macros[macro_name] = macro_value
                i += 1
                continue
            
            # Handle #undef
            if stripped.startswith('#undef '):
                match = re.match(r'#undef\s+(\w+)$', stripped)
                if match:
                    macro_name = match.group(1)
                    defined_macros.pop(macro_name, None)
                i += 1
                continue
            
            # Handle #ifdef
            if stripped.startswith('#ifdef '):
                macro_name = stripped[7:].strip()
                is_defined = macro_name in defined_macros
                condition_stack.append((is_defined, is_defined))
                i += 1
                continue
            
            # Handle #ifndef
            if stripped.startswith('#ifndef '):
                macro_name = stripped[8:].strip()
                is_defined = macro_name in defined_macros
                condition_stack.append((not is_defined, not is_defined))
                i += 1
                continue
            
            # Handle #if
            if stripped.startswith('#if '):
                condition_expr = stripped[4:].strip()
                result = _eval_preprocessor_expr(condition_expr, defined_macros)
                condition_stack.append((result, result))
                i += 1
                continue
            
            # Handle #elif
            if stripped.startswith('#elif '):
                if condition_stack:
                    should_include, branch_taken = condition_stack[-1]
                    if not branch_taken:
                        # Evaluate elif condition
                        condition_expr = stripped[6:].strip()
                        result = _eval_preprocessor_expr(condition_expr, defined_macros)
                        condition_stack[-1] = (result, result)
                    else:
                        # A previous branch was already taken, skip this elif
                        condition_stack[-1] = (False, True)
                i += 1
                continue
            
            # Handle #else
            if stripped == '#else':
                if condition_stack:
                    should_include, branch_taken = condition_stack[-1]
                    # Include else block only if no branch was taken yet
                    condition_stack[-1] = (not branch_taken, True)
                i += 1
                continue
            
            # Handle #endif
            if stripped == '#endif':
                if condition_stack:
                    condition_stack.pop()
                i += 1
                continue
            
            # Handle other directives - just pass through for now
            i += 1
            continue
        
        # Check if we should include this line based on condition stack
        should_include = True
        for include, _ in condition_stack:
            if not include:
                should_include = False
                break
        
        if should_include:
            output_lines.append(line)
        i += 1
    
    return '\n'.join(output_lines)


def _eval_preprocessor_expr(expr, defined_macros):
    """Evaluate a preprocessor condition expression.
    
    Supports: defined(MACRO), &&, ||, !, comparisons
    """
    import re
    
    # Replace defined(MACRO) with 1 or 0
    def replace_defined(match):
        macro_name = match.group(1)
        return "1" if macro_name in defined_macros else "0"
    
    expr = re.sub(r'defined\s*\(\s*(\w+)\s*\)', replace_defined, expr)
    
    # Simple evaluation - handle basic cases
    expr = expr.strip()
    
    # Handle empty expression
    if not expr:
        return False
    
    # After defined() replacement, evaluate the resulting expression
    # Handle simple values: 1 = True, 0 = False, or check if macro is defined
    if expr == "1":
        return True
    if expr == "0":
        return False
    
    # Handle simple macro name (standalone identifier)
    if re.match(r'^\w+$', expr):
        return expr in defined_macros
    
    # Handle ! (not)
    if expr.startswith('!'):
        return not _eval_preprocessor_expr(expr[1:].strip(), defined_macros)
    
    # Handle && (and)
    if '&&' in expr:
        parts = expr.split('&&', 1)
        left = _eval_preprocessor_expr(parts[0].strip(), defined_macros)
        right = _eval_preprocessor_expr(parts[1].strip(), defined_macros)
        return left and right
    
    # Handle || (or)
    if '||' in expr:
        parts = expr.split('||', 1)
        left = _eval_preprocessor_expr(parts[0].strip(), defined_macros)
        right = _eval_preprocessor_expr(parts[1].strip(), defined_macros)
        return left or right
    
    # Handle comparisons
    for op in ['==', '!=', '<', '>', '<=', '>=']:
        if op in expr:
            parts = expr.split(op, 1)
            left = parts[0].strip()
            right = parts[1].strip()
            
            # Get values
            left_val = defined_macros.get(left, left)
            right_val = defined_macros.get(right, right)
            
            # Convert to numbers if possible
            try:
                left_val = int(left_val)
            except (ValueError, TypeError):
                pass
            try:
                right_val = int(right_val)
            except (ValueError, TypeError):
                pass
            
            if op == '==':
                return left_val == right_val
            elif op == '!=':
                return left_val != right_val
            elif op == '<':
                return left_val < right_val
            elif op == '>':
                return left_val > right_val
            elif op == '<=':
                return left_val <= right_val
            elif op == '>=':
                return left_val >= right_val
    
    return False


def compile_file(path, target_arch=None):
    """Lex, parse, structure, and generate code for a file."""
    with open(path, "r") as f:
        content = f.read()

    validate_includes(path, content)

    # Preprocess source
    content = preprocess_source(content, target_arch)
    
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


def validate_includes(source_path, source_content):
    """Reject include directives that point back to the current source file."""
    import os
    import re

    source_realpath = os.path.realpath(source_path)
    source_dir = os.path.dirname(source_realpath)

    for match in re.finditer(r'^\s*#\s*include\s+"([^"]+)"', source_content, re.MULTILINE):
        include_path = match.group(1)
        include_candidates = [
            os.path.realpath(include_path),
            os.path.realpath(os.path.join(source_dir, include_path)),
        ]
        if source_realpath in include_candidates:
            raise SyntaxError(f"source file cannot include itself: {include_path}")


def write_output(path, data):
    with open(path, "w") as f:
        f.write(data)


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
            tokens, output, objects, asm_blocks = compile_file(path, args.target)

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
                # Determine target architecture for filtering
                target_arch = getattr(args, "target", None)
                if target_arch:
                    target_is_arm64 = (target_arch == "arm64")
                else:
                    # Auto-detect from platform
                    import platform
                    is_macos = platform.system() == "Darwin"
                    current_arch = platform.machine()
                    if is_macos:
                        target_is_arm64 = (current_arch == "arm64")
                    else:
                        target_is_arm64 = False

                for asm_block in asm_blocks:
                    # Check if block matches target architecture
                    if asm_block.syntax:
                        block_is_arm64, _ = nasmgen.get_asm_config(asm_block.syntax)
                        if target_is_arm64 and not block_is_arm64:
                            continue
                        if not target_is_arm64 and block_is_arm64:
                            continue
                    nasmgen.print_asm_block(asm_block, target_is_arm64)
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
                asm_object_files = assembler.assemble_asm_blocks(
                    asm_blocks,
                    path,
                    getattr(args, "target", None),
                    getattr(args, "format", None),
                )
                exe_path = assembler.compile_with_gcc(
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
