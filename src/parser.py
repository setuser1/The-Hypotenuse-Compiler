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
from typing import Any, List, Optional, Tuple

Tokens = [
    # COMMENTS
    ("COMMENT_MULTI"),
    ("COMMENT_LINE"),
    # PREPROCESSOR DIRECTIVES (e.g. #include, #define, #if, #endif, etc.)
    ("PREPROCESSOR"),
    # KEYWORDS
    ("IF"),
    ("ELSE"),
    ("WHILE"),
    ("FOR"),
    ("RETURN"),
    ("BREAK"),
    ("CONTINUE"),
    ("SWITCH"),
    ("CASE"),
    ("DEFAULT"),
    ("DO"),
    ("GOTO"),
    ("INT"),
    ("CHAR"),
    ("VOID"),
    ("FLOAT"),
    ("DOUBLE"),
    ("SHORT"),
    ("LONG"),
    ("SIGNED"),
    ("UNSIGNED"),
    ("STRUCT"),
    ("UNION"),
    ("ENUM"),
    ("TYPEDEF"),
    ("CONST"),
    ("VOLATILE"),
    ("STATIC"),
    ("EXTERN"),
    ("INLINE"),
    ("REGISTER"),
    ("AUTO"),
    ("SIZEOF"),
    ("RESTRICT"),
    ("BOOLEAN"),
    # DATA TYPES
    ("STRING_LITERAL"),
    ("CHAR_LITERAL"),
    ("FLOAT_LITERAL"),
    ("INT_LITERAL"),
    # OPERATORS AND DELIMITERS AND SYMBOLS
    ("INCREMENT"),
    ("PLUS"),
    ("DECREMENT"),
    ("MINUS"),
    ("MULTIPLY"),
    ("DIVIDE"),
    ("POWER"),
    ("LPAREN"),
    ("RPAREN"),
    ("ASSIGN"),
    ("SEMICOLON"),
    ("COMMA"),
    ("COLON"),
    ("LE"),
    ("GE"),
    ("LT"),
    ("GT"),
    ("NOT"),
    ("AND"),
    ("OR"),
    ("DOT"),
    ("ARROW"),
    ("LBRACKET"),
    ("RBRACKET"),
    ("LBRACE"),
    ("RBRACE"),
    # IDENTIFIERS
    ("IDENTIFIER"),
    # OTHERS
    ("WHITESPACE"),
    ("UNKNOWN"),
]
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

    ret_type: str  # Return type
    name: str  # Function identifier
    params: List[Tuple[str, str]]  # (type, name) parameter list
    body: Node  # Function body (Compound)


