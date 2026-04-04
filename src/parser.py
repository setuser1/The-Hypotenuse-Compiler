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
class Switch(Node):
    """Switch statement with case labels."""

    expr: Node
    cases: List[Tuple[Optional[Node], Node]]  # (case_value, body) - None for default


@dataclass
class Case(Node):
    """Case label within a switch."""

    value: Optional[Node]  # None for default case
    body: Node


@dataclass
class Return(Node):
    """Return statement."""

    expr: Optional[Node]


@dataclass
class Break(Node):
    """Break statement."""

    pass


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
    """Unary operation (prefix or postfix).

    prefix=True  -> prefix operator  (e.g. -x, !y, ++x, --x)
    prefix=False -> postfix operator (e.g. x++, x--)
    """

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
class TypeExpr(Node):
    """Type expression (used in va_arg and casts)."""

    type_name: str


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


@dataclass
class Cast(Node):
    """C-style cast expression: (type) expr"""

    cast_type: str
    operand: Node


# ============================================================
# Recursive-Descent Parser
# ============================================================


class Parser:
    """
    Recursive-descent parser for a C-like language.

    Implements operator precedence via layered parsing functions.

    Precedence (low -> high):
      assignment
      conditional (?:)
      logical or  (||)
      logical and (&&)
      equality    (== !=)
      relational  (< > <= >=)
      additive    (+ -)
      multiplicative (* /)
      power       (**)
      unary prefix  (- ! + ++ --)
      postfix       (call, subscript, ++ --)
      primary       (literal, identifier, grouped)
    """

    def __init__(self, tokens, var=None):
        self.tokens = tokens
        self.i = 0  # Current token index
        self.var = var  # Optional external state

    # -------------------------
    # Token helpers
    # -------------------------

    def peek(self):
        """Return current token without consuming it.

        Returns an ('EOF', '') sentinel when the token stream is exhausted
        so callers never receive an IndexError.
        """
        if self.i < len(self.tokens):
            return self.tokens[self.i]
        return ("EOF", "")

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

        # Preprocessor directives and comments are skipped silently.
        # C△ does not process #include / #define etc. — those are handled
        # by the C backend after code generation.
        if t[0] in ("PREPROCESSOR", "COMMENT_MULTI", "COMMENT_LINE"):
            self.advance()
            return self.parse_external()

        # Reject deprecated / removed keywords immediately.
        if t[0] in ("RESTRICT", "BOOLEAN"):
            raise SyntaxError(
                f"Deprecated keyword used! Please remove or replace the keyword. "
                f"Found '{t[0]}'."
            )

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
            # Handle compound types: long long, unsigned long, etc.
            if self.peek()[0] in (
                "INT",
                "CHAR",
                "VOID",
                "FLOAT",
                "DOUBLE",
                "SHORT",
                "LONG",
                "SIGNED",
                "UNSIGNED",
            ):
                typ2 = self.advance()[1]
                typ = f"{typ} {typ2}"
            # Handle pointer type: int* ptr or char** ptr2
            while self.peek()[0] == "MULTIPLY":
                self.advance()
                typ += "*"
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
                        # Handle type qualifiers (const, volatile, etc.)
                        type_qualifiers = []
                        while self.peek()[0] in ("CONST", "VOLATILE"):
                            type_qualifiers.append(self.advance()[1])

                        ptype = self.advance()[1]
                        # Handle compound types in parameters (e.g., long long, unsigned long)
                        if self.peek()[0] in (
                            "INT",
                            "CHAR",
                            "VOID",
                            "FLOAT",
                            "DOUBLE",
                            "SHORT",
                            "LONG",
                            "SIGNED",
                            "UNSIGNED",
                        ):
                            ptype2 = self.advance()[1]
                            ptype = f"{ptype} {ptype2}"
                        # Handle pointer types in parameters (e.g., const char* s)
                        while self.peek()[0] == "MULTIPLY":
                            self.advance()
                            ptype += "*"

                        # Prepend qualifiers if any
                        if type_qualifiers:
                            ptype = " ".join(type_qualifiers) + " " + ptype

                        pname = self.expect("IDENTIFIER")[1]
                        params.append((ptype, pname))
                        if self.accept("COMMA"):
                            # Handle variadic functions with ...
                            if self.accept("ELLIPSIS"):
                                params.append(("...", "..."))
                                self.expect("RPAREN")
                                break
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

        # Skip preprocessor directives and comments inside function bodies too
        if t[0] in ("PREPROCESSOR", "COMMENT_MULTI", "COMMENT_LINE"):
            self.advance()
            return self.parse_statement()

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

        if t[0] == "FOR":
            self.advance()
            self.expect("LPAREN")
            init = None
            if self.peek()[0] != "SEMICOLON":
                if self.peek()[0] in (
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
                ):
                    typ = self.advance()[1]
                    idtok = self.expect("IDENTIFIER")
                    name = idtok[1]
                    init = Declaration(var_type=typ, name=name, initializer=None)
                    if self.accept("ASSIGN"):
                        init.initializer = self.parse_expression()
                else:
                    init = self.parse_expression()
            self.expect("SEMICOLON")
            cond = None
            if self.peek()[0] != "SEMICOLON":
                cond = self.parse_expression()
            self.expect("SEMICOLON")
            post = None
            if self.peek()[0] != "RPAREN":
                post = self.parse_expression()
            self.expect("RPAREN")
            body = self.parse_statement()
            return For(init=init, cond=cond, post=post, body=body)

        if t[0] == "RETURN":
            self.advance()
            expr = self.parse_expression() if self.peek()[0] != "SEMICOLON" else None
            self.expect("SEMICOLON")
            return Return(expr)

        if t[0] == "BREAK":
            self.advance()
            self.expect("SEMICOLON")
            return Break()

        if t[0] == "CONTINUE":
            self.advance()
            self.expect("SEMICOLON")
            return type("Continue", (), {})()

        if t[0] == "SWITCH":
            self.advance()
            self.expect("LPAREN")
            expr = self.parse_expression()
            self.expect("RPAREN")
            body = self.parse_compound()
            cases = []
            i = 0
            while i < len(body.stmts):
                stmt = body.stmts[i]
                if hasattr(stmt, "case_label"):
                    case_value = stmt.case_label
                    case_body = []
                    i += 1
                    while i < len(body.stmts) and not (
                        hasattr(body.stmts[i], "case_label")
                        or hasattr(body.stmts[i], "is_default")
                    ):
                        case_body.append(body.stmts[i])
                        i += 1
                    cases.append(
                        (case_value, Compound(case_body) if case_body else Compound([]))
                    )
                else:
                    i += 1
            return Switch(expr, cases)

        if t[0] == "CASE":
            case_label_node = type(
                "CaseLabel", (), {"case_label": None, "is_default": False}
            )()
            self.advance()
            case_value = self.parse_expression()
            case_label_node.case_label = case_value
            self.expect("COLON")
            return case_label_node

        if t[0] == "DEFAULT":
            default_label_node = type(
                "DefaultLabel", (), {"case_label": None, "is_default": True}
            )()
            self.advance()
            self.expect("COLON")
            return default_label_node

        # Reject deprecated / removed keywords in statement position too.
        if t[0] in ("RESTRICT", "BOOLEAN"):
            raise SyntaxError(
                f"Deprecated keyword used! Please remove or replace the keyword. "
                f"Found '{t[0]}'."
            )

        # Local declaration
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
            "CONST",
            "VOLATILE",
        ) or (t[0] == "IDENTIFIER" and t[1] in ("va_list",)):
            qualifiers = []
            # Collect any leading type qualifiers
            while self.peek()[0] in ("CONST", "VOLATILE"):
                qualifiers.append(self.advance()[1])

            # Get the base type
            base_type = self.advance()[1]

            # Handle compound types in local declarations (e.g., long long, unsigned long)
            if self.peek()[0] in (
                "INT",
                "CHAR",
                "VOID",
                "FLOAT",
                "DOUBLE",
                "SHORT",
                "LONG",
                "SIGNED",
                "UNSIGNED",
            ):
                base_type2 = self.advance()[1]
                base_type = f"{base_type} {base_type2}"

            # Build the full type: [qualifiers] base_type [pointers]
            typ = base_type
            if qualifiers:
                typ = " ".join(qualifiers) + " " + typ

            # Handle pointer type: int* ptr or char** ptr2
            while self.peek()[0] == "MULTIPLY":
                self.advance()
                typ += "*"

            if self.peek()[0] != "IDENTIFIER":
                bad_tok = self.peek()
                raise SyntaxError(
                    f"Expected identifier. "
                    f"Declaration keyword '{typ}' was followed by a non-identifier token. "
                    f"Got '{bad_tok[0]}'."
                )
            name = self.advance()[1]

            # Handle array declarations: char temp[32]
            if self.peek()[0] == "LBRACKET":
                self.advance()  # consume '['
                if self.peek()[0] == "INT_LITERAL":
                    self.advance()  # consume array size
                self.expect("RBRACKET")

            # Handle initialization - only if followed by '='
            init = None
            if self.peek()[0] == "ASSIGN":
                self.advance()
                init = self.parse_expression()
            elif self.peek()[0] == "LBRACE":
                # Array initializer without '='
                init = self.parse_expression()

            self.expect("SEMICOLON")
            return Declaration(typ, name, init)

        # Expression statement
        expr = self.parse_expression() if self.peek()[0] != "SEMICOLON" else None
        self.expect("SEMICOLON")
        return ExprStmt(expr)

    def parse_compound(self) -> Compound:
        """Parse a block scope.

        Raises a clean SyntaxError if EOF is reached before the closing
        brace, rather than propagating an IndexError from peek().
        """
        self.expect("LBRACE")
        stmts = []
        while True:
            t = self.peek()
            if t[0] == "RBRACE":
                break
            if t[0] == "EOF":
                raise SyntaxError(
                    "Unexpected end of file: unclosed '{' — missing closing '}'"
                )
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
        # Handle compound assignment operators (+=, -=, *=, /=, %=, etc.)
        compound_ops = [
            "PLUS_ASSIGN",
            "MINUS_ASSIGN",
            "MULTIPLY_ASSIGN",
            "DIVIDE_ASSIGN",
            "MOD_ASSIGN",
        ]
        for op in compound_ops:
            if self.accept(op):
                # Convert += to op = node + value
                op_name = op.replace("_ASSIGN", "")  # += -> +
                # Create the compound assignment: node = node + value
                right = self.parse_assignment()
                return Assignment(node, Binary(op_name, node, right))
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
        """Parse logical OR expressions (||)."""
        left = self.parse_logical_and()
        while self.peek()[0] == "OR":
            op = self.advance()[1]
            right = self.parse_logical_and()
            left = Binary(op, left, right)
        return left

    def parse_logical_and(self) -> Node:
        """Parse logical AND expressions (&&)."""
        left = self.parse_equality()
        while self.peek()[0] == "AND":
            op = self.advance()[1]
            right = self.parse_equality()
            left = Binary(op, left, right)
        return left

    def parse_equality(self) -> Node:
        """Parse equality expressions (== !=)."""
        left = self.parse_relational()
        while self.peek()[0] in ("EQ", "NEQ"):
            op = self.advance()[1]
            right = self.parse_relational()
            left = Binary(op, left, right)
        return left

    def parse_relational(self) -> Node:
        """Parse relational expressions (< > <= >=)."""
        left = self.parse_add()
        while self.peek()[0] in ("LT", "GT", "LE", "GE"):
            op = self.advance()[1]
            right = self.parse_add()
            left = Binary(op, left, right)
        return left

    def parse_add(self) -> Node:
        """Parse addition and subtraction expressions."""
        left = self.parse_term()
        while self.peek()[0] in ("PLUS", "MINUS"):
            op = self.advance()[1]
            right = self.parse_term()
            left = Binary(op, left, right)
        return left

    def parse_term(self) -> Node:
        """Parse multiplication and division expressions."""
        left = self.parse_power()
        while self.peek()[0] in ("MULTIPLY", "DIVIDE", "MODULO"):
            op = self.advance()[1]
            right = self.parse_power()
            left = Binary(op, left, right)
        return left

    def parse_power(self) -> Node:
        """Parse exponentiation expressions (right-associative)."""
        left = self.parse_unary()
        if self.accept("POWER"):
            right = self.parse_power()  # Right-associative
            return Binary("**", left, right)
        return left

    def parse_unary(self) -> Node:
        """Parse unary prefix expressions (e.g. -x, !y, ++x, --x)."""
        token = self.peek()
        if token[0] in ("PLUS", "MINUS", "NOT"):
            op = self.advance()[1]
            operand = self.parse_unary()
            return Unary(op=op, operand=operand, prefix=True)
        if token[0] in ("INCREMENT", "DECREMENT"):
            op = self.advance()[1]
            operand = self.parse_unary()
            return Unary(op=op, operand=operand, prefix=True)
        if token[0] == "MULTIPLY":
            self.advance()
            operand = self.parse_unary()
            return Unary(op="*", operand=operand, prefix=True)
        if token[0] == "AMPERSAND":
            self.advance()
            operand = self.parse_unary()
            return Unary(op="&", operand=operand, prefix=True)
        return self.parse_postfix()

    def parse_postfix(self) -> Node:
        """Parse postfix expressions: calls, subscripts, and x++/x--."""
        node = self.parse_primary()
        while True:
            if self.peek()[0] == "LPAREN":
                # Function call: expr(arg, ...)
                self.advance()
                args = []
                if self.peek()[0] != "RPAREN":
                    # Check if first arg is a type keyword (for va_arg)
                    if self.peek()[0] in (
                        "INT",
                        "CHAR",
                        "VOID",
                        "FLOAT",
                        "DOUBLE",
                        "SHORT",
                        "LONG",
                        "SIGNED",
                        "UNSIGNED",
                    ):
                        args.append(self.parse_type_expression())
                    else:
                        args.append(self.parse_assignment())
                    while self.accept("COMMA"):
                        # Check if subsequent args are type keywords
                        if self.peek()[0] in (
                            "INT",
                            "CHAR",
                            "VOID",
                            "FLOAT",
                            "DOUBLE",
                            "SHORT",
                            "LONG",
                            "SIGNED",
                            "UNSIGNED",
                        ):
                            args.append(self.parse_type_expression())
                        else:
                            args.append(self.parse_assignment())
                self.expect("RPAREN")
                node = Call(node, args)
            elif self.peek()[0] == "LBRACKET":
                # Array subscript: expr[index]
                self.advance()
                index = self.parse_expression()
                self.expect("RBRACKET")
                node = ArrayAccess(node, index)
            elif self.peek()[0] in ("INCREMENT", "DECREMENT"):
                # Postfix ++/--: expr++ / expr--
                op = self.advance()[1]
                node = Unary(op=op, operand=node, prefix=False)
            else:
                break
        return node

    def parse_type_expression(self) -> Node:
        """Parse a type keyword or compound type (e.g., int, long long)."""
        if self.peek()[0] in (
            "INT",
            "CHAR",
            "VOID",
            "FLOAT",
            "DOUBLE",
            "SHORT",
            "LONG",
            "SIGNED",
            "UNSIGNED",
        ):
            type1 = self.advance()[1]
            # Handle compound types like long long, unsigned long, etc.
            if self.peek()[0] in (
                "INT",
                "CHAR",
                "VOID",
                "FLOAT",
                "DOUBLE",
                "SHORT",
                "LONG",
                "SIGNED",
                "UNSIGNED",
            ):
                type2 = self.advance()[1]
                type1 = f"{type1} {type2}"
            # Handle pointer types in type expressions (e.g., char*)
            while self.peek()[0] == "MULTIPLY":
                self.advance()
                type1 += "*"
            return TypeExpr(type1)
        raise SyntaxError(f"Expected type keyword, got {self.peek()}")

    def parse_primary(self) -> Node:
        """Parse the most basic expression forms."""
        tok = self.peek()
        if tok[0] == "IDENTIFIER":
            return Var(self.advance()[1])
        if tok[0] in ("INT_LITERAL", "FLOAT_LITERAL", "STRING_LITERAL", "CHAR_LITERAL"):
            return Literal(self.advance()[1])
        if tok[0] == "LPAREN":
            self.advance()
            if self.peek()[0] in (
                "INT",
                "CHAR",
                "VOID",
                "FLOAT",
                "DOUBLE",
                "SHORT",
                "LONG",
                "SIGNED",
                "UNSIGNED",
                "CONST",
                "VOLATILE",
            ):
                type_node = self.parse_type_expression()
                while self.peek()[0] == "MULTIPLY":
                    self.advance()
                    type_node.type_name += "*"
                self.expect("RPAREN")
                operand = self.parse_unary()
                return Cast(cast_type=type_node.type_name, operand=operand)
            expr = self.parse_expression()
            self.expect("RPAREN")
            return expr
        if tok[0] in (
            "INT",
            "CHAR",
            "VOID",
            "FLOAT",
            "DOUBLE",
            "SHORT",
            "LONG",
            "SIGNED",
            "UNSIGNED",
        ):
            return TypeExpr(self.advance()[1])
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
