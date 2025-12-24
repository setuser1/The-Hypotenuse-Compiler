from dataclasses import dataclass
from typing import List, Optional, Any, Tuple
from lexer import Tokens as Token

# ast data classes
@dataclass
class Node:
    pass

@dataclass
class Program(Node):
    declarations: List[Node]

@dataclass
class Function(Node):
    ret_type: str
    name: str
    params: List[Tuple[str, str]]
    body: Node

@dataclass
class Declaration(Node):
    var_type: str
    name: str
    initializer: Optional[Node]

@dataclass
class Compound(Node):
    stmts: List[Node]

@dataclass
class If(Node):
    cond: Node
    then_branch: Node
    else_branch: Optional[Node]

@dataclass
class While(Node):
    cond: Node
    body: Node

@dataclass
class For(Node):
    init: Optional[Node]
    cond: Optional[Node]
    post: Optional[Node]
    body: Node

@dataclass
class Return(Node):
    expr: Optional[Node]

@dataclass
class ExprStmt(Node):
    expr: Optional[Node]

@dataclass
class Binary(Node):
    op: str
    left: Node
    right: Node

@dataclass
class Unary(Node):
    op: str
    operand: Node
    prefix: bool = True

@dataclass
class Literal(Node):
    value: Any

@dataclass
class Var(Node):
    name: str

@dataclass
class Assignment(Node):
    target: Node
    value: Node

@dataclass
class Call(Node):
    callee: Node
    args: List[Node]

@dataclass
class ArrayAccess(Node):
    array: Node
    index: Node

