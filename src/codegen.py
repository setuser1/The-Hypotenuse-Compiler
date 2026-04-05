"""C11 code generator for C△ compiler."""

from parser import (
    Function,
    Declaration,
    Compound,
    If,
    While,
    Do,
    For,
    Return,
    Break,
    Continue,
    Goto,
    Label,
    ExprStmt,
    Binary,
    Unary,
    Literal,
    Var,
    Call,
    ArrayAccess,
    Cast,
    Assignment,
    Include,
    InitList,
    Switch,
    StructDef,
    Typedef,
    FieldAccess,
    DesignatedInit,
    TypeExpr,
    Generic,
    CompoundLiteral,
)


PRECEDENCE = {
    "||": 1,
    "&&": 2,
    "==": 3,
    "!=": 3,
    "<": 4,
    ">": 4,
    "<=": 4,
    ">=": 4,
    "+": 5,
    "-": 5,
    "*": 6,
    "/": 6,
    "%": 6,
    "**": 7,
}


TYPE_MAP = {
    "string": "char*",
    "int": "int",
    "float": "float",
    "double": "double",
    "char": "char",
    "void": "void",
    "short": "short",
    "long": "long",
    "signed": "signed",
    "unsigned": "unsigned",
}


class CodeGen:
    def __init__(self, ast, structor, layouts=None):
        self.ast = ast
        self.structor = structor
        self.layouts = layouts or {}
        self._output = []
        self._indent = 0
        self._last_line_ended_semicolon = False
        self._continuation = False

    def generate(self) -> str:
        """Main entry point. Returns generated C code as string."""
        self._output = []
        self._gen_program(self.ast)
        return "".join(self._output)

    def _emit(self, line: str = "", end: str = "\n"):
        """Emit a line of output with proper indentation."""
        stripped = line.rstrip()
        if len(stripped) > 120:
            stripped = stripped[:117] + "..."

        self._last_line_ended_semicolon = stripped.endswith(";")

        if stripped or end:
            indent = "    " * self._indent
            if self._continuation:
                self._output.append(stripped + end)
                self._continuation = False
            else:
                self._output.append(indent + stripped + end)
            if end == "":
                self._continuation = True

    def _needs_parens(self, expr) -> bool:
        """Check if expression needs parentheses due to precedence."""
        if isinstance(expr, Binary):
            # Don't add parens for comparison operators - they don't need it
            if expr.op in ("==", "!=", "<", ">", "<=", ">="):
                return False
            # Add parens for other operators that might have precedence issues
            if expr.op in ("+", "-", "*", "/", "%"):
                return False
            return True
        if isinstance(expr, Assignment):
            return True
        if isinstance(expr, Call):
            return False
        if isinstance(expr, Unary):
            return False
        return False

    def _get_expr_value(self, node) -> str:
        """Get string representation of an expression."""
        if isinstance(node, Literal):
            val = node.value
            if isinstance(val, str):
                stripped = val.lstrip("-")
                if (
                    stripped.startswith("0x")
                    or stripped.startswith("0X")
                    or stripped.startswith("0b")
                    or stripped.startswith("0B")
                    or (stripped.isdigit() and stripped.startswith("0"))
                ):
                    return val
                if any(
                    stripped.endswith(suffix)
                    for suffix in (
                        "LL",
                        "ll",
                        "U",
                        "u",
                        "UL",
                        "ul",
                        "ULL",
                        "ull",
                        "f",
                        "F",
                        "l",
                        "L",
                    )
                ) or (
                    stripped.replace(".", "", 1)
                    .replace("e", "")
                    .replace("E", "")
                    .isdigit()
                    and any(stripped.endswith(c) for c in "fFeE")
                ):
                    return val
                if stripped.isdigit():
                    return val
                if stripped.replace(".", "", 1).isdigit():
                    return val
                if val.startswith('"') or val.startswith("'"):
                    return val
                return f'"{val}"'
            else:
                return str(val)
        elif isinstance(node, Var):
            return node.name
        elif isinstance(node, Binary):
            left = self._get_expr_value(node.left)
            right = self._get_expr_value(node.right)
            if node.op == "?:":  # ternary operator: condition ? true_val : false_val
                if isinstance(node.right, Binary) and node.right.op == "branch":
                    true_val = self._get_expr_value(node.right.left)
                    false_val = self._get_expr_value(node.right.right)
                    return f"({left}) ? {true_val} : {false_val}"
            if self._needs_parens(node):
                return f"({left} {node.op} {right})"
            return f"{left} {node.op} {right}"
        elif isinstance(node, Unary):
            operand = self._get_expr_value(node.operand)
            if node.op == "sizeof":
                return f"sizeof({operand})"
            elif node.prefix:
                return f"{node.op}{operand}"
            return f"{operand}{node.op}"
        elif isinstance(node, FieldAccess):
            obj = getattr(node, "obj", None)
            field = getattr(node, "field_name", "")
            if obj is not None and hasattr(obj, "name"):
                return f"{obj.name}.{field}"
            return f"field.{field}"
        elif isinstance(node, Call):
            callee = (
                node.callee.name if hasattr(node.callee, "name") else str(node.callee)
            )
            args = ", ".join(self._get_expr_value(arg) for arg in node.args)
            return f"{callee}({args})"
        elif isinstance(node, ArrayAccess):
            arr = node.array.name if hasattr(node.array, "name") else str(node.array)
            idx = self._get_expr_value(node.index)
            return f"{arr}[{idx}]"
        elif isinstance(node, Cast):
            operand = self._get_expr_value(node.operand)
            return f"({node.cast_type}){operand}"
        elif isinstance(node, Assignment):
            target = self._get_expr_value(node.target)
            value = self._get_expr_value(node.value)
            return f"{target} = {value}"
        elif isinstance(node, InitList):
            elems = ", ".join(self._get_expr_value(e) for e in node.elements)
            return f"{{{elems}}}"
        elif isinstance(node, TypeExpr):
            return self._map_type(node.type_name)
        else:
            return str(node)

    def _gen_program(self, node):
        """Generate top-level declarations."""
        for i, decl in enumerate(node.declarations):
            self._gen_node(decl)
            if i < len(node.declarations) - 1 and not isinstance(decl, Include):
                self._emit(" ")

    def _gen_node(self, node):
        """Dispatch to appropriate generator method."""
        if isinstance(node, Function):
            self._gen_function(node)
        elif isinstance(node, Declaration):
            self._gen_declaration(node)
        elif isinstance(node, Compound):
            self._gen_compound(node)
        elif isinstance(node, If):
            self._gen_if(node)
        elif isinstance(node, While):
            self._gen_while(node)
        elif isinstance(node, Do):
            self._gen_do(node)
        elif isinstance(node, For):
            self._gen_for(node)
        elif isinstance(node, Return):
            self._gen_return(node)
        elif isinstance(node, Break):
            self._emit("break;")
        elif isinstance(node, Continue):
            self._emit("continue;")
        elif isinstance(node, ExprStmt):
            self._gen_expr_stmt(node)
        elif isinstance(node, Binary):
            self._gen_binary(node)
        elif isinstance(node, Unary):
            self._gen_unary(node)
        elif isinstance(node, Literal):
            self._gen_literal(node)
        elif isinstance(node, Var):
            self._emit(node.name)
        elif isinstance(node, Call):
            self._gen_call(node)
        elif isinstance(node, ArrayAccess):
            self._gen_array_access(node)
        elif isinstance(node, Cast):
            self._gen_cast(node)
        elif isinstance(node, Assignment):
            self._gen_assignment(node)
        elif isinstance(node, Include):
            self._gen_include(node)
        elif isinstance(node, InitList):
            self._gen_init_list(node)
        elif isinstance(node, Switch):
            self._gen_switch(node)
        elif isinstance(node, StructDef):
            self._gen_struct_def(node)
        elif isinstance(node, Typedef):
            self._gen_typedef(node)
        elif isinstance(node, FieldAccess):
            self._gen_field_access(node)
        elif isinstance(node, DesignatedInit):
            self._gen_designated_init(node)
        elif hasattr(node, "__class__") and node.__class__.__name__ == "AsmBlock":
            self._gen_asm_block(node)
        elif hasattr(node, "node_type") and node.node_type == "ASM":
            self._gen_asm_block(node)
        elif hasattr(node, "node_type") and node.node_type == "STRUCT_DEF":
            self._gen_struct_def(node)
        elif hasattr(node, "node_type") and node.node_type == "TYPEDEF":
            self._gen_typedef(node)
        elif hasattr(node, "node_type") and node.node_type == "FIELD_ACCESS":
            self._gen_field_access(node)
        elif hasattr(node, "node_type") and node.node_type == "DESIGNATED_INIT":
            self._gen_designated_init(node)
        elif isinstance(node, Generic):
            self._gen_generic(node)
        elif isinstance(node, CompoundLiteral):
            self._gen_compound_literal(node)
        else:
            self._emit(f"/* unknown node: {node.__class__.__name__} */")

    def _map_type(self, typ: str) -> str:
        """Map C△ type to C type."""
        if not typ:
            return typ
        if typ.startswith("dynam "):
            typ = typ[7:]
        if typ.startswith("tuple "):
            typ = typ[6:]
        if typ == "string":
            return "char*"
        return TYPE_MAP.get(typ, typ)

    def _gen_function(self, node: Function):
        """Generate function definition."""
        ret_type = self._map_type(node.ret_type)
        params = []
        for ptype, pname in node.params:
            params.append(f"{self._map_type(ptype)} {pname}")
        param_str = ", ".join(params) if params else "void"
        self._emit(f"{ret_type} {node.name}({param_str}) {{")
        self._indent += 1
        if isinstance(node.body, Compound):
            for stmt in node.body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(node.body)
        self._indent -= 1
        self._emit("}")

    def _gen_declaration(self, node: Declaration):
        """Generate variable declaration."""
        typ = self._map_type(node.var_type)
        name = node.name
        if node.array_size is not None:
            if isinstance(node.array_size, list):
                # Multi-dimensional array
                dims = "".join(f"[{s}]" for s in node.array_size)
                name = f"{node.name}{dims}"
            else:
                name = f"{node.name}[{node.array_size}]"
        if node.initializer is not None:
            val = self._get_expr_value(node.initializer)
            self._emit(f"{typ} {name} = {val};")
        else:
            self._emit(f"{typ} {name};")

    def _gen_compound(self, node: Compound):
        """Generate compound block."""
        if len(node.stmts) == 0:
            self._emit("{}")
            return
        if len(node.stmts) == 1:
            stmt = node.stmts[0]
            if isinstance(stmt, Declaration):
                self._gen_node(stmt)
                return
            if isinstance(stmt, ExprStmt) and isinstance(stmt.expr, Assignment):
                self._gen_node(stmt.expr)
                self._emit(";")
                return
            if isinstance(stmt, Return):
                self._gen_node(stmt)
                return
            if isinstance(stmt, ExprStmt):
                self._gen_node(stmt.expr)
                self._emit(";")
                return
        self._emit("{")
        self._indent += 1
        for stmt in node.stmts:
            self._gen_node(stmt)
        self._indent -= 1
        self._emit("}")

    def _gen_if(self, node: If):
        """Generate if/else statement."""
        cond = self._get_expr_value(node.cond)
        self._emit(f"if ({cond}) {{")
        self._indent += 1
        if isinstance(node.then_branch, Compound):
            for stmt in node.then_branch.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(node.then_branch)
        self._indent -= 1
        if node.else_branch is not None:
            self._emit("} else {")
            self._indent += 1
            if isinstance(node.else_branch, Compound):
                for stmt in node.else_branch.stmts:
                    self._gen_node(stmt)
            else:
                self._gen_node(node.else_branch)
            self._indent -= 1
            self._emit("}")
        else:
            self._emit("}")

    def _gen_while(self, node: While):
        """Generate while loop."""
        cond = self._get_expr_value(node.cond)
        self._emit(f"while ({cond}) {{")
        self._indent += 1
        if isinstance(node.body, Compound):
            for stmt in node.body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(node.body)
        self._indent -= 1
        self._emit("}")

    def _gen_do(self, node: Do):
        """Generate do-while loop."""
        cond = self._get_expr_value(node.cond)
        self._emit(f"do {{")
        self._indent += 1
        if isinstance(node.body, Compound):
            for stmt in node.body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(node.body)
        self._indent -= 1
        self._emit(f"}} while ({cond});")

    def _gen_for(self, node: For):
        """Generate for loop."""
        init_str = ""
        if node.init:
            if isinstance(node.init, Declaration):
                init_str = f"{self._map_type(node.init.var_type)} {node.init.name}"
                if node.init.initializer:
                    init_str += f" = {self._get_expr_value(node.init.initializer)}"
            else:
                init_str = self._get_expr_value(node.init)

        cond_str = self._get_expr_value(node.cond) if node.cond else ""

        post_str = ""
        if node.post:
            if isinstance(node.post, Assignment):
                target = self._get_expr_value(node.post.target)
                if isinstance(node.post.value, Binary) and hasattr(
                    node.post.value.left, "name"
                ):
                    if node.post.value.left.name == node.post.target.name:
                        post_str = f"{node.post.target.name} {node.post.value.op}= {self._get_expr_value(node.post.value.right)}"
                else:
                    post_str = self._get_expr_value(node.post)
            elif isinstance(node.post, Unary):
                operand = self._get_expr_value(node.post.operand)
                post_str = f"{operand}{node.post.op}"
            else:
                post_str = self._get_expr_value(node.post)

        self._emit(f"for ({init_str}; {cond_str}; {post_str}) {{")
        self._indent += 1
        if isinstance(node.body, Compound):
            for stmt in node.body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(node.body)
        self._indent -= 1
        self._emit("}")

    def _gen_return(self, node: Return):
        """Generate return statement."""
        if node.expr is not None:
            val = self._get_expr_value(node.expr)
            self._emit(f"return {val};")
        else:
            self._emit("return;")

    def _gen_expr_stmt(self, node: ExprStmt):
        """Generate expression statement."""
        if node.expr is not None:
            self._gen_node(node.expr)
            self._emit(";")

    def _gen_binary(self, node: Binary):
        """Generate binary expression with minimal parens."""
        need_parens = self._needs_parens(node)
        if need_parens:
            self._emit("(", end="")
        self._gen_node(node.left)
        self._emit(f" {node.op} ", end="")
        self._gen_node(node.right)
        if need_parens:
            self._emit(")", end="")

    def _gen_unary(self, node: Unary):
        """Generate unary expression."""
        if node.op == "sizeof":
            if hasattr(node.operand, "type_name"):
                self._emit(f"sizeof({node.operand.type_name})")
            else:
                self._emit("sizeof(", end="")
                self._gen_node(node.operand)
                self._emit(")", end="")
        else:
            operand = self._get_expr_value(node.operand)
            if node.prefix:
                self._emit(f"{node.op}{operand}", end="")
            else:
                self._emit(f"{operand}{node.op}", end="")

    def _gen_literal(self, node: Literal):
        """Generate literal value."""
        val = node.value
        # Lexer returns all literals as strings - check if it looks like a number
        if isinstance(val, str):
            stripped = val.lstrip("-")
            # Hex, binary, or octal literals (0x..., 0b..., 0...)
            if (
                stripped.startswith("0x")
                or stripped.startswith("0X")
                or stripped.startswith("0b")
                or stripped.startswith("0B")
                or (stripped.isdigit() and stripped.startswith("0"))
            ):
                self._emit(val, end="")
            # Numbers with suffixes (LL, U, UL, f, etc.) or float with suffix
            elif any(
                stripped.endswith(suffix)
                for suffix in (
                    "LL",
                    "ll",
                    "U",
                    "u",
                    "UL",
                    "ul",
                    "ULL",
                    "ull",
                    "f",
                    "F",
                    "l",
                    "L",
                )
            ) or (
                stripped.replace(".", "", 1).replace("e", "").replace("E", "").isdigit()
                and any(stripped.endswith(c) for c in "fFeE")
            ):
                self._emit(val, end="")
            elif stripped.isdigit():
                self._emit(val, end="")
            elif stripped.replace(".", "", 1).isdigit():
                self._emit(val, end="")
            elif val.startswith('"') or val.startswith("'"):
                self._emit(val, end="")
            else:
                self._emit(f'"{val}"', end="")
        else:
            self._emit(str(val), end="")

    def _gen_call(self, node: Call):
        """Generate function call."""
        callee_name = (
            node.callee.name if hasattr(node.callee, "name") else str(node.callee)
        )
        args_str = ", ".join(self._get_expr_value(arg) for arg in node.args)
        self._emit(f"{callee_name}({args_str})", end="")

    def _gen_array_access(self, node: ArrayAccess):
        """Generate array access."""
        arr_name = node.array.name if hasattr(node.array, "name") else str(node.array)
        idx = self._get_expr_value(node.index)
        self._emit(f"{arr_name}[{idx}]", end="")

    def _gen_cast(self, node: Cast):
        """Generate cast expression."""
        operand = self._get_expr_value(node.operand)
        self._emit(f"({node.cast_type}){operand}", end="")

    def _gen_assignment(self, node: Assignment):
        """Generate assignment expression."""
        target = self._get_expr_value(node.target)
        value = self._get_expr_value(node.value)
        self._emit(f"{target} = {value}", end="")

    def _gen_include(self, node: Include):
        """Generate include directive."""
        if node.is_system:
            self._emit(f"#include <{node.path}>")
        else:
            self._emit(f'#include "{node.path}"')

    def _gen_init_list(self, node: InitList):
        """Generate initializer list."""
        self._emit("{ ", end="")
        for i, elem in enumerate(node.elements):
            if i > 0:
                self._emit(", ", end="")
            self._gen_node(elem)
        self._emit(" }", end="")

    def _gen_switch(self, node: Switch):
        """Generate switch statement."""
        expr = self._get_expr_value(node.expr)
        self._emit(f"switch ({expr}) {{")
        self._indent += 1
        for case_val, body in node.cases:
            if case_val is None:
                self._emit("default:")
            else:
                case_str = self._get_expr_value(case_val)
                self._emit(f"case {case_str}:")
            self._indent += 1
            self._gen_node(body)
            self._indent -= 1
        self._indent -= 1
        self._emit("}")

    def _gen_asm_block(self, node):
        """Pass asm block through unchanged."""
        content = getattr(node, "content", str(node))
        for line in content.split("\n"):
            self._emit(line)

    def _gen_struct_def(self, node):
        """Generate struct definition."""
        name = getattr(node, "name", "")
        fields = getattr(node, "fields", [])
        self._emit(f"struct {name} {{")
        self._indent += 1
        for field_type, field_name in fields:
            self._emit(f"{field_type} {field_name};")
        self._indent -= 1
        self._emit("};")

    def _gen_typedef(self, node):
        """Generate typedef."""
        actual = getattr(node, "actual_type", "")
        alias = getattr(node, "alias", "")
        self._emit(f"typedef {actual} {alias};")

    def _gen_field_access(self, node):
        """Generate field access (obj.field)."""
        obj = getattr(node, "obj", None)
        field = getattr(node, "field_name", "")
        if obj is not None and hasattr(obj, "name"):
            self._emit(f"{obj.name}.{field}", end="")
        else:
            self._emit(f"field.{field}", end="")

    def _gen_designated_init(self, node):
        """Generate designated initializer."""
        field = getattr(node, "field", "")
        value = getattr(node, "value", None)
        self._emit(f".{field} = ", end="")
        if value is not None:
            self._gen_node(value)

    def _gen_generic(self, node):
        """Generate C11 _Generic expression."""
        expr = self._get_expr_value(node.expr)
        assocs = []
        for assoc_type, assoc_value in node.associations:
            val = self._get_expr_value(assoc_value)
            assocs.append(f"{assoc_type}: {val}")
        assocs_str = ", ".join(assocs)
        self._emit(f"_Generic({expr}, {assocs_str})", end="")

    def _gen_compound_literal(self, node):
        """Generate compound literal: (type){ elements }"""
        typ = self._map_type(node.lit_type)
        self._emit(f"({typ}){{", end="")
        for i, elem in enumerate(node.elements):
            if i > 0:
                self._emit(", ", end="")
            self._gen_node(elem)
        self._emit("}", end="")
