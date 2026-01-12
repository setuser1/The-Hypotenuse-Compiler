import sys
import parser as parse
import argparse
from lexer import get_tokens

def parse_args():
    """Parse command‑line arguments using argparse."""
    parser = argparse.ArgumentParser(
        prog="hypotenuse",
        description="C triangle compiler.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "files", nargs="*", help="Source file(s) to compile"
    )
    parser.add_argument(
        "-t", "--tokens", action="store_true",
        help="Print lexical tokens and exit"
    )
    parser.add_argument(
        "-o", "--output", metavar="PATH",
        help="Write compiled output to PATH (not yet implemented)"
    )
    parser.add_argument(
        "-a", "--asm", action="store_true",
        help="Show generated assembly"
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
            tokens = get_tokens(content)
        except FileNotFoundError:
            print(f"Error: file not found {args.files[0]}")
            sys.exit(1)
        print(tokens)
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
            tokens = get_tokens(content)
            # Append EOF token as the original script expected
            tokens.append(('EOF', 'EOF'))
            print(tokens)
            print("\n")
            parse.main(tokens)
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


if __name__ == "__main__":
    main()
