import sys
from lexer import Lexer
from parser import Parser, pretty

def parse_text(text):
    tokens = Lexer(text).tokenize()
    parser = Parser(tokens)
    ast = parser.parse_program()
    print(pretty(ast))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = sys.argv[1]
        with open(path, 'r', encoding='utf-8') as f:
            src = f.read()
        parse_text(src)
    else:
        sample = r'''
        int add(int a, int b) {
            int c = a + b;
            return c;
        }

        int main() {
            int x = 3;
            long y = 0x10;
            float f = 1.23e-1;
            int z = add(x, (int) y);
            if (z > 5) {
                z++;
            } else {
                z--;
            }
            return 0;
        }
        '''
        parse_text(sample)
