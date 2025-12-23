from lexer import Token, get_tokens
import sys
import parser as parse


def main(sys.argv):
  with open(sys.argv, "r") as file:
    content = file.read()
  tokens = get_tokens(content[0])
  parse.main(tokens)

main()
