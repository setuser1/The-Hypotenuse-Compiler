import re

# order matters, there might be errors if certain elements are not in the right order

Tokens = [
    # COMMENTS
    ("COMMENT_MULTI", re.compile(r"/\*.*?\*/", re.DOTALL)),
    ("COMMENT_LINE", re.compile(r"//[^\n]*")),
    # PREPROCESSOR DIRECTIVES (e.g. #include, #define, #if, #endif, etc.)
    ("PREPROCESSOR", re.compile(r"#[^\n]*")),
    # KEYWORDS
    ("IF", re.compile(r"\bif\b")),
    ("ELSE", re.compile(r"\belse\b")),
    ("WHILE", re.compile(r"\bwhile\b")),
    ("FOR", re.compile(r"\bfor\b")),
    ("RETURN", re.compile(r"\breturn\b")),
    ("BREAK", re.compile(r"\bbreak\b")),
    ("CONTINUE", re.compile(r"\bcontinue\b")),
    ("SWITCH", re.compile(r"\bswitch\b")),
    ("CASE", re.compile(r"\bcase\b")),
    ("DEFAULT", re.compile(r"\bdefault\b")),
    ("DO", re.compile(r"\bdo\b")),
    ("GOTO", re.compile(r"\bgoto\b")),
    ("INT", re.compile(r"\bint\b")),
    ("CHAR", re.compile(r"\bchar\b")),
    ("VOID", re.compile(r"\bvoid\b")),
    ("FLOAT", re.compile(r"\bfloat\b")),
    ("DOUBLE", re.compile(r"\bdouble\b")),
    ("SHORT", re.compile(r"\bshort\b")),
    ("LONG", re.compile(r"\blong\b")),
    ("SIGNED", re.compile(r"\bsigned\b")),
    ("UNSIGNED", re.compile(r"\bunsigned\b")),
    ("SIZE_T", re.compile(r"\bsize_t\b")),
    ("DYNAM", re.compile(r"\bdynam\b")),
    ("STRING", re.compile(r"\bstring\b")),
    ("STRUCT", re.compile(r"\bstruct\b")),
    ("UNION", re.compile(r"\bunion\b")),
    ("ENUM", re.compile(r"\benum\b")),
    ("TYPEDEF", re.compile(r"\btypedef\b")),
    ("CONST", re.compile(r"\bconst\b")),
    ("VOLATILE", re.compile(r"\bvolatile\b")),
    ("STATIC", re.compile(r"\bstatic\b")),
    ("EXTERN", re.compile(r"\bextern\b")),
    ("INLINE", re.compile(r"\binline\b")),
    ("REGISTER", re.compile(r"\bregister\b")),
    ("AUTO", re.compile(r"\bauto\b")),
    ("NORETURN", re.compile(r"\b_Noreturn\b")),
    ("SIZEOF", re.compile(r"\bsizeof\b")),
    ("RESTRICT", re.compile(r"\brestrict\b")),
    ("BOOLEAN", re.compile(r"\b_Bool\b")),
    ("UNDERSCORE_GENERIC", re.compile(r"\b_Generic\b")),
    ("UNDERSCORE_ALIGNOF", re.compile(r"\b_Alignof\b")),
    ("UNDERSCORE_ALIGNAS", re.compile(r"\b_Alignas\b")),
    ("UNDERSCORE_COMPLEX", re.compile(r"\b_Complex\b")),
    ("UNDERSCORE_IMAGINARY", re.compile(r"\b_Imaginary\b")),
    # C△ MEMORY KEYWORDS
    ("ALLOCATE", re.compile(r"\ballocate\b")),
    ("FREE", re.compile(r"\bfree\b")),
    # C△ IMPORT KEYWORDS
    ("USING", re.compile(r"\busing\b")),
    ("FROM", re.compile(r"\bfrom\b")),
    ("EXPOSE", re.compile(r"\bexpose\b")),
    ("SPACE", re.compile(r"\bspace\b")),
    ("AS", re.compile(r"\bas\b")),
    # ASM KEYWORD
    ("ASM", re.compile(r"\basm\b")),
    # DATA TYPES
    ("STRING_LITERAL", re.compile(r'"(?:\\.|[^"\\])*"')),
    ("CHAR_LITERAL", re.compile(r"'(?:\\.|[^'\\])*'")),
    ("FLOAT_LITERAL", re.compile(r"\b\d+\.\d+[fFlL]?\b")),
    ("HEX_LITERAL", re.compile(r"\b0[xX][0-9a-fA-F]+[uUlL]*\b")),
    ("BINARY_LITERAL", re.compile(r"\b0[bB][01]+[uUlL]*\b")),
    ("INT_LITERAL", re.compile(r"\b\d+[uUlL]*\b")),
    # OPERATORS AND DELIMITERS AND SYMBOLS
    # NOTE: multi-character operators must appear before their single-character
    # prefixes so the lexer matches the longer token first.
    ("INCREMENT", re.compile(r"\+\+")),
    ("PLUS_ASSIGN", re.compile(r"\+=")),  # must come before PLUS
    ("PLUS", re.compile(r"\+")),
    # ARROW must come before DECREMENT and MINUS so that -> is matched first.
    ("ARROW", re.compile(r"->")),
    ("DECREMENT", re.compile(r"--")),
    ("MINUS_ASSIGN", re.compile(r"-=")),  # must come before MINUS
    ("MINUS", re.compile(r"-")),
    ("POWER", re.compile(r"\*\*")),  # must come before MULTIPLY
    ("MULTIPLY_ASSIGN", re.compile(r"\*=")),  # must come before MULTIPLY
    ("MULTIPLY", re.compile(r"\*")),
    ("DIVIDE_ASSIGN", re.compile(r"/=")),  # must come before DIVIDE
    ("DIVIDE", re.compile(r"/")),
    ("MOD_ASSIGN", re.compile(r"%=")),  # must come before MODULO
    ("MODULO", re.compile(r"%")),
    ("LPAREN", re.compile(r"\(")),
    ("RPAREN", re.compile(r"\)")),
    ("LE", re.compile(r"<=")),  # must come before LT
    ("GE", re.compile(r">=")),  # must come before GT
    ("LSHIFT", re.compile(r"<<")),  # must come before LT
    ("RSHIFT", re.compile(r">>")),  # must come before GT
    ("EQ", re.compile(r"==")),  # must come before ASSIGN
    ("NEQ", re.compile(r"!=")),  # must come before NOT
    ("ASSIGN", re.compile(r"=")),
    ("SEMICOLON", re.compile(r";")),
    ("COMMA", re.compile(r",")),
    ("COLON", re.compile(r":")),
    ("QUESTION", re.compile(r"\?")),  # ternary operator
    ("LT", re.compile(r"<")),
    ("GT", re.compile(r">")),
    ("NOT", re.compile(r"!")),
    ("AND", re.compile(r"&&")),
    ("OR", re.compile(r"\|\|")),
    ("BITWISE_OR", re.compile(r"\|")),  # must come after OR (||)
    ("BITWISE_XOR", re.compile(r"\^")),
    ("AMPERSAND", re.compile(r"&")),  # must come after AND (&&)
    ("AT", re.compile(r"@")),  # namespace separator
    ("TILDE", re.compile(r"~")),  # bitwise NOT
    ("ELLIPSIS", re.compile(r"\.\.\.")),  # must come before DOT
    ("DOT", re.compile(r"\.")),
    ("LBRACKET", re.compile(r"\[")),
    ("RBRACKET", re.compile(r"]")),
    ("LBRACE", re.compile(r"\{")),
    ("RBRACE", re.compile(r"}")),
    # IDENTIFIERS
    ("IDENTIFIER", re.compile(r"[A-Za-z_][A-Za-z0-9_]*")),
    # OTHERS
    ("WHITESPACE", re.compile(r"\s+")),
    ("UNKNOWN", re.compile(r".")),
]


