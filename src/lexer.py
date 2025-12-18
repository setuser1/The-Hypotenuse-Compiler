import re    #not in use yet, will be used later on
# whoever comments unnecessarily will be murdered
#order matters, there might be errors if certain elements are not in the right order

Tokens = [
    # Keywords (use raw strings for \b)
    ('PRINT', r'\bprint\b'),
    ('IF', r'\bif\b'),
    ('ELSE', r'\belse\b'),
    ('ELIF', r'\belif\b'),
    ('WHILE', r'\bwhile\b'),
    ('FOR', r'\bfor\b'),
    ('RETURN', r'\breturn\b'),
    ('FUNCTION', r'\bfunction\b'),
    ('VAR', r'\bvar\b'),

    # Data types
    ('FLOAT', r'\d+\.\d+'),
    ('INTEGER', r'\d+'),
    ('STRING', r'"(.*?)"'),

    # Operators and delimiters
    ('PLUS', r'\+'),
    ('MINUS', r'-'),
    ('MULTIPLY', r'\*'),
    ('DIVIDE', r'/'),
    ('LPAREN', r'\('),
    ('RPAREN', r'\)'),
    ('ASSIGN', r'='),
    ('SEMICOLON', r';'),
    ('COMMA', r','),
    ('COLON', r':'),

    # Identifiers (after keywords)
    ('IDENTIFIER', r'[A-Za-z_][A-Za-z0-9_]*'),

    # Whitespace (skip)
    ('WHITESPACE', r'\s+')
]

#under construction, not finished yet, and will not work properly
#function to get token list goes here
def get_tokens():
    var = input() #input for source code
    # here turns the input into a list then cuts it into smaller parts
    while True:
        for token in Tokens:
            pattern = re.compile(token[1])
            match = pattern.match(var)
            if match:
                lexeme = match.group(0)
                if token[0] != 'WHITESPACE':  #skip whitespace tokens
                    print(f'Token: {token[0]}, Lexeme: {lexeme}')
                var = var[len(lexeme):]  #move forward in the input string
                break
        else:
            print(f'Unknown token: {var[0]}')
            var = var[1:]  #skip unknown character
