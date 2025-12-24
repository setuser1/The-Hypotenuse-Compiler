import sys
import parser as parse
from lexer import get_tokens

def main():
    if len(sys.argv) < 2:
        print("yo no way it works???")
        sys.exit(1)
    with open(sys.argv[1], "r") as file:
        content = file.read()
    tokens = get_tokens(content)
    tokens.append(('EOF', 'EOF'))
    parse.main(tokens)

if __name__ == "__main__":
    main()