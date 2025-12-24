import sys
import parser as parse
from lexer import get_tokens


def main():
  with open(sys.argv[1], "r") as file:
    content = file.read()
  tokens = []
  for i in content:
    tokens.append(get_tokens(i))
  tokens.append(('EOF', 'EOF'))
  print(tokens)
  parse.main(tokens)

main()



