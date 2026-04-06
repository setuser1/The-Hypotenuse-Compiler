import argparse

# import sys  # removed unused import
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

    parser.add_argument("files", nargs="+", help="Source file(s) to compile")

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

    return parser.parse_args()


def print_tokens(tokens):
    """Pretty-print a token list."""
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
    codegen_obj = codegen.CodeGen(ast, structor)
    output = codegen_obj.generate()

    return tokens, output, objects


def write_output(path, data):
    with open(path, "w") as f:
        f.write(data)


def main():
    args = parse_args()

    for path in args.files:
        if not path.endswith(".ctri"):
            print(f"Error: Only .ctri files are supported, got '{path}'")
            continue
        try:
            tokens, output, objects = compile_file(path)

            # -----------------------------
            # Token mode
            # -----------------------------
            if args.tokens:
                print_tokens(tokens)
                continue

            # -----------------------------
            # Structure graph mode
            # -----------------------------
            if args.print:
                print_objects(objects)
                continue

            # -----------------------------
            # ASM mode (WIP)
            # -----------------------------
            if args.asm:
                print("Error: assembly output is not implemented yet (WIP)")
                continue

            # -----------------------------
            # Default: compiled output
            # -----------------------------
            if args.output:
                write_output(args.output, output)
            else:
                print(output)

        except FileNotFoundError:
            print(f"Error: file not found {path}")
        except OSError as error:
            print(f"Error reading file: {error}")
        except SyntaxError as error:
            print(f"Syntax error: {error}")
        except Exception as error:
            print(f"Compilation error: {error}")


if __name__ == "__main__":
    main()
