"""C11 code generator for C△ compiler."""

import os

import error_msgs
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
    Define,
    InitList,
    Switch,
    StructDef,
    Typedef,
    UsingDecl,
    ExposeDecl,
    LibAccess,
    SpaceDecl,
    TypeExpr,
    FieldAccess,
    DesignatedInit,
    ArrayDesignation,
)


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
    def __init__(self, ast, structor, layouts=None, source_path=None):
        self.ast = ast
        self.structor = structor
        self.layouts = layouts or {}
        self.source_path = source_path  # path to source file for plib lookup
        self._lines = []
        self._indent = 0
        self._specific_imports = {}  # item -> (lib_name, namespace)
        self._current_alias = {}  # lib_name -> alias
        self._generating_plib = False  # Flag to bypass checks when generating plib code
        self._exposed_libs = set()  # Set of exposed library names
        self._collected_includes = set()
        # Track generated dynam helper functions and structs to avoid duplicates
        self._generated_dynam_structs = set()  # Track generated struct types
        self._generated_dynam_funcs = set()  # Track generated helper functions
        self._helper_lines = []  # Store dynam helper functions
        self._dynam_declarations = {}  # Track dynam/string declarations by name -> type
        self._len_int_generated = False  # Track if len_int helper has been generated
        self._current_space = None  # Current space name when generating inside a space
        self._space_local_functions = set()  # Functions defined in current space
        self._space_prefix_map = {}  # Maps space name -> actual prefix (e.g., "math" -> "lib_math")
        self._alias_to_lib = {}  # Maps alias (e.g., "lib") -> actual lib name (e.g., "mylib")
        self._top_level_lib_functions = {}  # Maps lib_name -> set of top-level function names
        self._used_functions = set()  # Track used function names for tree-shaking
        self._pending_plibs = []  # Store pending plib ASTs for tree-shaking
        self._global_dynam_inits = []  # Track global dynam initialization code for main()
        self._plib_global_inits = []  # Track global dynam inits for plib init function
        self._plib_init_funcs = []  # Track plib init function names to auto-call
        self._imported_plib_inits = []  # Track init funcs from imported plibs
        self._plib_inits_called = (
            False  # Track if plib inits have been called in main()
        )
        self._in_global_scope = True  # Track if we're at global scope
        self._dynam_inits_inserted = (
            False  # Track if global dynam inits have been inserted
        )
        self._is_plib_source = source_path and source_path.endswith(
            ".plib"
        )  # Direct plib compilation

    def generate(self) -> str:
        """Main entry point. Returns generated C code as string."""
        self._lines = []

        # First, collect plib info and process imports (which populates _top_level_lib_functions)
        self._gen_imports()

        # Emit collected includes at the very beginning
        includes_to_emit = []
        for inc in sorted(self._collected_includes):
            includes_to_emit.append(inc)
        # We'll prepend includes later after all code is generated

        # Generate main program code
        self._gen_program_code(self.ast)

        # Emit pending plibs with tree-shaking (after main program, but prepend includes)
        self._emit_pending_plibs()

        # Prepend includes before any existing code
        self._lines = includes_to_emit + self._lines

        # Always ensure required includes are present
        needs_stdlib = (
            self._len_int_generated
            or "malloc" in "\n".join(self._lines)
            or "free" in "\n".join(self._lines)
            or "realloc" in "\n".join(self._lines)
        )
        needs_string = (
            "strlen" in "\n".join(self._lines)
            or "strdup" in "\n".join(self._lines)
            or "strcpy" in "\n".join(self._lines)
            or "strcat" in "\n".join(self._lines)
        )

        # If we generated dynam helpers, prepend them after includes
        if self._helper_lines or needs_stdlib or needs_string:
            # Separate includes from other code
            includes = []
            rest = []
            in_includes = True
            for line in self._lines:
                if in_includes and (line.startswith("#include") or line.strip() == ""):
                    includes.append(line)
                else:
                    in_includes = False
                    rest.append(line)

            # Build new output with includes and helpers
            new_includes = []
            if "#include <stdlib.h>" not in "\n".join(includes) and needs_stdlib:
                new_includes.append("#include <stdlib.h>")
            if "#include <string.h>" not in "\n".join(includes) and needs_string:
                new_includes.append("#include <string.h>")

            new_lines = (
                includes + new_includes + [""] + self._helper_lines + [""] + rest
            )
            self._lines = new_lines

        # Add len_int helper if needed for integer len() calls
        if self._len_int_generated:
            # Insert len_int helper after stdlib.h include
            len_int_helper = [
                "",
                "int len_int(int x) {",
                "    if (x == 0) return 1;",
                "    int count = 0;",
                "    if (x < 0) { x = -x; count = 1; }",
                "    while (x > 0) { count++; x /= 10; }",
                "    return count;",
                "}",
                "",
            ]
            # Find position after stdlib.h include
            insert_pos = 2
            self._lines = (
                self._lines[:insert_pos] + len_int_helper + self._lines[insert_pos:]
            )

        return "\n".join(self._lines)

    # ------------------------------------------------------------------
    # Emission helpers
    # ------------------------------------------------------------------

    def _emit(self, line: str = ""):
        """Emit one complete source line at the current indent level."""
        indent = "    " * self._indent
        self._lines.append(indent + line)

    def _emit_raw(self, text: str):
        """Emit a pre-indented block of text verbatim (e.g. asm blocks)."""
        for line in text.splitlines():
            self._lines.append(line)

    # ------------------------------------------------------------------
    # Type mapping
    # ------------------------------------------------------------------

    def _map_type(self, typ: str) -> str:
        """Map C△ type to C type."""
        if not typ:
            return typ

        # Handle pointer types: strip trailing * and map base, then add * back
        pointer_suffix = ""
        while typ.endswith("*"):
            typ = typ[:-1].strip()
            pointer_suffix += "*"

        # Handle qualifiers: volatile string*, const int*, etc.
        qualifier = ""
        for q in ("volatile ", "const "):
            if typ.startswith(q):
                qualifier = q.strip() + " "
                typ = typ[len(q) :]
                break

        if typ.startswith("dynam "):
            typ = typ[6:]  # Strip "dynam " (6 chars)
        if typ.startswith("tuple "):
            typ = typ[6:]
        if typ == "string":
            mapped = "char*"
        else:
            mapped = TYPE_MAP.get(typ, typ)

        return qualifier + mapped + pointer_suffix

    def _get_dynam_type(self, var_name: str) -> str:
        """Get the type of a variable if it's dynam or string."""
        return self._dynam_declarations.get(var_name)

    def _get_expression_type(self, node) -> str:
        """Determine the type of an expression for codegen purposes."""
        if isinstance(node, Literal):
            # String literals are strings
            if isinstance(node.value, str) and node.value.startswith('"'):
                return "string"
            return ""  # Other literals

        if isinstance(node, Var):
            # Variables get their type from declaration tracking
            return self._get_dynam_type(node.name) or ""

        # For other expressions, we could do more analysis but for now keep it simple
        return ""

    def _contains_assignment(self, node) -> bool:
        """Recursively check if an expression contains an assignment."""
        if node is None:
            return False
        if isinstance(node, Assignment):
            return True
        if isinstance(node, Binary):
            return self._contains_assignment(node.left) or self._contains_assignment(
                node.right
            )
        if isinstance(node, Unary):
            return self._contains_assignment(node.operand)
        if isinstance(node, Call):
            return any(self._contains_assignment(a) for a in node.args)
        return False

    # ------------------------------------------------------------------
    # Expression serialiser
    # ------------------------------------------------------------------

    def _expr(self, node) -> str:
        """Recursively serialise an expression node to a C string.

        This is the single source of truth for expression rendering.
        All statement generators call this rather than recursing through
        _gen_node, which avoids the interleaved-emit ordering bugs that
        arise when half the code uses end='' streaming and the other half
        uses full-line emission.
        """
        if node is None:
            return ""

        if isinstance(node, Literal):
            val = node.value
            if isinstance(val, str):
                # Already a string lexeme — pass through as-is if it looks
                # like a number or a quoted literal; otherwise wrap in quotes.
                stripped = val.lstrip("-")
                if (
                    stripped.startswith("0x")
                    or stripped.startswith("0X")
                    or stripped.startswith("0b")
                    or stripped.startswith("0B")
                    or stripped.isdigit()
                    or stripped.replace(".", "", 1).isdigit()
                    or val.startswith('"')
                    or val.startswith("'")
                    or any(
                        stripped.rstrip("uUlLfF").replace(".", "", 1).isdigit()
                        for _ in [None]
                    )
                ):
                    return val
                return f'"{val}"'
            return str(val)

        if isinstance(node, Var):
            return node.name

        if isinstance(node, TypeExpr):
            return self._map_type(node.type_name)

        if isinstance(node, Binary):
            if node.op == "?:":
                # Ternary: condition ?  true_val : false_val
                # Parser encodes as Binary("?:", cond, Binary("branch", t, f))
                cond = self._expr(node.left)
                if isinstance(node.right, Binary) and node.right.op == "branch":
                    true_val = self._expr(node.right.left)
                    false_val = self._expr(node.right.right)
                    return f"({cond}) ? {true_val} : {false_val}"
                return f"({cond}) ? {self._expr(node.right)}"

            # Handle string concatenation: "hello" + "world" or s1 + s2
            if node.op == "+":
                left_type = self._get_expression_type(node.left)
                right_type = self._get_expression_type(node.right)
                left_is_string = left_type == "string" or (
                    isinstance(node.left, Literal)
                    and isinstance(node.left.value, str)
                    and node.left.value.startswith('"')
                )
                right_is_string = right_type == "string" or (
                    isinstance(node.right, Literal)
                    and isinstance(node.right.value, str)
                    and node.right.value.startswith('"')
                )

                # string + integer is pointer arithmetic, not concatenation
                def is_numeric_literal(node):
                    """Check if a Literal node contains a numeric value."""
                    if isinstance(node, Literal):
                        val = node.value
                        if isinstance(val, int):
                            return True
                        if isinstance(val, str):
                            try:
                                int(val)
                                return True
                            except:
                                pass
                    return False

                if left_is_string and is_numeric_literal(node.right):
                    left_is_string = False
                if right_is_string and is_numeric_literal(node.left):
                    right_is_string = False

                # If either operand is a string or string literal, treat as concatenation
                if left_is_string or right_is_string:
                    left_expr = self._expr(node.left)
                    right_expr = self._expr(node.right)

                    # String concatenation not yet implemented for expressions
                    raise NotImplementedError(
                        "String concatenation in expressions is not yet implemented. "
                        "Use separate string variables and strcpy/strcat manually."
                    )

            left = self._expr(node.left)
            right = self._expr(node.right)

            # Handle string comparisons: s == "hello" or s1 == s2
            if node.op in ("==", "!="):
                left_type = self._get_expression_type(node.left)
                right_type = self._get_expression_type(node.right)

                # If comparing strings, we need to use strcmp
                if (
                    left_type == "string"
                    or (
                        isinstance(node.left, Literal)
                        and isinstance(node.left.value, str)
                        and node.left.value.startswith('"')
                    )
                ) or (
                    right_type == "string"
                    or (
                        isinstance(node.right, Literal)
                        and isinstance(node.right.value, str)
                        and node.right.value.startswith('"')
                    )
                ):
                    # Handle string literal comparison: s == "hello" -> strcmp(s, "hello") == 0
                    if (
                        isinstance(node.left, Literal)
                        and isinstance(node.left.value, str)
                        and node.left.value.startswith('"')
                    ):
                        # "hello" == s -> strcmp(s, "hello") == 0
                        return (
                            f"(strcmp({right}, {left}) == 0)"
                            if node.op == "=="
                            else f"(strcmp({right}, {left}) != 0)"
                        )
                    elif (
                        isinstance(node.right, Literal)
                        and isinstance(node.right.value, str)
                        and node.right.value.startswith('"')
                    ):
                        # s == "hello" -> strcmp(s, "hello") == 0
                        return (
                            f"(strcmp({left}, {right}) == 0)"
                            if node.op == "=="
                            else f"(strcmp({left}, {right}) != 0)"
                        )
                    else:
                        # s1 == s2 -> strcmp(s1, s2) == 0
                        return (
                            f"(strcmp({left}, {right}) == 0)"
                            if node.op == "=="
                            else f"(strcmp({left}, {right}) != 0)"
                        )

            # Comparison operators don't need extra parens (avoid gcc warnings)
            if node.op in ("==", "!=", "<", ">", "<=", ">="):
                return f"{left} {node.op} {right}"
            # Preserve AST grouping regardless of C operator precedence.
            return f"({left} {node.op} {right})"

        if isinstance(node, Unary):
            if node.op == "sizeof":
                operand = self._expr(node.operand)
                return f"sizeof({operand})"
            # Handle string pointer dereferencing: *s for string s
            if node.op == "*" and isinstance(node.operand, Var):
                var_name = node.operand.name
                if self._get_dynam_type(var_name) == "string":
                    # For string types, *s should generate *(s) which is correct
                    return f"*({self._expr(node.operand)})"
            operand = self._expr(node.operand)
            if node.prefix:
                return f"{node.op}{operand}"
            return f"{operand}{node.op}"

        if isinstance(node, Assignment):
            target = self._expr(node.target)
            value = self._expr(node.value)
            return f"{target} = {value}"

        if isinstance(node, Call):
            # Check if this is a method call on a dynam array: obj.method(args)
            if isinstance(node.callee, FieldAccess):
                obj_expr = self._expr(node.callee.obj)
                method_name = node.callee.field_name

                # Check if this is a dynam array method: push, pop, len
                if method_name in ("push", "pop", "len"):
                    # For now, we'll assume any variable accessed with these methods is a dynam array
                    # In a full implementation, we'd check the symbol table for the variable type
                    # Generate helper function call: dynam_<type>_<method>(&obj, args)
                    # We don't have type info here, so we'll use a placeholder approach
                    # Better would be to pass type information through the codegen process

                    # Since we don't have the element type, we'll need to infer it or use a generic approach
                    # For now, let's assume we can determine the type from context or use a generic name
                    # This is a limitation - in a real compiler we'd have symbol table info

                    # Try to get the variable name from the object expression
                    # If obj_expr is a simple variable name, use it
                    if isinstance(node.callee.obj, Var):
                        var_name = node.callee.obj.name
                        # Look up the variable's type in our tracking dict
                        if var_name in self._dynam_declarations:
                            dyn_type = self._dynam_declarations[var_name]
                            if dyn_type.startswith("dynam "):
                                elem_type = dyn_type[6:]  # Remove "dynam " prefix
                                struct_name = self._get_dynam_struct_name(elem_type)
                            elif dyn_type == "string":
                                # For string, we need to treat as dynam char for push/pop/len
                                elem_type = "char"
                                struct_name = self._get_dynam_struct_name(elem_type)
                        else:
                            # Fallback to int if not found (shouldn't happen in valid code)
                            elem_type = "int"
                            struct_name = self._get_dynam_struct_name(elem_type)

                        if method_name == "push":
                            # arr.push(val) -> dynam_int_push(&arr, val)
                            args_str = ", ".join(self._expr(a) for a in node.args)
                            return f"{struct_name}_push(&{var_name}, {args_str})"
                        elif method_name == "pop":
                            # arr.pop() -> dynam_int_pop(&arr)
                            args_str = ", ".join(self._expr(a) for a in node.args)
                            return f"{struct_name}_pop(&{var_name}){'' if not node.args else f'({args_str})'}"
                        elif method_name == "len":
                            # arr.len() -> dynam_int_len(&arr)
                            args_str = ", ".join(self._expr(a) for a in node.args)
                            return f"{struct_name}_len(&{var_name}){'' if not node.args else f'({args_str})'}"
                    else:
                        # Complex object expression, fall back to regular handling
                        callee = self._expr(node.callee)
            else:
                # Check if this is a call to len() function: len(arr) or len("string") or len(123)
                if isinstance(node.callee, Var) and node.callee.name == "len":
                    if len(node.args) == 1:
                        arg = node.args[0]

                        # Handle integer literal: len(123) or len(-456)
                        if isinstance(arg, Literal):
                            # Extract the numeric value
                            val = arg.value
                            # Check if it's an integer (with optional suffix like L, LL, U, UL)
                            if isinstance(val, str):
                                stripped = val.lstrip("-")
                                # Integer with optional suffix (L, LL, U, UL, etc.)
                                if (
                                    stripped.replace("L", "")
                                    .replace("U", "")
                                    .replace("u", "")
                                    .isdigit()
                                ):
                                    self._len_int_generated = True
                                    return f"len_int({val})"
                                # Float/Double literal - count decimal places
                                if (
                                    stripped.replace("f", "")
                                    .replace("F", "")
                                    .replace(".", "")
                                    .isdigit()
                                ):
                                    # Count decimal places
                                    if "." in stripped:
                                        decimal_places = len(
                                            stripped.split(".")[1].rstrip("fF")
                                        )
                                        return str(decimal_places)
                                    else:
                                        return "0"  # No decimal places for integers

                        # Handle negative integer: len(-456)
                        if (
                            isinstance(arg, Unary)
                            and arg.op == "-"
                            and isinstance(arg.operand, Literal)
                        ):
                            val = arg.operand.value
                            if (
                                isinstance(val, str)
                                and val.lstrip("-")
                                .replace("L", "")
                                .replace("U", "")
                                .isdigit()
                            ):
                                self._len_int_generated = True
                                return f"len_int(-{val})"

                        # Handle regular variable - check if it's a dynam array or C array
                        if isinstance(arg, Var):
                            var_name = arg.name
                            # Check if this is a dynam array by checking our tracking dict
                            if var_name in self._dynam_declarations:
                                dyn_type = self._dynam_declarations[var_name]
                                if dyn_type.startswith("dynam "):
                                    elem_type = dyn_type[6:]
                                    struct_name = self._get_dynam_struct_name(elem_type)
                                    return f"{struct_name}_len(&{var_name})"
                                elif dyn_type == "string":
                                    return f"strlen({var_name})"

                            # For regular C arrays, we'd need symbol table info
                            # For now, try to use sizeof approach: sizeof(arr)/sizeof(arr[0])
                            # This works for static arrays
                            # Generate: sizeof(var)/sizeof(var[0])
                            return f"(int)(sizeof({var_name})/sizeof({var_name}[0]))"

                        # Handle other expressions - default to strlen for strings
                        arg_expr = self._expr(arg)
                        return f"strlen({arg_expr})"

                # Regular function call
                callee = (
                    node.callee.name
                    if isinstance(node.callee, Var)
                    else self._expr(node.callee)
                )

                # Handle space-local function calls: if we're inside a space and calling
                # a function defined in that space, prefix with the space name
                if self._current_space and callee in self._space_local_functions:
                    callee = f"{self._current_space}_{callee}"

            # Handle specific imports: using sin from <math> -> math_sin()
            # AND intra-file scoped imports: using X&Y -> map Y to X_Y
            # This must run BEFORE namespace transformation so "func@lib" can match "func"
            base_callee = callee.split("@")[0] if "@" in callee else callee
            func_from_unexposed_lib = False
            if (
                hasattr(self, "_specific_imports")
                and base_callee in self._specific_imports
            ):
                lib_name, func_name = self._specific_imports[base_callee]
                # Check if this library is exposed - if not, require @ prefix
                is_exposed = lib_name in getattr(self, "_exposed_libs", set())
                if not is_exposed and "@" not in callee:
                    raise ValueError(
                        error_msgs.get_error_msg(
                            "E802",
                            lib=lib_name,
                            func=base_callee,
                            fallback=f"Function '{base_callee}' requires '{base_callee}@{lib_name}()' syntax (library not exposed). Use 'expose {lib_name}' before calling.",
                        )
                    )
                # If func_name is None or equals base_callee, no transformation needed
                # The function is already named correctly (top-level function)
                if func_name is None or func_name == base_callee:
                    pass  # callee stays as-is
                elif "&" in str(lib_name):
                    # Chain like a&b&c - transform
                    scope_chain = lib_name
                    callee = scope_chain.replace("&", "_") + "_" + func_name
                elif lib_name == func_name:
                    # Alias used - callee should already be the alias
                    pass  # callee stays as-is (already matches)
                else:
                    # Single scope like foo - transform to foo_bar
                    callee = lib_name + "_" + func_name

            # Check if calling a function from an imported but unexposed plib
            # without using @ syntax (skip when generating plib code itself)
            elif (
                not getattr(self, "_generating_plib", False)
                and base_callee not in getattr(self, "_specific_imports", {})
                and base_callee not in getattr(self, "_space_local_functions", set())
                and "@" not in callee
            ):
                # Check if function exists in any imported plib's top-level functions
                for lib_name, funcs in getattr(
                    self, "_top_level_lib_functions", {}
                ).items():
                    if base_callee in funcs:
                        is_exposed = lib_name in getattr(self, "_exposed_libs", set())
                        if not is_exposed:
                            raise ValueError(
                                error_msgs.get_error_msg(
                                    "E802",
                                    lib=lib_name,
                                    func=base_callee,
                                    fallback=f"Function '{base_callee}' requires '{base_callee}@{lib_name}()' syntax (library '{lib_name}' not exposed). Use 'expose {lib_name}' before calling.",
                                )
                            )
                        break

            # Handle namespace prefix like "func@lib" or "func@space" -> "prefix_func"
            # @ is for calling space-local functions or top-level library functions
            elif "@" in callee:
                parts = callee.split("@")
                if len(parts) == 2:
                    func, namespace = parts
                    # Check if this is a space-local function (preferred)
                    if namespace in self._space_prefix_map:
                        actual_prefix = self._space_prefix_map[namespace]
                        callee = f"{actual_prefix}_{func}"
                    elif namespace in self._alias_to_lib:
                        # @lib or other valid alias
                        actual_lib = self._alias_to_lib[namespace]
                        if (
                            actual_lib in self._top_level_lib_functions
                            and func in self._top_level_lib_functions[actual_lib]
                        ):
                            # Top-level function - call directly without prefix
                            callee = func
                        else:
                            raise ValueError(
                                error_msgs.get_error_msg(
                                    "E803",
                                    func=func,
                                    lib=actual_lib,
                                    fallback=f"Function '{func}' not found in library '{actual_lib}'. Use '{func}()' directly if it's a top-level function.",
                                )
                            )
                    elif namespace in self._top_level_lib_functions:
                        # Direct lib name like @streamer
                        if func in self._top_level_lib_functions[namespace]:
                            callee = func
                        else:
                            raise ValueError(
                                error_msgs.get_error_msg(
                                    "E803",
                                    func=func,
                                    lib=namespace,
                                    fallback=f"Function '{func}' not found in library '{namespace}'.",
                                )
                            )
                    else:
                        # Invalid alias
                        raise ValueError(
                            error_msgs.get_error_msg(
                                "E804",
                                alias=namespace,
                                fallback=f"Invalid alias '{namespace}'. Library not imported or does not exist.",
                            )
                        )
            # Track this function call for tree-shaking plibs
            self._used_functions.add(base_callee)
            args = ", ".join(self._expr(a) for a in node.args)
            return f"{callee}({args})"

        if isinstance(node, ArrayAccess):
            arr = self._expr(node.array)
            idx = self._expr(node.index)
            # Check if this is a dynam array subscript
            if isinstance(node.array, Var):
                var_name = node.array.name
                dyn_type = self._get_dynam_type(var_name)
                if dyn_type and dyn_type.startswith("dynam "):
                    # Dynam array: arr[idx] -> arr.data[idx]
                    return f"{arr}.data[{idx}]"
            return f"{arr}[{idx}]"

        if isinstance(node, Cast):
            operand = self._expr(node.operand)
            cast_type = self._map_type(node.cast_type)
            return f"({cast_type})({operand})"

        if isinstance(node, FieldAccess):
            obj = self._expr(node.obj)
            # If object is a dereference (Unary *), use arrow notation
            # The Unary was added by the parser when converting -> to (*).field
            # So we don't need another *
            if isinstance(node.obj, Unary) and node.obj.op == "*":
                # Get the operand of the unary (the pointer variable)
                ptr = self._expr(node.obj.operand)
                return f"{ptr}->{node.field_name}"
            return f"{obj}.{node.field_name}"

        if isinstance(node, InitList):
            elems = ", ".join(self._expr(e) for e in node.elements)
            return f"{{{elems}}}"

        if isinstance(node, DesignatedInit):
            return f".{node.field} = {self._expr(node.value)}"

        if isinstance(node, ArrayDesignation):
            idx = self._expr(node.index)
            val = self._expr(node.value)
            if node.is_range and node.end_index:
                end = self._expr(node.end_index)
                return f"[{idx}...{end}] = {val}"
            return f"[{idx}] = {val}"

        if isinstance(node, CompoundLiteral):
            typ = self._map_type(node.lit_type)
            elems = ", ".join(self._expr(e) for e in node.elements)
            return f"({typ}){{{elems}}}"

        if isinstance(node, Generic):
            expr = self._expr(node.expr)
            assocs = ", ".join(f"{t}: {self._expr(v)}" for t, v in node.associations)
            return f"_Generic({expr}, {assocs})"

        # Fallback
        return f"/* unknown expr: {node.__class__.__name__} */"

    # ------------------------------------------------------------------
    # Top-level
    # ------------------------------------------------------------------

    def _gen_program(self, node):
        # First collect all includes from user file and all plib dependencies
        self._gen_imports()
        # Now generate main program code
        self._gen_program_code(node)
        # Emit pending plibs with tree-shaking
        self._emit_pending_plibs()

    def _gen_program_code(self, node):
        # Now emit collected includes at the very beginning (prepend)
        includes_to_emit = []
        for inc in sorted(self._collected_includes):
            includes_to_emit.append(inc)
        # Prepend includes before any existing code
        self._lines = includes_to_emit + self._lines
        # Now generate rest of code (plib functions included via _gen_plib_code)
        for decl in node.declarations:
            if isinstance(decl, SpaceDecl):
                # Handle SpaceDecl in main file - generate nested declarations with prefix
                prefix = decl.name
                # Track space name -> prefix mapping for @space calls
                self._space_prefix_map[decl.name] = prefix
                # Track current space for function call prefixing
                old_space = self._current_space
                old_local_funcs = self._space_local_functions.copy()
                self._current_space = decl.name
                self._space_local_functions = set()
                for nested in decl.declarations:
                    if isinstance(nested, Function):
                        nested.name = f"{prefix}_{nested.name}"
                        # Track original name for call prefixing
                        self._space_local_functions.add(
                            nested.name.replace(f"{prefix}_", "")
                        )
                    elif isinstance(nested, Declaration):
                        nested.name = f"{prefix}_{nested.name}"
                    self._gen_node(nested)
                # Restore previous space context
                self._current_space = old_space
                self._space_local_functions = old_local_funcs
            elif not isinstance(decl, (UsingDecl, ExposeDecl)):
                # Skip Include/Define - they were collected in _gen_imports via _collect_include
                if isinstance(decl, (Include, Define)):
                    continue
                self._gen_node(decl)

        # Generate plib init function for global dynam arrays (direct plib compilation)
        if self._is_plib_source and self._plib_global_inits:
            # Extract base name from source path (e.g., /tmp/test.plib -> test)
            import os

            base_name = os.path.basename(self.source_path)
            if base_name.endswith(".plib"):
                safe_name = base_name[:-5]  # Remove .plib extension
            else:
                safe_name = base_name
            safe_name = safe_name.replace("/", "_").replace("-", "_")
            self._emit("")
            self._emit(f"void {safe_name}_init(void) {{")
            for init_line, push_lines in self._plib_global_inits:
                self._emit(f"    {init_line}")
                for p_line in push_lines:
                    self._emit(f"    {p_line}")
            self._emit(f"}}")

    def _emit_collected_includes(self):
        for inc in sorted(self._collected_includes):
            self._emit(inc)

    def _gen_imports(self):
        """Generate import-related code (includes, exposes)."""
        if self.structor is None:
            for decl in self.ast.declarations:
                if isinstance(decl, Include):
                    self._collect_include(decl)
                elif isinstance(decl, Define):
                    self._collected_includes.add(decl.directive)
            return

        # Collect user file includes from the AST
        for decl in self.ast.declarations:
            if isinstance(decl, Include):
                self._collect_include(decl)
            elif isinstance(decl, Define):
                self._collected_includes.add(decl.directive)

        imports = self.structor.get_imports()
        exposes = self.structor.get_exposes()

        local_imports = []
        alias_map = {}  # alias -> lib_name
        seen_libs = set()
        specific_imports = {}  # item -> lib_name (for "using X from <Y>")

        for imp in imports:
            source = imp.source

            if source.startswith("<") and source.endswith(">"):
                lib_name = source[1:-1]

                if lib_name not in seen_libs:
                    local_imports.append(lib_name)
                    seen_libs.add(lib_name)
                if imp.alias:
                    alias_map[imp.alias] = (lib_name, "local")
                if imp.item:
                    specific_imports[imp.item] = lib_name
            elif "&" in source:
                # Handle intra-file scoped imports: using X&Y or using a&b&c&Y
                # This imports a symbol Y from scope X (chain of scopes)
                # We need to track this and map the symbol accordingly
                parts = source.split("&")
                if len(parts) >= 2:
                    # Last part is the symbol being imported
                    # First part(s) are the scope chain
                    symbol_name = parts[-1]
                    scope_chain = "&".join(parts[:-1])
                    # If there's an alias, use it instead of scope chain
                    if imp.alias:
                        self._specific_imports[symbol_name] = (imp.alias, imp.alias)
                    else:
                        # Store for later mapping in _expr
                        self._specific_imports[symbol_name] = (scope_chain, symbol_name)
                pass
            else:
                if source not in seen_libs:
                    local_imports.append(source)
                    seen_libs.add(source)
                if imp.alias:
                    alias_map[imp.alias] = (source, "local")
                if imp.item:
                    specific_imports[imp.item] = source

        # Store for use in _expr
        # Map: bare_name -> (lib_name, namespace)
        # Preserve any scoped imports already added (from & in source)
        existing_scoped = dict(self._specific_imports)
        self._specific_imports = {}
        self._current_alias = {}
        # Add scoped imports back
        self._specific_imports.update(existing_scoped)
        # Add specific imports from "using X from Y"
        for item, lib_name in specific_imports.items():
            # Will be updated when plib is processed
            self._specific_imports[item] = (lib_name, None)

        for lib_name in local_imports:
            alias = None
            for a, (lib, type_) in alias_map.items():
                if lib == lib_name and type_ == "local":
                    alias = a
                    break
            if alias:
                self._current_alias[lib_name] = alias
                self._alias_to_lib[alias] = lib_name
            # "lib" is an alias for the standard library (plstd)
            if lib_name == "plstd" and "lib" not in self._alias_to_lib:
                self._alias_to_lib["lib"] = "plstd"
            # Only collect includes from plib (don't generate code yet)
            self._collect_plib_includes(lib_name)

        # Collect plib info for tree-shaking (generate later after main program)
        for lib_name in local_imports:
            alias = self._current_alias.get(lib_name)
            self._collect_plib_for_tree_shake(lib_name, alias)

        for exp in exposes:
            # Check if the library was imported first
            exp_target = exp.target

            # Handle @ syntax: expose func@lib exposes a specific item from a library
            if "@" in exp_target:
                func_name, lib_name = exp_target.rsplit("@", 1)
                # Resolve lib alias to actual library name
                actual_lib = self._alias_to_lib.get(lib_name, lib_name)

                # Check if the library was imported
                lib_imported = any(
                    (imp.source == l)
                    or (imp.source == f"<{l}>")
                    or (imp.source == f'"{l}"')
                    or (imp.source.startswith(f"<{l}/"))
                    for imp in imports
                    for l in [lib_name, actual_lib]
                )
                # Also check if specific function was imported
                func_imported = any(imp.item == func_name for imp in imports)
                if not lib_imported and not func_imported:
                    raise ValueError(
                        error_msgs.get_error_msg(
                            "E801",
                            lib=lib_name,
                            item=func_name,
                            fallback=f"Cannot expose '{exp.target}' - library must be imported first. Use: using <{lib_name}> or using {func_name} from <{lib_name}> before exposing it.",
                        )
                    )
                self._exposed_libs.add(lib_name)
                self._exposed_libs.add(actual_lib)
                continue

            if exp_target.startswith("<") and exp_target.endswith(">"):
                exp_target = exp.target[1:-1]

            # Normalize: strip .plib extension for comparison
            exp_base = (
                exp_target.rsplit(".plib", 1)[0]
                if ".plib" in exp_target
                else exp_target
            )

            # Check if the library was imported
            lib_imported = any(
                (imp.source == exp_target)
                or (imp.source == f"<{exp_target}>")
                or (imp.source == f'"{exp_target}"')
                or (imp.item == exp_target)
                # Also check without .plib extension
                or (imp.source == exp_base)
                or (imp.source == f"<{exp_base}>")
                or (imp.source == f'"{exp_base}"')
                or (
                    imp.source.rsplit(".plib", 1)[0]
                    if ".plib" in imp.source
                    else imp.source
                )
                == exp_base
                for imp in imports
            )
            if not lib_imported:
                if any(
                    imp.source.startswith(f"<{exp_target}/")
                    or imp.source == f"<{exp_target}>"
                    or imp.source == exp_target
                    or imp.source.startswith(f"<{exp_base}/")
                    or imp.source == f"<{exp_base}>"
                    or imp.source == exp_base
                    for imp in imports
                ):
                    lib_imported = True
            # Track that this library is now exposed
            self._exposed_libs.add(exp_target)
            self._exposed_libs.add(exp_base)

    def _gen_plib_code(
        self, lib_name: str, alias: str = None, plib_ast: "p.Program" = None
    ):
        """Generate code from a local plib file."""
        import os
        import lexer
        import parser as p

        # Bypass checks when generating plib code itself
        old_generating = self._generating_plib
        old_imported_inits = list(self._imported_plib_inits)  # Save imported plib inits
        self._generating_plib = True
        self._imported_plib_inits = []  # Reset for this plib's imports
        seen_libs = {lib_name}  # Track which plibs we've processed in this chain

        # If AST wasn't provided, parse the file
        if plib_ast is None:
            plib_path = None
            search_name = lib_name.split("/")[-1]

            # Handle absolute paths directly
            if os.path.isabs(lib_name):
                if os.path.exists(lib_name):
                    plib_path = lib_name
                elif os.path.exists(f"{lib_name}.plib"):
                    plib_path = f"{lib_name}.plib"
            else:
                # Always check current directory and parent directories
                current_dir = (
                    os.path.dirname(self.source_path) if self.source_path else "."
                )
                search_paths = [current_dir]
                parent = os.path.dirname(current_dir)
            while parent and parent != current_dir:
                search_paths.append(parent)
                current_dir = parent
                parent = os.path.dirname(parent)
            search_paths.extend(self._get_plibs_search_dirs())

            # Handle path with folder: lib/func -> import first .plib in folder
            if "/" in lib_name:
                folder = lib_name.split("/")[0]
                for base in search_paths:
                    folder_path = os.path.join(base, folder)
                    if os.path.isdir(folder_path):
                        for f in sorted(os.listdir(folder_path)):
                            if f.endswith(".plib"):
                                plib_path = os.path.join(folder_path, f)
                                break
                        if plib_path:
                            break
            else:
                # First try direct .plib file
                for base in search_paths:
                    candidate = os.path.join(base, f"{search_name}.plib")
                    if os.path.exists(candidate):
                        plib_path = candidate
                        break

                # If no .plib file found, try as folder (import all .plib files in folder)
                if not plib_path:
                    for base in search_paths:
                        folder_path = os.path.join(base, search_name)
                        if os.path.isdir(folder_path):
                            # Import first .plib in folder
                            for f in sorted(os.listdir(folder_path)):
                                if f.endswith(".plib"):
                                    plib_path = os.path.join(folder_path, f)
                                    break
                        if plib_path:
                            break

        # If AST wasn't provided and we found a path, parse it
        if plib_ast is None:
            if not plib_path:
                return

            with open(plib_path, "r") as f:
                plib_content = f.read()

            tokens = lexer.Lexer(plib_content).lex()
            tokens.append(("EOF", "EOF", 0, 0))
            plib_ast = p.Parser(tokens).parse_program()

        # Now plib_ast is available (either passed in or just parsed)

        # Collect all includes from the plib (not emit - collected for later)
        for decl in plib_ast.declarations:
            if isinstance(decl, p.Include):
                self._collect_include(decl)
            elif isinstance(decl, p.Define):
                # Collect defines into a set too for later deduplication
                self._collected_includes.add(decl.directive)

        # Recursively generate code for imported plibs first
        for decl in plib_ast.declarations:
            if isinstance(decl, p.UsingDecl):
                source = decl.source
                # Skip system libraries like <plstd>
                if source.startswith("<") and source.endswith(">"):
                    continue
                # Skip if already imported
                if source in seen_libs:
                    continue
                seen_libs.add(source)
                # Recursively generate the imported plib's code
                self._gen_plib_code(source, None)

        # Determine the prefix to use - alias if provided, else lib_name
        if alias:
            prefix = alias
        elif "/" in lib_name:
            # Folder import - extract folder name as prefix
            prefix = lib_name.split("/")[0]
            self._exposed_libs.add(prefix)
        else:
            prefix = lib_name

        for decl in plib_ast.declarations:
            # Skip includes/defines - already handled above
            if isinstance(decl, (p.Include, p.Define)):
                continue

            # Apply prefix to top-level declarations only if alias is provided
            if alias:
                if isinstance(decl, p.Function):
                    decl.name = f"{prefix}_{decl.name}"
                elif isinstance(decl, p.Declaration):
                    decl.name = f"{prefix}_{decl.name}"

            # Handle SpaceDecl - generate with prefix + namespace prefix
            if isinstance(decl, p.SpaceDecl):
                # Determine actual generated prefix
                if prefix == decl.name:
                    actual_prefix = prefix  # e.g., math_sin
                else:
                    actual_prefix = f"{prefix}_{decl.name}"  # e.g., lib_utils_func

                # Track space name -> actual prefix mapping for @space calls
                # e.g., "math" -> "lib_math"
                self._space_prefix_map[decl.name] = actual_prefix

                # Track current space for function call prefixing
                old_space = self._current_space
                old_local_funcs = self._space_local_functions.copy()
                self._current_space = actual_prefix
                self._space_local_functions = set()

                # Update specific imports mapping with actual generated prefix
                for nested_decl in decl.declarations:
                    if isinstance(nested_decl, p.Function):
                        original_name = nested_decl.name
                        generated_name = f"{actual_prefix}_{nested_decl.name}"
                        # Track ORIGINAL name for space-local function call prefixing
                        self._space_local_functions.add(original_name)
                        # Update mapping: func -> (lib, lib_func)
                        if nested_decl.name in self._specific_imports:
                            self._specific_imports[nested_decl.name] = (
                                lib_name.split("/")[-1],
                                generated_name,
                            )

                        nested_decl.name = generated_name
                    elif isinstance(nested_decl, p.Declaration):
                        nested_decl.name = f"{actual_prefix}_{nested_decl.name}"
                    self._gen_node(nested_decl)

                # Restore previous space context
                self._current_space = old_space
                self._space_local_functions = old_local_funcs
            elif isinstance(
                decl, (p.Function, p.Declaration, p.StructDef, p.Typedef, p.EnumDef)
            ):
                # Track top-level library functions (not in any space)
                lib_key = lib_name.split("/")[-1]
                if isinstance(decl, p.Function):
                    if lib_key not in self._top_level_lib_functions:
                        self._top_level_lib_functions[lib_key] = set()
                    self._top_level_lib_functions[lib_key].add(decl.name)

                # Update specific_imports mapping for this function
                if isinstance(decl, p.Function) and decl.name in self._specific_imports:
                    self._specific_imports[decl.name] = (
                        lib_name.split("/")[-1],
                        decl.name,
                    )

                # Tree-shaking: skip unused top-level functions (unless lib is exposed)
                lib_key = lib_name.split("/")[-1]
                is_exposed = lib_key in self._exposed_libs
                if isinstance(decl, p.Function) and not is_exposed:
                    if decl.name not in self._used_functions:
                        continue  # Skip unused function

                self._gen_node(decl)

        # Generate plib init function for global dynam arrays if any
        # Also call init functions for any imported plibs that have globals
        if self._plib_global_inits or self._imported_plib_inits:
            safe_name = lib_name.replace("/", "_").replace("-", "_")
            init_func_name = f"{safe_name}_init"
            self._emit("")
            self._emit(f"void {init_func_name}(void) {{")
            # First call init functions for imported plibs (nested deps)
            for imported_init in self._imported_plib_inits:
                self._emit(f"    {imported_init}();")
            # Then initialize this plib's globals
            for init_line, push_lines in self._plib_global_inits:
                self._emit(f"    {init_line}")
                for p_line in push_lines:
                    self._emit(f"    {p_line}")
            self._emit(f"}}")
            # Only add to _plib_init_funcs if this is a top-level plib (not nested)
            # Nested plibs' inits are chained via _imported_plib_inits
            if not old_generating:
                self._plib_init_funcs.append(init_func_name)
            # Add this plib's init to parent's imported list
            self._imported_plib_inits.append(init_func_name)
            self._plib_global_inits = []  # Clear for next plib

        # Restore the flag after generating plib code
        self._generating_plib = old_generating
        # Restore imported plib inits for parent's context
        # Accumulate: parent's inits + this plib's inits
        self._imported_plib_inits = old_imported_inits + [
            i for i in self._imported_plib_inits if i not in old_imported_inits
        ]

    def _collect_plib_for_tree_shake(self, lib_name: str, alias: str = None):
        """Collect plib AST for tree-shaking - don't generate yet."""
        import os
        import lexer
        import parser as p

        plib_path = None
        search_name = lib_name.split("/")[-1]

        if os.path.isabs(lib_name):
            if os.path.exists(lib_name):
                plib_path = lib_name
            elif os.path.exists(f"{lib_name}.plib"):
                plib_path = f"{lib_name}.plib"
        else:
            current_dir = os.path.dirname(self.source_path) if self.source_path else "."
            search_paths = [current_dir]
            parent = os.path.dirname(current_dir)
            while parent and parent != current_dir:
                search_paths.append(parent)
                current_dir = parent
                parent = os.path.dirname(parent)
            search_paths.extend(self._get_plibs_search_dirs())

            for base in search_paths:
                candidate = os.path.join(base, f"{search_name}.plib")
                if os.path.exists(candidate):
                    plib_path = candidate
                    break

            if not plib_path:
                for base in search_paths:
                    folder_path = os.path.join(base, search_name)
                    if os.path.isdir(folder_path):
                        for f in sorted(os.listdir(folder_path)):
                            if f.endswith(".plib"):
                                plib_path = os.path.join(folder_path, f)
                                break
                        if plib_path:
                            break

        if not plib_path:
            return

        with open(plib_path, "r") as f:
            plib_content = f.read()

        tokens = lexer.Lexer(plib_content).lex()
        tokens.append(("EOF", "EOF", 0, 0))
        plib_ast = p.Parser(tokens).parse_program()

        # Collect includes from the plib
        for decl in plib_ast.declarations:
            if isinstance(decl, p.Include):
                self._collect_include(decl)
            elif isinstance(decl, p.Define):
                self._collected_includes.add(decl.directive)

        # Pre-populate _top_level_lib_functions so @ syntax works
        lib_key = lib_name.split("/")[-1]
        for decl in plib_ast.declarations:
            if isinstance(decl, p.Function):
                if lib_key not in self._top_level_lib_functions:
                    self._top_level_lib_functions[lib_key] = set()
                self._top_level_lib_functions[lib_key].add(decl.name)

        self._pending_plibs.append(
            {
                "lib_name": lib_name,
                "alias": alias,
                "ast": plib_ast,
            }
        )

    def _emit_pending_plibs(self):
        """Emit pending plib code with tree-shaking."""
        plib_lines = []
        for plib_info in self._pending_plibs:
            # Temporarily redirect emit to capture plib code
            old_lines = self._lines
            old_indent = self._indent
            self._lines = []
            self._indent = 0

            self._gen_plib_code(
                plib_info["lib_name"], plib_info["alias"], plib_info["ast"]
            )

            plib_lines.extend(self._lines)
            self._lines = old_lines
            self._indent = old_indent

        # Prepend plib code before main program
        if plib_lines:
            self._lines = plib_lines + self._lines

    def _get_plibs_search_dirs(self):
        """Return list of directories to search for plib files."""
        return [
            os.path.expanduser("~/.local/lib/PLIBS"),
            "/usr/lib/PLIBS",
        ]

    def _collect_plib_includes(self, lib_name: str, alias: str = None):
        """Collect includes from a plib file into self._collected_includes."""
        import os
        import lexer
        import parser as p

        plib_path = None

        # Handle absolute paths directly
        if os.path.isabs(lib_name):
            if os.path.exists(lib_name):
                plib_path = lib_name
            elif os.path.exists(f"{lib_name}.plib"):
                plib_path = f"{lib_name}.plib"
        else:
            search_dirs = []
            if self.source_path:
                src_dir = os.path.dirname(self.source_path)
                search_dirs.append(src_dir)
                parent = os.path.dirname(src_dir)
                while parent and parent != src_dir:
                    search_dirs.append(parent)
                    src_dir = parent
                    parent = os.path.dirname(parent)

            if "/" in lib_name:
                folder, filename = lib_name.split("/", 1)
                search_dirs.extend(
                    [
                        os.path.expanduser(f"~/.local/lib/PLIBS/{folder}"),
                        f"/usr/lib/PLIBS/{folder}",
                    ]
                )
            else:
                search_dirs.extend(
                    [
                        ".",
                        os.path.expanduser("~/.local/lib/PLIBS"),
                        "/usr/lib/PLIBS",
                    ]
                )

            search_name = lib_name.split("/")[-1]

            # For paths like "folder/name", look in folder subdirectory
            if "/" in lib_name:
                folder = lib_name.split("/")[0]
                for base in ["."] + self._get_plibs_search_dirs():
                    folder_path = os.path.join(base, folder)
                    if os.path.isdir(folder_path):
                        # Find any .plib file in the folder
                        for f in os.listdir(folder_path):
                            if f.endswith(".plib"):
                                plib_path = os.path.join(folder_path, f)
                                break
                        if plib_path:
                            break

            if not plib_path:
                # Standard search
                for d in self._get_plibs_search_dirs():
                    candidate = os.path.join(d, f"{search_name}.plib")
                    if os.path.exists(candidate):
                        plib_path = candidate
                        break

        if not plib_path:
            return

        self._do_collect_plib_includes(plib_path)

    def _do_collect_plib_includes(self, plib_path: str):
        """Actually parse plib and collect its includes."""
        import lexer
        import parser as p

        with open(plib_path, "r") as f:
            plib_content = f.read()

        tokens = lexer.Lexer(plib_content).lex()
        tokens.append(("EOF", "EOF", 0, 0))
        plib_ast = p.Parser(tokens).parse_program()

        for decl in plib_ast.declarations:
            if isinstance(decl, p.Include):
                self._collect_include(decl)

    # ------------------------------------------------------------------
    # Statement / declaration dispatcher
    # ------------------------------------------------------------------

    def _gen_node(self, node):
        """Dispatch to the appropriate generator."""
        if isinstance(node, Function):
            self._gen_function(node)
        elif isinstance(node, Declaration):
            self._gen_declaration(node)
        elif isinstance(node, Compound):
            self._gen_compound_block(node)
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
        elif isinstance(node, Goto):
            self._emit(f"goto {node.label};")
        elif isinstance(node, Label):
            # Labels are dedented by one level in C convention
            indent = "    " * max(0, self._indent - 1)
            self._lines.append(f"{indent}{node.name}:")
        elif isinstance(node, ExprStmt):
            self._gen_expr_stmt(node)
        elif isinstance(node, Include):
            self._collect_include(node)
        elif isinstance(node, Define):
            # Emit #define directives as-is
            self._emit(node.directive)
        elif isinstance(node, Switch):
            self._gen_switch(node)
        elif isinstance(node, StructDef):
            self._gen_struct_def(node)
        elif isinstance(node, Typedef):
            self._gen_typedef(node)
        elif hasattr(node, "node_type") and node.node_type == "ASM":
            self._gen_asm_block(node)
        elif hasattr(node, "__class__") and node.__class__.__name__ == "AsmBlock":
            self._gen_asm_block(node)
        elif isinstance(node, UsingDecl):
            pass  # Imports handled in header generation
        elif isinstance(node, ExposeDecl):
            pass  # Expose handled in header generation
        elif isinstance(node, LibAccess):
            pass  # Handled in expression context
        elif isinstance(node, SpaceDecl):
            old_space = self._current_space
            old_local_funcs = self._space_local_functions.copy()
            self._current_space = node.name
            self._space_local_functions = set()
            for decl in node.declarations:
                if isinstance(decl, Function):
                    self._space_local_functions.add(decl.name)
            for decl in node.declarations:
                self._gen_statement(decl)
            self._current_space = old_space
            self._space_local_functions = old_local_funcs
        elif node is None:
            pass  # Skip None declarations (e.g., skipped extern "C" blocks)
        else:
            # Expression used as a statement (e.g. bare assignment at top level)
            self._emit(f"{self._expr(node)};")

    # ------------------------------------------------------------------
    # Statement generators
    # ------------------------------------------------------------------

    def _gen_function(self, node: Function):
        ret_type = self._map_type(node.ret_type)
        params = []
        for p in node.params:
            ptype = p[0]
            pname = p[1]
            psize = p[2] if len(p) > 2 else None
            # Track parameter types for len() and other operations
            if ptype != "...":
                self._dynam_declarations[pname] = ptype
            if ptype == "...":
                params.append("...")
            else:
                param_str = f"{self._map_type(ptype)} {pname}"
                if psize is not None:
                    if isinstance(psize, list):
                        param_str += "[]"
                        for s in psize[1:]:
                            if s == 0:
                                param_str += "[]"
                            else:
                                param_str += f"[{s}]"
                    else:
                        if psize == 0:
                            param_str += "[]"
                        else:
                            param_str += f"[{psize}]"
                params.append(param_str)
        param_str = ", ".join(params) if params else "void"
        self._emit(f"{ret_type} {node.name}({param_str}) {{")
        self._indent += 1

        # Insert global dynam initializations at the start of main()
        if (
            node.name == "main"
            and self._global_dynam_inits
            and not self._dynam_inits_inserted
        ):
            for init_line in self._global_dynam_inits:
                self._emit(init_line)
            self._emit("")
            self._dynam_inits_inserted = True

        # Auto-call plib init functions for global dynam arrays
        if (
            node.name == "main"
            and self._plib_init_funcs
            and not self._plib_inits_called
        ):
            for init_func in self._plib_init_funcs:
                self._emit(f"{init_func}();")
            self._emit("")
            self._plib_inits_called = True

        old_in_global = self._in_global_scope
        self._in_global_scope = False

        if isinstance(node.body, Compound):
            for stmt in node.body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(node.body)
        self._indent -= 1
        self._emit("}")
        self._emit("")  # blank line after function

        self._in_global_scope = old_in_global

    def _gen_declaration(self, node: Declaration):
        original_type = node.var_type  # Keep original for special types
        typ = self._map_type(node.var_type)
        name = node.name
        array_size = getattr(node, "array_size", None)

        # Handle dynam arrays: generate as struct-based dynamic array with helper functions
        if original_type.startswith("dynam "):
            elem_type = original_type[6:]  # Get element type (after "dynam ")
            mapped_elem = self._map_type(elem_type)

            # Track this dynam declaration
            self._dynam_declarations[name] = original_type

            # Generate struct name for this dynam type
            struct_name = self._get_dynam_struct_name(elem_type)

            # Generate struct definition and helper functions (stored in _helper_lines)
            if struct_name not in self._generated_dynam_structs:
                self._generated_dynam_structs.add(struct_name)
            self._gen_dynam_helper_functions(struct_name, mapped_elem, elem_type)

            # Generate initialization code
            # At global scope in .ctri: emit declaration at file scope, track initialization for main()
            # At global scope in .plib: emit declaration at file scope, track for init function
            # At local scope: emit directly
            is_plib = self._generating_plib or self._is_plib_source
            if node.initializer and hasattr(node.initializer, "elements"):
                # Array initializer: [1, 2, 3]
                init_vals = [self._expr(e) for e in node.initializer.elements]
                init_count = len(init_vals)
                init_capacity = max(4, init_count)

                if self._in_global_scope:
                    self._emit(f"{struct_name} {name};")
                    init_line = f"{name}.data = malloc({init_capacity} * sizeof({mapped_elem})); {name}.size = 0; {name}.capacity = {init_capacity};"
                    push_lines = [
                        f"{struct_name}_push(&{name}, {v});" for v in init_vals
                    ]
                    if is_plib:
                        self._plib_global_inits.append((init_line, push_lines))
                    else:
                        self._global_dynam_inits.append(init_line)
                        self._global_dynam_inits.extend(push_lines)
                else:
                    self._emit(
                        f"{struct_name} {name} = {{malloc({init_capacity} * sizeof({mapped_elem})), 0, {init_capacity}}};"
                    )
                    for v in init_vals:
                        self._emit(f"{struct_name}_push(&{name}, {v});")
            elif node.initializer and isinstance(node.initializer, Call):
                init_expr = self._expr(node.initializer)

                if self._in_global_scope:
                    self._emit(f"{struct_name} {name};")
                    init_line = f"{name}.data = malloc(4 * sizeof({mapped_elem})); {name}.size = 0; {name}.capacity = 4;"
                    push_line = f"{struct_name}_push(&{name}, {init_expr});"
                    if is_plib:
                        self._plib_global_inits.append((init_line, [push_line]))
                    else:
                        self._global_dynam_inits.append(init_line)
                        self._global_dynam_inits.append(push_line)
                else:
                    self._emit(
                        f"{struct_name} {name} = {{malloc(4 * sizeof({mapped_elem})), 0, 4}};"
                    )
                    self._emit(f"{struct_name}_push(&{name}, {init_expr});")
            else:
                if self._in_global_scope:
                    self._emit(f"{struct_name} {name};")
                    init_line = f"{name}.data = malloc(4 * sizeof({mapped_elem})); {name}.size = 0; {name}.capacity = 4;"
                    if is_plib:
                        self._plib_global_inits.append((init_line, []))
                    else:
                        self._global_dynam_inits.append(init_line)
                else:
                    self._emit(
                        f"{struct_name} {name} = {{malloc(4 * sizeof({mapped_elem})), 0, 4}};"
                    )
            return

        # Handle string type: dynamic character array (like dynam char)
        if original_type == "string":
            # Track this string declaration
            self._dynam_declarations[name] = "string"

            # Handle string concatenation in initialization: string s = "hello" + "world";
            if (
                node.initializer
                and isinstance(node.initializer, Binary)
                and node.initializer.op == "+"
            ):
                left = node.initializer.left
                right = node.initializer.right
                # Check if both operands are string literals or string variables
                left_is_string = (
                    isinstance(left, Literal)
                    and isinstance(left.value, str)
                    and left.value.startswith('"')
                ) or (
                    isinstance(left, Var)
                    and self._get_dynam_type(left.name) == "string"
                )
                right_is_string = (
                    isinstance(right, Literal)
                    and isinstance(right.value, str)
                    and right.value.startswith('"')
                ) or (
                    isinstance(right, Var)
                    and self._get_dynam_type(right.name) == "string"
                )

                if left_is_string and right_is_string:
                    # Generate concatenation: malloc + strcpy + strcat
                    left_expr = self._expr(left)
                    right_expr = self._expr(right)
                    var_name = node.name

                    # Emit the concatenation sequence
                    self._emit(
                        f"char* _tmp = malloc(strlen({left_expr}) + strlen({right_expr}) + 1);"
                    )
                    self._emit(f"strcpy(_tmp, {left_expr});")
                    self._emit(f"strcat(_tmp, {right_expr});")
                    self._emit(f"char* {var_name} = _tmp;")
                    return

            if node.initializer and isinstance(node.initializer, Cast):
                # Cast to string: string s = (string)ptr;
                if node.initializer.cast_type == "string":
                    init_expr = self._expr(node.initializer)
                    self._emit(f"char* {name} = {init_expr};")
                    return
            if node.initializer and isinstance(node.initializer, Call):
                # Function call returning string: string s = func(...);
                init_expr = self._expr(node.initializer)
                self._emit(f"char* {name} = {init_expr};")
                return
            if node.initializer and hasattr(node.initializer, "value"):
                # String literal: "hello"
                init_val = node.initializer.value
                if isinstance(init_val, str) and init_val.startswith('"'):
                    # Generate: char* name = strdup("hello");
                    self._emit(f"char* {name} = strdup({init_val});")
                    return
            # Empty string
            self._emit(f'char* {name} = strdup("");')
            return
            # Empty string
            self._emit(f'char* {name} = strdup("");')
            return

        # Handle string to char array conversion: char s[] = "hello"
        if typ == "char" and node.initializer is not None:
            init_val = node.initializer
            if (
                hasattr(init_val, "value")
                and isinstance(init_val.value, str)
                and init_val.value.startswith('"')
            ):
                # Convert string to char array: "hello" -> {'h','e','l','l','o','\0'}
                s = init_val.value[1:-1]  # Remove quotes
                chars = [f"'{c}'" if c not in '\\"' else f"'{c}'" for c in s]
                chars.append("'\\0'")  # Add null terminator
                init_str = "{" + ", ".join(chars) + "}"
                if array_size is None:
                    # Infer size from string length + null
                    array_size = len(chars)
                    name = f"{name}[{array_size}]"
                else:
                    name = f"{name}[{array_size}]"
                self._emit(f"char {name} = {init_str};")
                return

        # Handle function prototypes: var_type is "void (func prototype)"
        if "(func prototype)" in node.var_type:
            # Extract return type and params from name if stored
            actual_type = node.var_type.replace(" (func prototype)", "")
            actual_type = self._map_type(actual_type)
            # Try to get params from node if available
            params = getattr(node, "params", None)
            if params:
                param_str = ", ".join(f"{self._map_type(p[0])} {p[1]}" for p in params)
                self._emit(f"{actual_type} {name}({param_str});")
            else:
                self._emit(f"{actual_type} {name}(void);")
            return

        # Collect dimensions from both array_size and dimensions
        dims = getattr(node, "dimensions", None)

        # Build full dimension list: use array_size for 1D, dimensions for multi-dim
        dim_list = []

        # Build full dimension list from array_size and/or dimensions
        if dims and isinstance(dims, list):
            # Use dimensions list directly (contains all dims)
            dim_list = list(dims)
        elif array_size is not None:
            # Single dimension from array_size
            if isinstance(array_size, list):
                dim_list = list(array_size)
            else:
                dim_list = [array_size]

        # If we have None in any position, try to infer from initializer
        init = node.initializer

        def count_elements_at_depth(init_list, depth):
            """Count elements at given nesting depth."""
            if depth < 0 or not init_list or not hasattr(init_list, "elements"):
                return 0
            if depth == 0:
                return len(init_list.elements) if init_list.elements else 0
            # Go deeper: use first element at each level
            if init_list.elements and init_list.elements[0]:
                return count_elements_at_depth(init_list.elements[0], depth - 1)
            return 0

        # Process each dimension position
        for i, d in enumerate(dim_list):
            if d is None:
                if init:
                    # Try to infer from initializer at this depth
                    inferred = count_elements_at_depth(init, i)
                    if inferred > 0:
                        dim_list[i] = inferred
                    else:
                        raise ValueError(
                            error_msgs.get_error_msg(
                                "E751",
                                dim=i + 1,
                                name=node.name,
                                fallback=f"Cannot infer dimension {i + 1} for array '{node.name}' - provide explicit size or ensure initializer has values at this level",
                            )
                        )
                else:
                    raise ValueError(
                        error_msgs.get_error_msg(
                            "E751",
                            dim=i + 1,
                            name=node.name,
                            fallback=f"Cannot infer dimension {i + 1} for array '{node.name}' - provide explicit size or initializer",
                        )
                    )

        # Build final name with all dimensions
        def is_valid_dim(d):
            if d is None:
                return False
            if isinstance(d, list):
                return any(is_valid_dim(x) for x in d)
            return isinstance(d, int) and d > 0

        dim_str = ""
        for d in dim_list:
            if d is None:
                continue
            if isinstance(d, list):
                dim_str += "".join(f"[{x}]" for x in d if x and isinstance(x, int))
            elif isinstance(d, int) and d > 0:
                dim_str += f"[{d}]"
        if dim_str:
            name = f"{node.name}{dim_str}"

        # Emit the declaration
        if node.initializer is not None:
            val = self._expr(node.initializer)
            self._emit(f"{typ} {name} = {val};")
        else:
            self._emit(f"{typ} {name};")

    def _get_dynam_struct_name(self, elem_type: str) -> str:
        """Generate a valid C struct name from an element type.

        Replaces invalid characters in struct names (like '*') with valid alternatives.
        """
        sanitized = elem_type.replace("*", "_ptr").replace(" ", "_")
        return f"dynam_{sanitized}"

    def _gen_dynam_helper_functions(
        self, struct_name: str, elem_type: str, original_elem_type: str
    ):
        """Generate push, pop, and len helper functions for a dynam type."""
        # Skip if already generated
        if f"{struct_name}_push" in self._generated_dynam_funcs:
            return

        # Generate struct definition
        self._helper_lines.append(f"typedef struct {{")
        self._helper_lines.append(f"    {elem_type}* data;")
        self._helper_lines.append(f"    int size;")
        self._helper_lines.append(f"    int capacity;")
        self._helper_lines.append(f"}} {struct_name};")
        self._helper_lines.append("")

        # Generate push function
        self._helper_lines.append(
            f"void {struct_name}_push({struct_name}* arr, {elem_type} val) {{"
        )
        self._helper_lines.append(f"    if (arr->size >= arr->capacity) {{")
        self._helper_lines.append(f"        arr->capacity *= 2;")
        self._helper_lines.append(
            f"        arr->data = realloc(arr->data, arr->capacity * sizeof({elem_type}));"
        )
        self._helper_lines.append(f"    }}")
        self._helper_lines.append(f"    arr->data[arr->size++] = val;")
        self._helper_lines.append(f"}}")
        self._helper_lines.append("")

        # Generate pop function
        self._helper_lines.append(
            f"{elem_type} {struct_name}_pop({struct_name}* arr) {{"
        )
        self._helper_lines.append(f"    return arr->data[--arr->size];")
        self._helper_lines.append(f"}}")
        self._helper_lines.append("")

        # Generate len function
        self._helper_lines.append(f"int {struct_name}_len({struct_name}* arr) {{")
        self._helper_lines.append(f"    return arr->size;")
        self._helper_lines.append(f"}}")
        self._helper_lines.append("")

        # Track generated functions to avoid duplicates
        self._generated_dynam_funcs.add(f"{struct_name}_push")
        self._generated_dynam_funcs.add(f"{struct_name}_pop")
        self._generated_dynam_funcs.add(f"{struct_name}_len")

    def _gen_compound_block(self, node: Compound):
        """Emit a braced block.  Used when a Compound appears as a standalone
        statement rather than as a function body (which is handled inline)."""
        if getattr(node, "_is_decl_list", False):
            for stmt in node.stmts:
                self._gen_node(stmt)
            return
        self._emit("{")
        self._indent += 1
        for stmt in node.stmts:
            self._gen_node(stmt)
        self._indent -= 1
        self._emit("}")

    def _gen_if(self, node: If):
        cond = self._expr(node.cond)
        # Don't add extra parens if condition is already a comparison (causes warnings)
        if isinstance(node.cond, Binary) and node.cond.op in (
            "==",
            "!=",
            "<",
            ">",
            "<=",
            ">=",
        ):
            self._emit(f"if ({cond}) {{")
        else:
            self._emit(f"if ({cond}) {{")
        self._indent += 1
        body = node.then_branch
        if isinstance(body, Compound):
            for stmt in body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(body)
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
        cond = self._expr(node.cond)
        # Detect the problematic pattern: (assignment != comparison)
        # This happens when parsing "entry = readdir(dir) != NULL"
        # which becomes Binary("!=", Assignment(...), NULL)
        # Output: while ((entry = readdir(dir)) != NULL) {
        # NOT: while ((entry = readdir(dir) != NULL)) {

        # Check if it's a binary with assignment on the left and comparison
        needs_fix = False
        if isinstance(node.cond, Binary) and isinstance(node.cond.left, Assignment):
            # The binary left is an assignment - need special handling
            needs_fix = True

        if needs_fix:
            # Reconstruct: (assignment) op right
            left = self._expr(node.cond.left)
            op = node.cond.op
            right = self._expr(node.cond.right)
            cond = f"({left}) {op} {right}"

        self._emit(f"while ({cond}) {{")
        self._indent += 1
        body = node.body
        if isinstance(body, Compound):
            for stmt in body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(body)
        self._indent -= 1
        self._emit("}")

    def _gen_do(self, node: Do):
        cond = self._expr(node.cond)
        self._emit("do {")
        self._indent += 1
        body = node.body
        if isinstance(body, Compound):
            for stmt in body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(body)
        self._indent -= 1
        self._emit(f"}} while ({cond});")

    def _gen_for(self, node: For):
        init_parts = []
        first_type = None
        if node.init is not None:
            if isinstance(node.init, Compound):
                for stmt in node.init.stmts:
                    if isinstance(stmt, Declaration):
                        if first_type is None:
                            first_type = self._map_type(stmt.var_type)
                            typ = first_type
                        else:
                            typ = ""
                        name = stmt.name
                        if stmt.initializer is not None:
                            if typ:
                                init_parts.append(
                                    f"{typ} {name} = {self._expr(stmt.initializer)}"
                                )
                            else:
                                init_parts.append(
                                    f"{name} = {self._expr(stmt.initializer)}"
                                )
                        else:
                            if typ:
                                init_parts.append(f"{typ} {name}")
                            else:
                                init_parts.append(name)
                    else:
                        init_parts.append(self._expr(stmt))
            elif isinstance(node.init, Declaration):
                first_type = self._map_type(node.init.var_type)
                typ = first_type
                name = node.init.name
                if node.init.initializer is not None:
                    init_parts.append(
                        f"{typ} {name} = {self._expr(node.init.initializer)}"
                    )
                else:
                    init_parts.append(f"{typ} {name}")
            else:
                init_parts.append(self._expr(node.init))
        init_str = ", ".join(init_parts)

        cond_str = self._expr(node.cond) if node.cond else ""

        post_parts = []
        if node.post is not None:
            if isinstance(node.post, Compound):
                for stmt in node.post.stmts:
                    post_parts.append(self._expr(stmt))
            else:
                post_parts.append(self._expr(node.post))
        post_str = ", ".join(post_parts)

        self._emit(f"for ({init_str}; {cond_str}; {post_str}) {{")
        self._indent += 1
        body = node.body
        if isinstance(body, Compound):
            for stmt in body.stmts:
                self._gen_node(stmt)
        else:
            self._gen_node(body)
        self._indent -= 1
        self._emit("}")

    def _gen_return(self, node: Return):
        if node.expr is not None:
            expr_str = self._expr(node.expr)
            if isinstance(node.expr, Var):
                var_name = node.expr.name
                dynam_type = self._get_dynam_type(var_name)
                if dynam_type and dynam_type.startswith("dynam "):
                    expr_str = f"{var_name}.data"
            self._emit(f"return {expr_str};")
        else:
            self._emit("return;")

    def _gen_expr_stmt(self, node: ExprStmt):
        if node.expr is not None:
            # Handle assignment to dynam/string specially
            if isinstance(node.expr, Assignment):
                target = node.expr.target
                value = node.expr.value

                # Check if target is a Var that refers to a dynam or string
                if isinstance(target, Var):
                    var_name = target.name
                    # Check if this variable is dynam or string by looking at declaration
                    dynam_type = self._get_dynam_type(var_name)

                    if dynam_type and dynam_type.startswith("dynam "):
                        # This is a reassignment to a dynam array
                        if isinstance(value, InitList):
                            init_vals = [self._expr(e) for e in value.elements]
                            elem_type = dynam_type[6:]
                            struct_name = self._get_dynam_struct_name(elem_type)
                            mapped_elem = self._map_type(elem_type)

                            # Free old data, reallocate and copy
                            self._emit(f"free({var_name}.data);")
                            init_capacity = max(4, len(init_vals))
                            self._emit(
                                f"{var_name}.data = malloc({init_capacity} * sizeof({mapped_elem}));"
                            )
                            self._emit(f"{var_name}.size = 0;")
                            self._emit(f"{var_name}.capacity = {init_capacity};")
                            for init_val in init_vals:
                                self._emit(
                                    f"{struct_name}_push(&{var_name}, {init_val});"
                                )
                            return

                    if dynam_type == "string":
                        # This is a reassignment to a string
                        if (
                            isinstance(value, Literal)
                            and isinstance(value.value, str)
                            and value.value.startswith('"')
                        ):
                            # String literal reassignment: free(s); s = strdup("new");
                            self._emit(f"free({var_name});")
                            self._emit(f"{var_name} = strdup({value.value});")
                            return
                        elif isinstance(value, Binary) and value.op == "+":
                            # String concatenation: s = s + " World"
                            right = self._expr(value.right)
                            self._emit(
                                f"{var_name} = realloc({var_name}, strlen({var_name}) + strlen({right}) + 1);"
                            )
                            self._emit(f"strcat({var_name}, {right});")
                            return

            self._emit(f"{self._expr(node.expr)};")

    def _collect_include(self, node: Include):
        if node.is_system:
            self._collected_includes.add(f"#include <{node.path}>")
        else:
            self._collected_includes.add(f'#include "{node.path}"')

    def _gen_switch(self, node: Switch):
        expr = self._expr(node.expr)
        self._emit(f"switch ({expr}) {{")
        self._indent += 1
        for case_val, body in node.cases:
            if case_val is None:
                self._emit("default:")
            else:
                self._emit(f"case {self._expr(case_val)}:")
            self._indent += 1
            if isinstance(body, Compound):
                for stmt in body.stmts:
                    self._gen_node(stmt)
            else:
                self._gen_node(body)
            self._indent -= 1
        self._indent -= 1
        self._emit("}")

    def _gen_struct_def(self, node):
        name = getattr(node, "name", "") or ""
        fields = getattr(node, "fields", []) or []
        header = f"struct {name}" if name else "struct"
        self._emit(f"{header} {{")
        self._indent += 1
        for field_type, field_name in fields:
            self._emit(f"{field_type} {field_name};")
        self._indent -= 1
        self._emit("};")  # struct definition always ends with ;

    def _gen_typedef(self, node):
        actual = getattr(node, "actual_type", "")
        alias = getattr(node, "alias", "")
        self._emit(f"typedef {actual} {alias};")

    def _gen_asm_block(self, node):
        """Pass asm blocks through verbatim."""
        content = getattr(node, "content", "") or str(node)
        self._emit_raw(content)
