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


def compile_file(path):
    """Lex, parse, and structure a single source file.

    Returns the ordered list of Callee/Caller graph objects.
    """
    with open(path, "r") as f:
        content = f.read()

    # Lex
    tokens = lexer.Lexer(content).lex()
    tokens.append(("EOF", "EOF"))

    # Parse tokens -> AST
    ast = p.Parser(tokens).parse_program()

    # Build Callee/Caller/Scope graph from AST
    structor = structure.Structor(ast)
    return structor.build_from_ast()


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
            with open(args.files[0], "r") as f:
                content = f.read()
            tokens = lexer.Lexer(content).lex()
            tokens.append(("EOF", "EOF"))
            print(tokens)

            ast = p.Parser(tokens).parse_program()
            structor = structure.Structor(ast)
            objects = structor.build_from_ast()
            print("Objects (including parent scopes):", objects)
            return objects
        except FileNotFoundError:
            print(f"Error: file not found {args.files[0]}")
            sys.exit(1)

    # -------------------------------------------------
    #  Normal compilation path (one or more files)
    # -------------------------------------------------
    if not args.files:
        print("Error: no input file provided")
        sys.exit(1)

    for path in args.files:
        try:
            objects = compile_file(path)
            print("Objects (including parent scopes):", objects)
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
