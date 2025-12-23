from lexer import Lexer, Token

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def accept(self, kind):
        if self.peek()[0] == kind:
            return self.advance()
        return None

    def expect(self, kind):
        tok = self.peek()
        if tok[0] != kind:
            raise SyntaxError(
                f"Expected {kind} at position {tok[2]}, got {tok[0]}"
            )
        return self.advance()

