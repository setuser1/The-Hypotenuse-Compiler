import sys
import parser as parse
from lexer import get_tokens

help_options = """
      usage: python3 main.py [file..] or
      python3 main.py [option...] [file..]
      
      --help, -h: displays this help message
      -o: output to file
      -t: print tokens
      -a: show asm 
      """

def args():
    """ Command line argument parser. """
    match sys.argv[1]:
        case '--help':
            print(help_options)
        case '-h':
            print(help_options)
        case '-o':
            pass
        case '-t':
            try:
                with open(sys.argv[2], "r") as file:
                    content = file.read()
                tokens = get_tokens(content)
            except FileNotFoundError:
                print(f"Error: file not found {sys.argv[1]}")
                sys.exit(1)
            print(tokens)
            sys.exit(0)


def main():
    if 2 < len(sys.argv) <= 3:
        args()
    elif len(sys.argv) < 3:
        #Catch errors with try and except
        try:
            with open(sys.argv[1], "r") as file:
                content = file.read()
                tokens = get_tokens(content)
            # Debug:
            # Add this to verify EOF works: print(tokens[-1])
            tokens.append(('EOF', 'EOF'))
            print(tokens)
            print("\n")
            parse.main(tokens)
        except FileNotFoundError as error:
            try:
                args()
            except:
                print(f"Error: file not found {sys.argv[1]}")
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
    else:
        error_msg = f"Usage: main.py [option...] [file..]"
        print(error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
