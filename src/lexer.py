import re
import sys
#order matters, there might be errors if certain elements are not in the right order

Tokens = [


    #KEYWORDS
    ('IF', re.compile(r'\bif\b')),
    ('ELSE', re.compile(r'\belse\b')),
    ('WHILE', re.compile(r'\bwhile\b')),
    ('FOR', re.compile(r'\bfor\b')),
    ('RETURN', re.compile(r'\breturn\b')),
    ('INT', re.compile(r'\bint\b')),
    ('CHAR', re.compile(r'\bchar\b')),
    ('VOID', re.compile(r'\bvoid\b')),
    ('FLOAT', re.compile(r'\bfloat\b')),
    ('BOOLEAN', re.compile(r'\b_Bool\b'))

    #DATA TYPES
    ('STRING LITERAL', re.compile(r'"[^"]*"')),
    ('DOUBLE LITERAL', re.compile(r'\b\d+\.\d+\b')),
    ('LONG LITERAL', re.compile(r'\b\d+\b')),

    
    #OPERATORS AND DELIMITERS AND SYMBOLS
    ('PLUS', re.compile(r'\+')),
    ('MINUS', re.compile(r'-')),
    ('MULTIPLY', re.compile(r'\*')),
    ('DIVIDE', re.compile(r'/')),
    ('LPAREN', re.compile(r'\(')),
    ('RPAREN', re.compile(r'\)')),
    ('ASSIGN', re.compile(r'=')),
    ('SEMICOLON', re.compile(r';')),
    ('COMMA', re.compile(r',')),
    ('COLON', re.compile(r':')),
    ('LT', re.compile(r'<')),
    ('GT', re.compile(r'>')),
    ('LE', re.compile(r'<=')),
    ('GE', re.compile(r'>=')),
    ('NOT', re.compile(r'!')),
    ('AND', re.compile(r'&&')),
    ('OR', re.compile(r'\|\|')),
    ('INCREMENT', re.compile(r'\+\+')),
    ('DECREMENT', re.compile(r'--')),
    ('DOT', re.compile(r'\.')),
    ('ARROW', re.compile(r'->')),
    ('LBRACKET', re.compile(r'\[')),
    ('RBRACKET', re.compile(r'\]')),
    ('LBRACE', re.compile(r'\{')),
    ('RBRACE', re.compile(r'\}')),

    #IDENTIFIERS
    ('IDENTIFIER', re.compile(r'[A-Za-z_][A-Za-z0-9_]*')),

    #OTHERS
    ('WHITESPACE', re.compile(r'\s+'))
]

#under construction, not finished yet, and will not work properly
#function to get token list goes here
def get_tokens(argv):
    # here turns the input into a list then cuts it into smaller parts
    var = argv[1]
    while var:
        for token in Tokens:
            match = token[1].match(var)
            if match:
                lexeme = match.group(0)
                if token[0] != 'WHITESPACE':  #skip whitespace tokens
                    print(f'Token: {token[0]}, Lexeme: {lexeme}')
                var = var[len(lexeme):]  #move forward in the input string
                break
        else:
            print(f'Unknown token: {var[0]}')
            var = var[1:]  #skip unknown character

if __name__ == "__main__":
    if len(sys.argv) < 2:
        exit()
    else:
        get_tokens(sys.argv)
