import argparse
import sys
import lexer
import parser as p
import structure


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
        "-o",
        "--output",
        metavar="PATH",
        help="Write compiled output to PATH (not yet implemented)",
    )
    parser.add_argument(
        "-a", "--asm", action="store_true", help="Show generated assembly"
    )
    return parser.parse_args()


def print_tokens(tokens):
    """Pretty-print a token list, one token per line."""
    width = max(len(t[0]) for t in tokens)
    print("\u250c\u2500 Tokens " + "\u2500" * (width + 24) + "\u2510")
    for typ, val in tokens:
        print(f"\u2502  {typ:<{width}}  {val!r}")
    print("\u2514" + "\u2500" * (width + 26) + "\u2518")


def print_objects(objects):
    """Pretty-print the Callee/Caller graph objects grouped by scope."""
    from structure import Callee, Caller, callee_value_display_parts

    # Group by scope name
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
                # Determine kind correctly:
                # 1. Pointer variables -> their type string
                # 2. Library callees   -> 'library'
                # 3. User functions    -> 'function'  (is_variable=False, value=None)
                # 4. Variables         -> kind from value (integer/float/string/none)
                if node.var_type and "*" in node.var_type:
                    kind = node.var_type
                elif node.is_library:
                    kind = "library"
                elif not node.is_variable:
                    kind = "function"
                else:
                    kind, _ = callee_value_display_parts(node.value)
                val_repr = repr(node.value)
                print(
                    f"\u2502    Callee  {node.name!r:<20} kind={kind:<12} value={val_repr}"
                )
            elif isinstance(node, Caller):
                callee_name = node.dependencies[0][0].name if node.dependencies else "?"
                args = node.dependencies[0][1] if node.dependencies else []
                args_str = ", ".join(repr(a) for a in args)
                print(f"\u2502    Caller  {node.name!r:<20} -> {callee_name}({args_str})")
    print("\u2502")
    print("\u2514" + "\u2500" * 54 + "\u2518")


def compile_file(path):
    """Lex, parse, and structure a single source file.

    Returns (tokens, objects).
    """
    with open(path, "r") as f:
        content = f.read()

    tokens = lexer.Lexer(content).lex()
    tokens.append(("EOF", "EOF"))
    ast = p.Parser(tokens).parse_program()
    structor = structure.Structor(ast, content)
    return tokens, structor.build_from_ast()


def main():
    args = parse_args()

    # -------------------------------------------------
    #  Token-only mode (-t / --tokens)
    # -------------------------------------------------
    if args.tokens:
        if not args.files:
            print("Error: no input file provided for token printing")
            sys.exit(1)
        try:
            tokens, objects = compile_file(args.files[0])
            print_tokens(tokens)
            print_objects(objects)
            return objects
        except FileNotFoundError:
            print(f"Error: file not found {args.files[0]}")
            sys.exit(1)
        except SyntaxError as error:
            print(f"Syntax error: {error}")
            sys.exit(1)
        except Exception as error:
            print(f"Compilation error: {error}")
            sys.exit(1)

    # -------------------------------------------------
    #  Normal compilation path (one or more files)
    # -------------------------------------------------
    if not args.files:
        print("Error: no input file provided")
        sys.exit(1)

    for path in args.files:
        try:
            tokens, objects = compile_file(path)
            print_objects(objects)
            return objects
        except FileNotFoundError:
            print(f"Error: file not found {path}")
            sys.exit(1)
        except OSError as error:
            print(f"Error reading file: {error}")
            sys.exit(1)
        except SyntaxError as error:
            print(f"Syntax error: {error}")
            sys.exit(1)
        except Exception as error:
            print(f"Compilation error: {error}")
            sys.exit(1)


main()
