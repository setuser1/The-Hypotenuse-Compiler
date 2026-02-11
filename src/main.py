import argparse
import sys
import lexer
import parser as p
import structure


def parse_args():
    """Parse command‑line arguments using argparse."""
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


def main():
    args = parse_args()
    # -------------------------------------------------
    #  Token‑only mode (-t / --tokens)
    # -------------------------------------------------
    if args.tokens:
        if not args.files:
            print("Error: no input file provided for token printing")
            sys.exit(1)
        try:
            with open(args.files[0], "r") as file:
                content = file.read()
            tokenizer = lexer.Lexer(content)
            tokens = tokenizer.lex()
            tokens.append(("EOF", "EOF"))

            # Use Structure module to handle the token list.
            # Use the real parser module (which now has the recursion bug fixed).
            parser = p
            struct = structure.Structor(tokens, parser)
            objects = struct.build_and_sort()
            print(tokens)
            print("Objects (including parent scopes):", objects)
            return objects
        except FileNotFoundError:
            print(f"Error: file not found {args.files[0]}")
            sys.exit(1)
        sys.exit(0)

    # -------------------------------------------------
    #  Normal compilation path (one or more files)
    # -------------------------------------------------
    if not args.files:
        print("Error: no input file provided")
        sys.exit(1)
    for path in args.files:
        try:
            with open(path, "r") as file:
                content = file.read()
            tokenizer = lexer.Lexer(content)
            tokens = tokenizer.lex()
            tokens.append(("EOF", "EOF"))

            # Pass the parser module for consistency.
            parser = p
            # Use Structure module for each file's token stream.
            struct = structure.Structor(tokens, parser)
            objects = struct.build_and_sort()
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
            print(f"Lexing error: {error}")
            sys.exit(1)


main()