@dataclass
class Declaration(Node):
    """Variable declaration or function prototype."""

    var_type: str
    name: str
    initializer: Optional[Node]  # Optional initializer expression


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
        self.i = 0  # Current token index
        self.var = var  # Optional external state

    # -------------------------
    # Token helpers
    # -------------------------

    def peek(self):
        """Return current token without consuming it."""
        return self.tokens[self.i]

    def advance(self):
        """Consume and return current token."""
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def expect(self, type_name: str):
        """Consume token of expected type or raise syntax error."""
        tok = self.peek()
        if tok[0] == type_name:
            return self.advance()
        # ``tok`` is a (type, lexeme) tuple; it has no position information.
        # Use the parser's current index as a simple position indicator.
        raise SyntaxError(
            f"Expected {type_name} at token index {self.i}, got {tok[0]} ({tok[1]!r})"
        )

    def accept(self, type_name: str):
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
        while self.peek()[0] != "EOF":
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
        #Deprecated keyword error handler for replaced/useless keywords
        #REMOVE MULTILINE COMMENTS FOR THIS WHEN THESE ARE REPLACED/DEPRECATED FULLY
        if t[0] in (
            "RESTRICT",
            "BOOLEAN",
            "COMPLEX",
            "IMAGINARY",
        ):
            raise SyntaxError(
                f"Deprecated keyword used! Please remove or replace the keyword. "
                f"Found '{t[0]}'."
            )
        # COMMENTS ARE SKIPPED
        if t[0] in (
            "COMMENT_MULTI",
            "COMMENT_LINE",
        ):
            self.advance()
            return self.parse_external()
        if t[0] in (
            "INT",
            "CHAR",
            "VOID",
            "FLOAT",
            "DOUBLE",
            "SHORT",
            "LONG",
            "SIGNED",
            "UNSIGNED",
            "STRUCT",
            "UNION",
            "ENUM",
            "TYPEDEF",
            "CONST",
            "VOLATILE",
            "STATIC",
            "EXTERN",
            "INLINE",
            "REGISTER",
            "AUTO",
            "SIZEOF",
            "UNKNOWN",
        ):
            typ = self.advance()[1]
            # Expected Identifier error handling            
            if self.peek()[0] != "IDENTIFIER":
                bad_tok = self.peek()
                raise SyntaxError(
                    f"Expected identifier. "
                    f"Declaration keyword '{typ}' was followed by a non-identifier token. "
                    f"Got '{bad_tok[0]}'."
                )
            name = self.advance()[1]
            # Function or prototype
            if self.accept("LPAREN"):
                params = []

                if not self.accept("RPAREN"):
                    while True:
                        ptype = self.advance()[1]
                        pname = self.expect("IDENTIFIER")[1]
                        params.append((ptype, pname))
                        if self.accept("COMMA"):
                            continue
                        self.expect("RPAREN")
                        break

                # Function definition vs prototype
                if self.peek()[0] == "LBRACE":
                    return Function(typ, name, params, self.parse_compound())
                else:
                    self.expect("SEMICOLON")
                    return Declaration(f"{typ} (func prototype)", name, None)

            # Global variable
            init = self.parse_expression() if self.accept("ASSIGN") else None
            self.expect("SEMICOLON")
            return Declaration(typ, name, init)

        raise SyntaxError(f"Unexpected token at top-level: {t}")

    # ============================================================
    # Statements
    # ============================================================

    def parse_statement(self) -> Node:
        """Parse a single statement."""
        t = self.peek()

        if t[0] == "LBRACE":
            return self.parse_compound()

        if t[0] == "IF":
            self.advance()
            self.expect("LPAREN")
            cond = self.parse_expression()
            self.expect("RPAREN")
            then_branch = self.parse_statement()
            else_branch = self.parse_statement() if self.accept("ELSE") else None
            return If(cond, then_branch, else_branch)

        if t[0] == "WHILE":
            self.advance()
            self.expect("LPAREN")
            cond = self.parse_expression()
            self.expect("RPAREN")
            return While(cond, self.parse_statement())

        if t[0] == "RETURN":
            self.advance()
            expr = self.parse_expression() if self.peek()[0] != "SEMICOLON" else None
            self.expect("SEMICOLON")
            return Return(expr)

        # Local declaration
        #Deprecated keyword error handler for replaced/useless keywords
        #REMOVE MULTILINE COMMENTS FOR THIS WHEN THESE ARE REPLACED/DEPRECATED FULLY
        """if t[0] in (
            "RESTRICT",
            "BOOLEAN",
            "COMPLEX",
            "IMAGINARY",
        ):
            raise SyntaxError(
                f"Deprecated keyword used! Please remove or replace the keyword. "
                f"Found '{t[0]}'."
            )"""
        if t[0] in (
            "INT",
            "CHAR",
            "VOID",
            "FLOAT",
            "DOUBLE",
            "LONG",
            "SHORT",
            "SIGNED",
            "UNSIGNED",
            "STRUCT",
            "UNION",
            "ENUM",
            "BOOLEAN",
        ):
            typ = self.advance()[1]
            if self.peek()[0] != "IDENTIFIER":
                bad_tok = self.peek()
                raise SyntaxError(
                    f"Expected identifier. "
                    f"Declaration keyword '{typ}' was followed by a non-identifier token. "
                    f"Got '{bad_tok[0]}'."
                )
            name = self.advance()[1]
            init = self.parse_expression() if self.accept("ASSIGN") else None
            self.expect("SEMICOLON")
            return Declaration(typ, name, init)

        # Expression statement
        expr = self.parse_expression() if self.peek()[0] != "SEMICOLON" else None
        self.expect("SEMICOLON")
        return ExprStmt(expr)

    def parse_compound(self) -> Compound:
        """Parse a block scope."""
        self.expect("LBRACE")
        stmts = []
        while self.peek()[0] != "RBRACE":
            stmts.append(self.parse_statement())
        self.expect("RBRACE")
        return Compound(stmts)

    # ============================================================
    # Expressions (precedence climbing)
    # ============================================================

    def parse_expression(self) -> Node:
        return self.parse_assignment()

    def parse_assignment(self) -> Node:
        node = self.parse_conditional()
        if self.accept("ASSIGN"):
            return Assignment(node, self.parse_assignment())
        return node

    def parse_conditional(self) -> Node:
        node = self.parse_logical_or()
        if self.accept("QUESTION"):
            t = self.parse_expression()
            self.expect("COLON")
            f = self.parse_conditional()
            return Binary("?:", node, Binary("branch", t, f))
        return node

    def parse_logical_or(self) -> Node:
        """
        Old order: Logical OR -> Primary
        New order: Logical OR -> Unary -> Primary
        """
        left = self.parse_add()
        while self.peek()[0] == "OR":
            op = self.advance()[1]
            right = self.parse_add()
            left = Binary(op, left, right)
        return left

    def parse_add(self) -> Node:
        """
        Parse addition and subtraction expressions.
        """
        left = self.parse_term()
        while self.peek()[0] in ("PLUS", "MINUS"):
            op = self.advance()[1]
            right = self.parse_term()
            left = Binary(op, left, right)
        return left

    def parse_term(self) -> Node:
        """
        Parse multiplication and division expressions.
        """
        left = self.parse_unary()
        while self.peek()[0] in ("MULTIPLY", "DIVIDE"):
            op = self.advance()[1]
            right = self.parse_unary()
            left = Binary(op, left, right)
        return left

    def parse_unary(self):
        """Parse unary prefix expression (e.g., -x, !y)."""
        # checks if current token is a unary operator
        token = self.peek()
        if token[0] in ("PLUS", "MINUS", "NOT"):
            op = self.advance()[1]
            operand = self.parse_unary()
            return Unary(op=op, operand=operand, prefix=True)
        return self.parse_primary()

    def parse_power(self) -> Node:
        """Parse exponentiation expressions (right-associative)."""
        left = self.parse_unary()
        if self.accept("POWER"):
            right = self.parse_power()  # Right-associative
            return Binary("**", left, right)
        return left

    # -----------------------------------------------------------------
    # Primary expression helper (identifiers, literals, parenthesised expr)
    # -----------------------------------------------------------------
    def parse_primary(self) -> Node:
        """Parse the most basic expression forms."""
        tok = self.peek()
        if tok[0] == "IDENTIFIER":
            # Variable reference
            return Var(self.advance()[1])
        if tok[0] in ("INT_LITERAL", "FLOAT_LITERAL", "STRING_LITERAL"):
            # Literal constant
            return Literal(self.advance()[1])
        if tok[0] == "LPAREN":
            # Parenthesised sub‑expression
            self.advance()
            expr = self.parse_expression()
            self.expect("RPAREN")
            return expr
        raise SyntaxError(f"Unexpected token {tok} in primary expression")



# ============================================================
# AST Pretty Printer
# ============================================================


def pretty(node: Node, indent: int = 0) -> str:
    """Human-readable AST dump."""
    pad = "  " * indent
    return pad + repr(node) + "\n"


# ============================================================
# Entry point
# ============================================================


def main(tokens):
    """Parse tokens and print AST."""
    parser = Parser(tokens)
    ast = parser.parse_program()
    print(pretty(ast))
