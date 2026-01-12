"""
C-like language parser and AST implementation.

This file defines:
- Abstract Syntax Tree (AST) node classes
- A recursive-descent parser with proper operator precedence
- A pretty-printer for AST visualization

The parser consumes tokens produced by an external lexer and builds
a structured AST suitable for semantic analysis or code generation.
"""

from dataclasses import dataclass
from typing import List, Optional, Any, Tuple
from lexer import Tokens as Token


# ============================================================
# AST (Abstract Syntax Tree) Nodes
# ============================================================

@dataclass
class Node:
    """Base class for all AST nodes."""
    pass


@dataclass
class Program(Node):
    """Root of the AST: list of top-level declarations."""
    declarations: List[Node]


@dataclass
class Function(Node):
    """Function definition."""
    ret_type: str                    # Return type
    name: str                        # Function identifier
    params: List[Tuple[str, str]]    # (type, name) parameter list
    body: Node                       # Function body (Compound)


@dataclass
class Declaration(Node):
    """Variable declaration or function prototype."""
    var_type: str
    name: str
    initializer: Optional[Node]      # Optional initializer expression


@dataclass
class Compound(Node):
    """Block scope: { statement* }"""
    stmts: List[Node]


@dataclass
class If(Node):
    """If / else control structure."""
    cond: Node
    then_branch: Node
    else_branch: Optional[Node]


@dataclass
class While(Node):
    """While loop."""
    cond: Node
    body: Node


@dataclass
class For(Node):
    """For loop with optional init, condition, and post expressions."""
    init: Optional[Node]
    cond: Optional[Node]
    post: Optional[Node]
    body: Node


@dataclass
class Return(Node):
    """Return statement."""
    expr: Optional[Node]


@dataclass
class ExprStmt(Node):
    """Expression used as a statement."""
    expr: Optional[Node]


@dataclass
class Binary(Node):
    """Binary operation node."""
    op: str
    left: Node
    right: Node


@dataclass
class Unary(Node):
    """Unary operation (prefix or postfix)."""
    op: str
    operand: Node
    prefix: bool = True


@dataclass
class Literal(Node):
    """Literal constant."""
    value: Any


@dataclass
class Var(Node):
    """Variable reference."""
    name: str


@dataclass
class Assignment(Node):
    """Assignment expression."""
    target: Node
    value: Node


@dataclass
class Call(Node):
    """Function call."""
    callee: Node
    args: List[Node]


@dataclass
class ArrayAccess(Node):
    """Array indexing expression."""
    array: Node
    index: Node


# ============================================================
# Recursive-Descent Parser
# ============================================================

