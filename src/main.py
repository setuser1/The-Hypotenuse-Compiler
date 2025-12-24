import sys
import parser as parse
from lexer import get_tokens


def main():
  if len(sys.argv) != 2:
    print("Usage: python main.py <source-file>")
    sys.exit(1)
  #Catch file errors with try and except
  try:
    with open(sys.argv[1], "r") as file:
      content = file.read()
  except FileNotFoundError:
    print(f"Error: file not found {sys.argv[1]}")
    sys.exit(1)
  tokens = get_tokens(content)
  #Add this to verify EOF works: print(tokens[-1])
  tokens.append(('EOF', 'EOF'))
  print(tokens)
  parse.main(tokens)

if __name__ == "__main__":
  main()