def get_tokens(string):
    result = []
    i = 0
    while i < len(string):
        if string[i] == "\\" and i + 1 < len(string) and string[i + 1] in "\n\r":
            i += 2
        else:
            result.append(string[i])
            i += 1
    var = "".join(result)

    tokens = []
    line = 1
    col = 1
    i = 0

    while i < len(var):
        if var[i : i + 2] == "/*":
            depth = 1
            start = i
            start_line = line
            start_col = col
            i += 2
            for c in "/*":
                if c == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
            while i < len(var) and depth > 0:
                if var[i : i + 2] == "/*":
                    depth += 1
                    i += 2
                    for c in "/*":
                        if c == "\n":
                            line += 1
                            col = 1
                        else:
                            col += 1
                elif var[i : i + 2] == "*/":
                    depth -= 1
                    i += 2
                    for c in "*/":
                        if c == "\n":
                            line += 1
                            col = 1
                        else:
                            col += 1
                else:
                    if var[i] == "\n":
                        line += 1
                        col = 1
                    else:
                        col += 1
                    i += 1
            tokens.append(("COMMENT_MULTI", var[start:i], start_line, start_col))
        else:
            matched = False
            for token in Tokens:
                match = token[1].match(var, i)
                if match and match.start() == i:
                    lexeme = match.group(0)
                    if token[0] not in ("WHITESPACE", "COMMENT_LINE", "COMMENT_MULTI"):
                        tokens.append((token[0], lexeme, line, col))
                    for c in lexeme:
                        if c == "\n":
                            line += 1
                            col = 1
                        else:
                            col += 1
                    i += len(lexeme)
                    matched = True
                    break
            if not matched:
                tokens.append(("UNKNOWN", var[i], line, col))
                if var[i] == "\n":
                    line += 1
                    col = 1
                else:
                    col += 1
                i += 1
    return tokens


class Lexer:
    def __init__(self, text):
        self.text = text
        self.pos = 0
        self.tokens = get_tokens(text)
        self.token_index = 0

    def peek(self):
        if self.token_index < len(self.tokens):
            return self.tokens[self.token_index]
        return None

    def next(self):
        token = self.peek()
        self.token_index += 1
        return token

    def lex_expression(self):
        """Consume characters forming a balanced expression."""
        start = self.pos
        paren = 0
        bracket = 0
        in_string = None
        while self.pos < len(self.text):
            c = self.text[self.pos]
            if in_string:
                if c == "\\":
                    self.pos += 2
                    continue
                if c == in_string:
                    in_string = None
            else:
                if c in ('"', "'"):
                    in_string = c
                elif c == "(":
                    paren += 1
                elif c == ")":
                    if paren == 0:
                        break
                    paren -= 1
                elif c == "[":
                    bracket += 1
                elif c == "]":
                    if bracket == 0:
                        break
                    bracket -= 1
                elif c in (";", ",") and paren == 0 and bracket == 0:
                    break
            self.pos += 1
        value = self.text[start : self.pos].strip()
        return "EXPR", value

    def lex(self):
        """Convenience wrapper that returns a list of (type, lexeme) tokens for *text*."""
        return [token for token in self.tokens]