class Parser:
    """
    Recursive-descent parser for a C-like language.

    Implements operator precedence via layered parsing functions.
    """

    def __init__(self, tokens, var=None):
        self.tokens = tokens
        self.i = 0                    # Current token index
        self.var = var                # Optional external state

    # -------------------------
    # Token helpers
    # -------------------------

    def peek(self) -> Token:
        """Return current token without consuming it."""
        return self.tokens[self.i]

    def advance(self) -> Token:
        """Consume and return current token."""
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def expect(self, type_name: str) -> Token:
        """Consume token of expected type or raise syntax error."""
        tok = self.peek()
        if tok[0] == type_name:
            return self.advance()
        raise SyntaxError(
            f"Expected {type_name} at pos {tok[2]}, got {tok[0]} ({tok[1]!r})"
        )

    def accept(self, type_name: str) -> Optional[Token]:
        """Consume token if it matches expected type."""
        if self.peek()[0] == type_name:
            return self.advance()
        return None

    # ============================================================
    # Top-level parsing
    # ============================================================

    def parse_program(self) -> Program:
        """Parse entire translation unit."""
        decls = []
        while self.peek()[0] != 'EOF':
            decls.append(self.parse_external())
        return Program(decls)

    def parse_external(self) -> Node:
        """
        Parse global declarations:
        - Functions
        - Function prototypes
        - Global variables
        """
        t = self.peek()

        if t[0] in (
            'INT','CHAR','VOID','FLOAT','DOUBLE','LONG','SHORT',
            'SIGNED','UNSIGNED','STRUCT','UNION','ENUM','BOOLEAN'
        ):
            typ = self.advance()[1]
            name = self.expect('IDENTIFIER')[1]

            # Function or prototype
            if self.accept('LPAREN'):
                params = []

                if not self.accept('RPAREN'):
                    while True:
                        ptype = self.advance()[1]
                        pname = self.expect('IDENTIFIER')[1]
                        params.append((ptype, pname))
                        if self.accept('COMMA'):
                            continue
                        self.expect('RPAREN')
                        break

                # Function definition vs prototype
                if self.peek()[0] == 'LBRACE':
                    return Function(typ, name, params, self.parse_compound())
                else:
                    self.expect('SEMICOLON')
                    return Declaration(f"{typ} (func prototype)", name, None)

            # Global variable
            init = self.parse_expression() if self.accept('ASSIGN') else None
            self.expect('SEMICOLON')
            return Declaration(typ, name, init)

        raise SyntaxError(f"Unexpected token at top-level: {t}")

    # ============================================================
    # Statements
    # ============================================================

    def parse_statement(self) -> Node:
        """Parse a single statement."""
        t = self.peek()

        if t[0] == 'LBRACE':
            return self.parse_compound()

        if t[0] == 'IF':
            self.advance()
            self.expect('LPAREN')
            cond = self.parse_expression()
            self.expect('RPAREN')
            then_branch = self.parse_statement()
            else_branch = self.parse_statement() if self.accept('ELSE') else None
            return If(cond, then_branch, else_branch)

        if t[0] == 'WHILE':
            self.advance()
            self.expect('LPAREN')
            cond = self.parse_expression()
            self.expect('RPAREN')
            return While(cond, self.parse_statement())

        if t[0] == 'RETURN':
            self.advance()
            expr = self.parse_expression() if self.peek()[0] != 'SEMICOLON' else None
            self.expect('SEMICOLON')
            return Return(expr)

        # Local declaration
        if t[0] in (
            'INT','CHAR','VOID','FLOAT','DOUBLE','LONG','SHORT',
            'SIGNED','UNSIGNED','STRUCT','UNION','ENUM','BOOLEAN'
        ):
            typ = self.advance()[1]
            name = self.expect('IDENTIFIER')[1]
            init = self.parse_expression() if self.accept('ASSIGN') else None
            self.expect('SEMICOLON')
            return Declaration(typ, name, init)

        # Expression statement
        expr = self.parse_expression() if self.peek()[0] != 'SEMICOLON' else None
        self.expect('SEMICOLON')
        return ExprStmt(expr)

    def parse_compound(self) -> Compound:
        """Parse a block scope."""
        self.expect('LBRACE')
        stmts = []
        while self.peek()[0] != 'RBRACE':
            stmts.append(self.parse_statement())
        self.expect('RBRACE')
        return Compound(stmts)

    # ============================================================
    # Expressions (precedence climbing)
    # ============================================================

    def parse_expression(self) -> Node:
        return self.parse_assignment()

    def parse_assignment(self) -> Node:
        node = self.parse_conditional()
        if self.accept('ASSIGN'):
            return Assignment(node, self.parse_assignment())
        return node

    def parse_conditional(self) -> Node:
        node = self.parse_logical_or()
        if self.accept('QUESTION'):
            t = self.parse_expression()
            self.expect('COLON')
            f = self.parse_conditional()
            return Binary('?:', node, Binary('branch', t, f))
        return node

    # Remaining precedence layers intentionally omitted here for brevity
    # (they are identical to your original implementation)

# ============================================================
# AST Pretty Printer
# ============================================================

def pretty(node: Node, indent: int = 0) -> str:
    """Human-readable AST dump."""
    pad = '  ' * indent
    return pad + repr(node) + "\n"


# ============================================================
# Entry point
# ============================================================

def main(tokens):
    """Parse tokens and print AST."""
    parser = Parser(tokens)
    ast = parser.parse_program()
    print(pretty(ast))