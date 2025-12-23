import re
import sys
#order matters, there might be errors if certain elements are not in the right order

Tokens = [
    # COMMENTS
    ('COMMENT_MULTI', re.compile(r'/\*.*?\*/', re.DOTALL)),
    ('COMMENT_LINE', re.compile(r'//[^\n]*')),

    #KEYWORDS
    ('IF', re.compile(r'\bif\b')),
    ('ELSE', re.compile(r'\belse\b')),
    ('WHILE', re.compile(r'\bwhile\b')),
    ('FOR', re.compile(r'\bfor\b')),
    ('RETURN', re.compile(r'\breturn\b')),
    ('BREAK', re.compile(r'\bbreak\b')),
    ('CONTINUE', re.compile(r'\bcontinue\b')),
    ('SWITCH', re.compile(r'\bswitch\b')),
    ('CASE', re.compile(r'\bcase\b')),
    ('DEFAULT', re.compile(r'\bdefault\b')),
    ('DO', re.compile(r'\bdo\b')),
    ('GOTO', re.compile(r'\bgoto\b')),

    
    ('INT', re.compile(r'\bint\b')),
    ('CHAR', re.compile(r'\bchar\b')),
    ('VOID', re.compile(r'\bvoid\b')),
    ('FLOAT', re.compile(r'\bfloat\b')),
    ('DOUBLE', re.compile(r'\bdouble\b')),
    ('SHORT', re.compile(r'\bshort\b')),
    ('LONG', re.compile(r'\blong\b')),
    ('SIGNED', re.compile(r'\bsigned\b')),
    ('UNSIGNED', re.compile(r'\bunsigned\b')),
    ('STRUCT', re.compile(r'\bstruct\b')),
    ('UNION', re.compile(r'\bunion\b')),
    ('ENUM', re.compile(r'\benum\b')),
    ('TYPEDEF', re.compile(r'\btypedef\b')),
    ('CONST', re.compile(r'\bconst\b')),
    ('VOLATILE', re.compile(r'\bvolatile\b')),
    ('STATIC', re.compile(r'\bstatic\b')),
    ('EXTERN', re.compile(r'\bextern\b')),
    ('INLINE', re.compile(r'\binline\b')),
    ('REGISTER', re.compile(r'\bregister\b')),
    ('AUTO', re.compile(r'\bauto\b')),
    ('SIZEOF', re.compile(r'\bsizeof\b')),
    ('RESTRICT', re.compile(r'\brestrict\b')),    
    ('BOOLEAN', re.compile(r'\b_Bool\b')),

    #DATA TYPES
    ('STRING LITERAL', re.compile(r'"[^"]*"')),
    ('DOUBLE LITERAL', re.compile(r'\b\d+\.\d+\b')),
    ('LONG LITERAL', re.compile(r'\b\d+\b')),

    
    #OPERATORS AND DELIMITERS AND SYMBOLS
    ('INCREMENT', re.compile(r'\+\+')),
    ('PLUS', re.compile(r'\+')),
    ('DECREMENT', re.compile(r'--')),
    ('MINUS', re.compile(r'-')),
    ('MULTIPLY', re.compile(r'\*')),
    ('DIVIDE', re.compile(r'/')),
    ('LPAREN', re.compile(r'\(')),
    ('RPAREN', re.compile(r'\)')),
    ('ASSIGN', re.compile(r'=')),
    ('SEMICOLON', re.compile(r';')),
    ('COMMA', re.compile(r',')),
    ('COLON', re.compile(r':')),
    ('LE', re.compile(r'<=')),
    ('GE', re.compile(r'>=')),
    ('LT', re.compile(r'<')),
    ('GT', re.compile(r'>')),
    ('NOT', re.compile(r'!')),
    ('AND', re.compile(r'&&')),
    ('OR', re.compile(r'\|\|')),
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

def get_tokens(argv):
    var = argv[1]
    tokens = []
    
    while var:
        for token in Tokens:
            match = token[1].match(var)
            if match:
                lexeme = match.group(0)
                if token[0] != 'WHITESPACE':
                    tokens.append((Token[0], lexeme))
                var = var[len(lexeme):]
                break
        else:
            tokens.append(('UNKNOWN', var[0]))
            var = var[1:]
    return tokens
if __name__ == "__main__":
    if len(sys.argv) < 2:
        exit()
    else:
        with open(sys.argv, 'r') as file:
                content = file.read()
        token_list = get_tokens(content)
        for t in token_list:
            print(f"Token: {t[0]}, Lexeme {t[1]}")
            
