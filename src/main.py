import sys
import parser as parse
from lexer import get_tokens


def main():
  if len(sys.argv) != 2:
    print("Usage: python main.py <source-file>")
    sys.exit(1)
  #Catch errors with try and except
  try:
    with open(sys.argv[1], "r") as file:
      content = file.read()
  except FileNotFoundError:
    print(f"Error: file not found {sys.argv[1]}")
    sys.exit(1)
  except OSError as e:
    print(f"Error reading file: {e}")
    sys.exit(1)
  except SyntaxError as e:
    print(f"Syntax error: {e}")
    sys.exit(1)
  except Exception as e:
    print(f"Lexing error: {e}")
    sys.exit(1)
  tokens = get_tokens(content)
  #Debug: 
  #Add this to verify EOF works: print(tokens[-1])
  tokens.append(('EOF', 'EOF'))
  print(tokens)
  parse.main(tokens)

if __name__ == "__main__":
  main()