# parser
class Parser:
    def __init__(self, tokens, var=None):
        self.var = var
        self.tokens = tokens
        self.i = 0

    def peek(self) -> Token:
        return self.tokens[self.i]

    def advance(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def expect(self, type_name: str) -> Token:
        tok = self.peek()
        if tok[0] == type_name:
            return self.advance()
        raise SyntaxError(f"Expected {type_name} at pos {tok[2]}, got {tok[0]} ({tok[1]!r})")

    def accept(self, type_name: str) -> Optional[Token]:
        tok = self.peek()
        if tok[0] == type_name:
            return self.advance()
        return None

    # top level
    def parse_program(self) -> Program:
        decls = []
        while self.peek()[0] != 'EOF':
            decls.append(self.parse_external())
        return Program(decls)

    def parse_external(self) -> Node:
        t = self.peek()
        if t[0] in ('INT','CHAR','VOID','FLOAT','DOUBLE','LONG','SHORT','SIGNED','UNSIGNED','STRUCT','UNION','ENUM','BOOLEAN'):
            typ = self.advance()[1]
            idtok = self.expect('IDENTIFIER')
            name = idtok[1]
            if self.accept('LPAREN'):
                params = []
                if not self.accept('RPAREN'):
                    while True:
                        ptype_tok = self.peek()
                        if ptype_tok[0] not in ('INT','CHAR','VOID','FLOAT','DOUBLE','LONG','SHORT','SIGNED','UNSIGNED','STRUCT','UNION','ENUM','BOOLEAN'):
                            raise SyntaxError(f"Expected type in parameter list at pos {ptype_tok[2]} got {ptype_tok[0]}")
                        ptype = self.advance()[1]
                        pname_tok = self.expect('IDENTIFIER')
                        pname = pname_tok[1]
                        params.append((ptype, pname))
                        if self.accept('COMMA'):
                            continue
                        self.expect('RPAREN')
                        break
                # function body or prototype
                if self.peek()[0] == 'LBRACE':
                    body = self.parse_compound()
                    return Function(ret_type=typ, name=name, params=params, body=body)
                else:
                    self.expect('SEMICOLON')
                    return Declaration(var_type=f"{typ} (func prototype)", name=name, initializer=None)
            else:
                # variable declaration
                init = None
                if self.accept('ASSIGN'):
                    init = self.parse_expression()
                self.expect('SEMICOLON')
                return Declaration(var_type=typ, name=name, initializer=init)
        else:
            raise SyntaxError(f"Unexpected token at top-level: {t}")

    # statements
    def parse_statement(self) -> Node:
        t = self.peek()
        if t[0] == 'LBRACE':
            return self.parse_compound()
        if t[0] == 'IF':
            self.advance()
            self.expect('LPAREN')
            cond = self.parse_expression()
            self.expect('RPAREN')
            then_branch = self.parse_statement()
            else_branch = None
            if self.accept('ELSE'):
                else_branch = self.parse_statement()
            return If(cond=cond, then_branch=then_branch, else_branch=else_branch)
        if t[0] == 'WHILE':
            self.advance()
            self.expect('LPAREN')
            cond = self.parse_expression()
            self.expect('RPAREN')
            body = self.parse_statement()
            return While(cond=cond, body=body)
        if t[0] == 'FOR':
            self.advance()
            self.expect('LPAREN')
            init = None
            if self.peek()[0] != 'SEMICOLON':
                # could be declaration or expression
                if self.peek()[0] in ('INT','CHAR','VOID','FLOAT','DOUBLE','LONG','SHORT','SIGNED','UNSIGNED','STRUCT','UNION','ENUM','BOOLEAN'):
                    # local declaration
                    typ = self.advance()[1]
                    idtok = self.expect('IDENTIFIER')
                    name = idtok[1]
                    init = Declaration(var_type=typ, name=name, initializer=None)
                    if self.accept('ASSIGN'):
                        init.initializer = self.parse_expression()
                else:
                    init = self.parse_expression()
            self.expect('SEMICOLON')
            cond = None
            if self.peek()[0] != 'SEMICOLON':
                cond = self.parse_expression()
            self.expect('SEMICOLON')
            post = None
            if self.peek()[0] != 'RPAREN':
                post = self.parse_expression()
            self.expect('RPAREN')
            body = self.parse_statement()
            return For(init=init, cond=cond, post=post, body=body)
        if t[0] == 'RETURN':
            self.advance()
            expr = None
            if self.peek()[0] != 'SEMICOLON':
                expr = self.parse_expression()
            self.expect('SEMICOLON')
            return Return(expr=expr)
        # local declaration
        if t[0] in ('INT','CHAR','VOID','FLOAT','DOUBLE','LONG','SHORT','SIGNED','UNSIGNED','STRUCT','UNION','ENUM','BOOLEAN'):
            typ = self.advance()[1]
            idtok = self.expect('IDENTIFIER')
            name = idtok[1]
            init = None
            if self.accept('ASSIGN'):
                init = self.parse_expression()
            self.expect('SEMICOLON')
            return Declaration(var_type=typ, name=name, initializer=init)
        # expression statement
        expr = None
        if self.peek()[0] != 'SEMICOLON':
            expr = self.parse_expression()
        self.expect('SEMICOLON')
        return ExprStmt(expr=expr)

    def parse_compound(self) -> Compound:
        self.expect('LBRACE')
        stmts = []
        while self.peek()[0] != 'RBRACE':
            stmts.append(self.parse_statement())
        self.expect('RBRACE')
        return Compound(stmts=stmts)



    def parse_expression(self) -> Node:
        return self.parse_assignment()

    def parse_assignment(self) -> Node:
        node = self.parse_conditional()
        if self.accept('ASSIGN'):
            rhs = self.parse_assignment()
            return Assignment(target=node, value=rhs)
        return node

    def parse_conditional(self) -> Node:
        node = self.parse_logical_or()
        if self.accept('QUESTION'):
            true_expr = self.parse_expression()
            self.expect('COLON')
            false_expr = self.parse_conditional()  # right associative
            return Binary(op='?:', left=node, right=Binary(op='branch', left=true_expr, right=false_expr))
        return node

    def parse_logical_or(self) -> Node:
        node = self.parse_logical_and()
        while self.accept('OR'):
            rhs = self.parse_logical_and()
            node = Binary(op='||', left=node, right=rhs)
        return node

    def parse_logical_and(self) -> Node:
        node = self.parse_bitwise_or()
        while self.accept('AND'):
            rhs = self.parse_bitwise_or()
            node = Binary(op='&&', left=node, right=rhs)
        return node

    def parse_bitwise_or(self) -> Node:
        node = self.parse_bitwise_xor()
        while self.accept('BITOR'):
            rhs = self.parse_bitwise_xor()
            node = Binary(op='|', left=node, right=rhs)
        return node

    def parse_bitwise_xor(self) -> Node:
        node = self.parse_bitwise_and()
        while self.accept('XOR'):
            rhs = self.parse_bitwise_and()
            node = Binary(op='^', left=node, right=rhs)
        return node

    def parse_bitwise_and(self) -> Node:
        node = self.parse_equality()
        while self.accept('BITAND'):
            rhs = self.parse_equality()
            node = Binary(op='&', left=node, right=rhs)
        return node

    def parse_equality(self) -> Node:
        node = self.parse_relational()
        while True:
            if self.accept('EQ'):
                rhs = self.parse_relational()
                node = Binary(op='==', left=node, right=rhs)
            elif self.accept('NE'):
                rhs = self.parse_relational()
                node = Binary(op='!=', left=node, right=rhs)
            else:
                break
        return node


    def parse_relational(self) -> Node:
        node = self.parse_shifts()
        while True:
            if self.accept('LT'):
                rhs = self.parse_shifts()
                node = Binary(op='<', left=node, right=rhs)
            elif self.accept('GT'):
                rhs = self.parse_shifts()
                node = Binary(op='>', left=node, right=rhs)
            elif self.accept('LE'):
                rhs = self.parse_shifts()
                node = Binary(op='<=', left=node, right=rhs)
            elif self.accept('GE'):
                rhs = self.parse_shifts()
                node = Binary(op='>=', left=node, right=rhs)
            else:
                break
        return node

    def parse_shifts(self) -> Node:
        node = self.parse_additive()
        while True:
            if self.accept('LSHIFT'):
                rhs = self.parse_additive()
                node = Binary(op='<<', left=node, right=rhs)
            elif self.accept('RSHIFT'):
                rhs = self.parse_additive()
                node = Binary(op='>>', left=node, right=rhs)
            else:
                break
        return node

    def parse_additive(self) -> Node:
        node = self.parse_multiplicative()
        while True:
            if self.accept('PLUS'):
                rhs = self.parse_multiplicative()
                node = Binary(op='+', left=node, right=rhs)
            elif self.accept('MINUS'):
                rhs = self.parse_multiplicative()
                node = Binary(op='-', left=node, right=rhs)
            else:
                break
        return node

    def parse_multiplicative(self) -> Node:
        node = self.parse_unary()
        while True:
            if self.accept('MULTIPLY'):
                rhs = self.parse_unary()
                node = Binary(op='*', left=node, right=rhs)
            elif self.accept('DIVIDE'):
                rhs = self.parse_unary()
                node = Binary(op='/', left=node, right=rhs)
            elif self.accept('MODULO'):
                rhs = self.parse_unary()
                node = Binary(op='%', left=node, right=rhs)
            else:
                break
        return node

    def parse_unary(self) -> Node:
        if self.accept('PLUS'):
            return Unary(op='+', operand=self.parse_unary(), prefix=True)
        if self.accept('MINUS'):
            return Unary(op='-', operand=self.parse_unary(), prefix=True)
        if self.accept('NOT'):
            return Unary(op='!', operand=self.parse_unary(), prefix=True)
        if self.accept('TILDE'):
            return Unary(op='~', operand=self.parse_unary(), prefix=True)
        if self.accept('INCREMENT'):
            return Unary(op='++', operand=self.parse_unary(), prefix=True)
        if self.accept('DECREMENT'):
            return Unary(op='--', operand=self.parse_unary(), prefix=True)
        return self.parse_postfix()

    def parse_postfix(self) -> Node:
        node = self.parse_primary()
        while True:
            if self.accept('LPAREN'):
                args = []
                if not self.accept('RPAREN'):
                    while True:
                        args.append(self.parse_expression())
                        if self.accept('COMMA'):
                            continue
                        self.expect('RPAREN')
                        break
                node = Call(callee=node, args=args)
            elif self.accept('LBRACKET'):
                idx = self.parse_expression()
                self.expect('RBRACKET')
                node = ArrayAccess(array=node, index=idx)
            elif self.accept('INCREMENT'):
                node = Unary(op='++', operand=node, prefix=False)
            elif self.accept('DECREMENT'):
                node = Unary(op='--', operand=node, prefix=False)
            else:
                break
        return node

    def parse_primary(self) -> Node:
        tok = self.peek()
        if tok[0] == 'IDENTIFIER':
            self.advance()
            return Var(name=tok[1])
        if tok[0] == 'STRING_LITERAL':
            self.advance()
            return Literal(value=tok[1])
        if tok[0] == 'CHAR_LITERAL':
            self.advance()
            return Literal(value=tok[1])
        if tok[0] == 'FLOAT_LITERAL':
            self.advance()
            try:
                val = float(tok[1])
            except:
                val = tok[1]
            return Literal(value=val)
        if tok[0] == 'HEX_LITERAL':
            self.advance()
            return Literal(value=int(tok[1], 16))
        if tok[0] == 'BIN_LITERAL':
            self.advance()
            return Literal(value=int(tok[1], 2))
        if tok[0] == 'INT_LITERAL':
            self.advance()
            return Literal(value=int(tok[1]))
        if tok[0] == 'LPAREN':
            self.advance()
            e = self.parse_expression()
            self.expect('RPAREN')
            return e
        raise SyntaxError(f"Unexpected token in expression at pos {tok[2]}: {tok}")

# pretty printer for ast
def pretty(node: Node, indent: int = 0) -> str:
    pad = '  ' * indent
    if isinstance(node, Program):
        s = pad + "Program:\n"
        for d in node.declarations:
            s += pretty(d, indent+1)
        return s
    if isinstance(node, Function):
        s = pad + f"Function: {node.ret_type} {node.name}({', '.join(t+' '+n for t,n in node.params)})\n"
        s += pretty(node.body, indent+1)
        return s
    if isinstance(node, Declaration):
        s = pad + f"Declaration: {node.var_type} {node.name}"
        if node.initializer:
            s += " =\n" + pretty(node.initializer, indent+1)
        else:
            s += "\n"
        return s
    if isinstance(node, Compound):
        s = pad + "Compound:\n"
        for st in node.stmts:
            s += pretty(st, indent+1)
        return s
    if isinstance(node, If):
        s = pad + "If:\n"
        s += pad + "  Cond:\n" + pretty(node.cond, indent+2)
        s += pad + "  Then:\n" + pretty(node.then_branch, indent+2)
        if node.else_branch:
            s += pad + "  Else:\n" + pretty(node.else_branch, indent+2)
        return s
    if isinstance(node, While):
        return pad + "While:\n" + pad + "  Cond:\n" + pretty(node.cond, indent+2) + pad + "  Body:\n" + pretty(node.body, indent+2)
    if isinstance(node, For):
        s = pad + "For:\n"
        s += pad + "  Init:\n" + (pretty(node.init, indent+2) if node.init else pad + "    <none>\n")
        s += pad + "  Cond:\n" + (pretty(node.cond, indent+2) if node.cond else pad + "    <none>\n")
        s += pad + "  Post:\n" + (pretty(node.post, indent+2) if node.post else pad + "    <none>\n")
        s += pad + "  Body:\n" + pretty(node.body, indent+2)
        return s
    if isinstance(node, Return):
        return pad + "Return:\n" + (pretty(node.expr, indent+1) if node.expr else pad + "  <none>\n")
    if isinstance(node, ExprStmt):
        return pad + "ExprStmt:\n" + (pretty(node.expr, indent+1) if node.expr else pad + "  <none>\n")
    if isinstance(node, Binary):
        return pad + f"Binary({node.op}):\n" + pretty(node.left, indent+1) + pretty(node.right, indent+1)
    if isinstance(node, Unary):
        return pad + f"Unary({'prefix' if node.prefix else 'postfix'} {node.op}):\n" + pretty(node.operand, indent+1)
    if isinstance(node, Literal):
        return pad + f"Literal({node.value})\n"
    if isinstance(node, Var):
        return pad + f"Var({node.name})\n"
    if isinstance(node, Assignment):
        return pad + "Assignment:\n" + pretty(node.target, indent+1) + pretty(node.value, indent+1)
    if isinstance(node, Call):
        s = pad + "Call:\n" + pretty(node.callee, indent+1)
        for a in node.args:
            s += pretty(a, indent+1)
        return s
    if isinstance(node, ArrayAccess):
        return pad + "ArrayAccess:\n" + pretty(node.array, indent+1) + pretty(node.index, indent+1)
    return pad + f"UnknownNode:{node}\n"

# example use
def main(tokens):
    p = Parser(tokens)
    ast = p.parse_program()
    print(pretty(ast))




