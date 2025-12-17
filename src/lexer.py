import re    #not in use yet, will be used later on

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

#function to get token list goes here
