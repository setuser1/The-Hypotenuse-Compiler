"""C11 code generator for C△ compiler."""

import os
import platform

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
    CompoundLiteral,
    Generic,
    Alloc,
    Free,
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
        self._scoped_var_imports = {}  # imported name -> (owner, symbol, generated name)
        self._scoped_var_globals = []
        self._emitted_scoped_var_globals = set()
        self._current_function_name = None
        self._current_alias = {}  # lib_name -> alias
        self._generating_plib = False  # Flag to bypass checks when generating plib code
        self._current_lib_name = None  # Current library name for function prefixing
        self._exposed_libs = set()  # Set of exposed library names
        self._collected_includes = set()
        # Track generated dynam helper functions and structs to avoid duplicates
        self._generated_dynam_structs = set()  # Track generated struct types
        self._generated_dynam_funcs = set()  # Track generated helper functions
        self._helper_lines = []  # Store dynam helper functions
        self._dynam_declarations = {}  # Track dynam/string declarations by name -> type
        self._len_int_generated = False  # Track if len_int helper has been generated
        self._ctri_string_helpers_generated = (
            False  # Track if internal string helpers have been generated
        )
        self._ctri_allocator_helpers_generated = (
            False  # Track if internal allocator helpers have been generated
        )
        self._current_space = None  # Current space name when generating inside a space
        self._space_local_functions = set()  # Functions defined in current space
        self._space_prefix_map = {}  # Maps space name -> actual prefix (e.g., "math" -> "lib_math")
        self._alias_to_lib = {}  # Maps alias (e.g., "lib") -> actual lib name (e.g., "mylib")
        self._top_level_lib_functions = {}  # Maps lib_name -> set of top-level function names
        self._exposed_funcs = {}  # Maps bare_name -> lib_name for exposed functions
        self._folder_libs = {}  # Maps folder alias -> list of plib names (e.g., "lib" -> ["plstd/streamer", "plstd/other"])
        self._used_functions = set()  # Track used function names for tree-shaking
        self._pending_plibs = []  # Store pending plib ASTs for tree-shaking
        self._asm_function_names = set()  # Track asm function names for macOS _ prefix
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
        self._asm_blocks = []  # Store asm blocks for later .asm file generation

    def _ensure_ctri_allocator_helpers(self):
        if self._ctri_allocator_helpers_generated:
            return
        self._ctri_allocator_helpers_generated = True
        self._helper_lines.append("")
        self._helper_lines.append("#define __CTRI_HEAP_SIZE 4194304")
        self._helper_lines.append("static char __ctri_heap[__CTRI_HEAP_SIZE];")
        self._helper_lines.append("")
        self._helper_lines.append("void* __ctri_malloc(int size) {")
        self._helper_lines.append("    int pos = 0;")
        self._helper_lines.append("    size = (size + 7) & ~7;")
        self._helper_lines.append("    if (size <= 0) return (void*)0;")
        self._helper_lines.append("    while (pos < __CTRI_HEAP_SIZE) {")
        self._helper_lines.append(
            "        int* block_size = (int*)(__ctri_heap + pos);"
        )
        self._helper_lines.append(
            "        int* block_free = (int*)(__ctri_heap + pos + sizeof(int));"
        )
        self._helper_lines.append(
            "        int* block_next = (int*)(__ctri_heap + pos + 2 * sizeof(int));"
        )
        self._helper_lines.append("        if (*block_size == 0) {")
        self._helper_lines.append("            *block_size = size;")
        self._helper_lines.append("            *block_free = 0;")
        self._helper_lines.append("            *block_next = 0;")
        self._helper_lines.append(
            "            return (void*)(__ctri_heap + pos + 2 * sizeof(int));"
        )
        self._helper_lines.append("        }")
        self._helper_lines.append("        if (*block_free && *block_size >= size) {")
        self._helper_lines.append("            int remaining = *block_size - size;")
        self._helper_lines.append(
            "            if (remaining > (int)(3 * sizeof(int))) {"
        )
        self._helper_lines.append(
            "                int next_pos = pos + 2 * sizeof(int) + size;"
        )
        self._helper_lines.append(
            "                *(int*)(__ctri_heap + next_pos) = remaining - 2 * sizeof(int);"
        )
        self._helper_lines.append(
            "                *(int*)(__ctri_heap + next_pos + sizeof(int)) = 1;"
        )
        self._helper_lines.append(
            "                *(int*)(__ctri_heap + next_pos + 2 * sizeof(int)) = 0;"
        )
        self._helper_lines.append("                *block_next = next_pos;")
        self._helper_lines.append("            }")
        self._helper_lines.append("            *block_free = 0;")
        self._helper_lines.append("            *block_size = size;")
        self._helper_lines.append(
            "            return (void*)(__ctri_heap + pos + 2 * sizeof(int));"
        )
        self._helper_lines.append("        }")
        self._helper_lines.append("        if (*block_next == 0) {")
        self._helper_lines.append(
            "            int total = *block_size + 2 * sizeof(int) + size;"
        )
        self._helper_lines.append("            *(int*)(__ctri_heap + pos) = total;")
        self._helper_lines.append(
            "            *(int*)(__ctri_heap + pos + sizeof(int)) = 0;"
        )
        self._helper_lines.append(
            "            *(int*)(__ctri_heap + pos + 2 * sizeof(int) + size) = 0;"
        )
        self._helper_lines.append(
            "            *(int*)(__ctri_heap + pos + 2 * sizeof(int) + size + sizeof(int)) = 1;"
        )
        self._helper_lines.append(
            "            *(int*)(__ctri_heap + pos + 2 * sizeof(int) + size + 2 * sizeof(int)) = 0;"
        )
        self._helper_lines.append(
            "            *(int*)(__ctri_heap + pos) = *block_size + 2 * sizeof(int) + size;"
        )
        self._helper_lines.append(
            "            *block_next = pos + 2 * sizeof(int) + size;"
        )
        self._helper_lines.append(
            "            return (void*)(__ctri_heap + pos + 2 * sizeof(int));"
        )
        self._helper_lines.append("        }")
        self._helper_lines.append("        pos = *block_next;")
        self._helper_lines.append("    }")
        self._helper_lines.append("    return (void*)0;")
        self._helper_lines.append("}")
        self._helper_lines.append("")
        self._helper_lines.append("void __ctri_free(void* ptr) {")
        self._helper_lines.append("    if (!ptr) return;")
        self._helper_lines.append(
            "    int pos = (int)((char*)ptr - __ctri_heap) - 2 * sizeof(int);"
        )
        self._helper_lines.append("    if (pos < 0 || pos >= __CTRI_HEAP_SIZE) return;")
        self._helper_lines.append("    *(int*)(__ctri_heap + pos + sizeof(int)) = 1;")
        self._helper_lines.append(
            "    int* next = (int*)(__ctri_heap + pos + 2 * sizeof(int));"
        )
        self._helper_lines.append("    while (*next != 0) {")
        self._helper_lines.append(
            "        int next_free = *(int*)(__ctri_heap + *next + sizeof(int));"
        )
        self._helper_lines.append("        if (!next_free) break;")
        self._helper_lines.append(
            "        int total = *(int*)(__ctri_heap + pos) + 2 * sizeof(int) + *(int*)(__ctri_heap + *next);"
        )
        self._helper_lines.append("        *(int*)(__ctri_heap + pos) = total;")
        self._helper_lines.append(
            "        *next = *(int*)(__ctri_heap + *next + 2 * sizeof(int));"
        )
        self._helper_lines.append("    }")
        self._helper_lines.append("}")
        self._helper_lines.append("")
        self._helper_lines.append("void* __ctri_realloc(void* ptr, int new_size) {")
        self._helper_lines.append("    if (!ptr) return __ctri_malloc(new_size);")
        self._helper_lines.append(
            "    int pos = (int)((char*)ptr - __ctri_heap) - 2 * sizeof(int);"
        )
        self._helper_lines.append(
            "    if (pos < 0 || pos >= __CTRI_HEAP_SIZE) return (void*)0;"
        )
        self._helper_lines.append("    int old_size = *(int*)(__ctri_heap + pos);")
        self._helper_lines.append("    new_size = (new_size + 7) & ~7;")
        self._helper_lines.append("    if (new_size <= old_size) return ptr;")
        self._helper_lines.append(
            "    int* next = (int*)(__ctri_heap + pos + 2 * sizeof(int));"
        )
        self._helper_lines.append("    if (*next != 0) {")
        self._helper_lines.append(
            "        int next_free = *(int*)(__ctri_heap + *next + sizeof(int));"
        )
        self._helper_lines.append("        if (next_free) {")
        self._helper_lines.append(
            "            int next_size = *(int*)(__ctri_heap + *next);"
        )
        self._helper_lines.append(
            "            int combined = old_size + 2 * sizeof(int) + next_size;"
        )
        self._helper_lines.append("            if (combined >= new_size) {")
        self._helper_lines.append(
            "                int remaining = combined - new_size - 2 * sizeof(int);"
        )
        self._helper_lines.append(
            "                *(int*)(__ctri_heap + pos) = new_size;"
        )
        self._helper_lines.append("                if (remaining > 0) {")
        self._helper_lines.append(
            "                    int next_pos = pos + 2 * sizeof(int) + new_size;"
        )
        self._helper_lines.append(
            "                    *(int*)(__ctri_heap + next_pos) = remaining;"
        )
        self._helper_lines.append(
            "                    *(int*)(__ctri_heap + next_pos + sizeof(int)) = 1;"
        )
        self._helper_lines.append(
            "                    *(int*)(__ctri_heap + next_pos + 2 * sizeof(int)) = 0;"
        )
        self._helper_lines.append("                    *next = next_pos;")
        self._helper_lines.append("                }")
        self._helper_lines.append("                return ptr;")
        self._helper_lines.append("            }")
        self._helper_lines.append("        }")
        self._helper_lines.append("    }")
        self._helper_lines.append("    void* new_ptr = __ctri_malloc(new_size);")
        self._helper_lines.append("    if (new_ptr) {")
        self._helper_lines.append("        char* src = (char*)ptr;")
        self._helper_lines.append("        char* dst = (char*)new_ptr;")
        self._helper_lines.append("        int i;")
        self._helper_lines.append(
            "        for (i = 0; i < old_size; i++) dst[i] = src[i];"
        )
        self._helper_lines.append("    }")
        self._helper_lines.append("    __ctri_free(ptr);")
        self._helper_lines.append("    return new_ptr;")
        self._helper_lines.append("}")
        self._helper_lines.append("")

    def _ensure_ctri_string_helpers(self):
        if self._ctri_string_helpers_generated:
            return
        self._ctri_string_helpers_generated = True
        self._ensure_ctri_allocator_helpers()
        self._helper_lines.append("")
        self._helper_lines.append("int __ctri_strlen(char* s) {")
        self._helper_lines.append("    char* p = s;")
        self._helper_lines.append("    while (*p) p++;")
        self._helper_lines.append("    return (int)(p - s);")
        self._helper_lines.append("}")
        self._helper_lines.append("")
        self._helper_lines.append("char* __ctri_strcpy(char* dest, char* src) {")
        self._helper_lines.append("    char* d = dest;")
        self._helper_lines.append("    while ((*d++ = *src++));")
        self._helper_lines.append("    return dest;")
        self._helper_lines.append("}")
        self._helper_lines.append("")
        self._helper_lines.append("char* __ctri_strcat(char* dest, char* src) {")
        self._helper_lines.append("    char* d = dest;")
        self._helper_lines.append("    while (*d) d++;")
        self._helper_lines.append("    while ((*d++ = *src++));")
        self._helper_lines.append("    return dest;")
        self._helper_lines.append("}")
        self._helper_lines.append("")
        self._helper_lines.append("char* __ctri_strdup(char* s) {")
        self._helper_lines.append("    int len = __ctri_strlen(s);")
        self._helper_lines.append("    char* d = __ctri_malloc(len + 1);")
        self._helper_lines.append("    if (d) __ctri_strcpy(d, s);")
        self._helper_lines.append("    return d;")
        self._helper_lines.append("}")
        self._helper_lines.append("")

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

        # If we generated dynam helpers, prepend them after includes
        if self._helper_lines:
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
            new_lines = includes + [""] + self._helper_lines + [""] + rest
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
            scoped_var = self._scoped_var_imports.get(node.name)
            if scoped_var and self._current_function_name != scoped_var[0]:
                return scoped_var[2]
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
                    # String concatenation: malloc + strcpy + strcat
                    left_expr = self._expr(node.left)
                    right_expr = self._expr(node.right)
                    self._ensure_ctri_string_helpers()
                    return (
                        f"({{ char* _ct = __ctri_malloc(__ctri_strlen({left_expr}) + __ctri_strlen({right_expr}) + 1); "
                        f"__ctri_strcpy(_ct, {left_expr}); __ctri_strcat(_ct, {right_expr}); _ct; }})"
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
            if isinstance(node.callee, FieldAccess):
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
                                    self._ensure_ctri_string_helpers()
                                    return f"__ctri_strlen({var_name})"

                            # For regular C arrays, we'd need symbol table info
                            # For now, try to use sizeof approach: sizeof(arr)/sizeof(arr[0])
                            # This works for static arrays
                            # Generate: sizeof(var)/sizeof(var[0])
                            return f"(int)(sizeof({var_name})/sizeof({var_name}[0]))"

                        # Handle other expressions - default to strlen for strings
                        arg_expr = self._expr(arg)
                        self._ensure_ctri_string_helpers()
                        return f"__ctri_strlen({arg_expr})"

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
                # If func_name is None, the function is a top-level plib function
                # whose generated name is {lib_name}_{base_callee}.
                # When called without @ syntax, resolve to the prefixed name.
                if func_name is None or func_name == base_callee:
                    # Handle @ syntax (func@namespace -> namespace_func)
                    if "@" in callee:
                        parts = callee.rsplit("@", 1)
                        if len(parts) == 2:
                            func_part, namespace = parts
                            if not func_part or not namespace:
                                raise ValueError(
                                    error_msgs.get_error_msg(
                                        "E805",
                                        callee=callee,
                                        fallback=f"Malformed '@' syntax in '{callee}'. Function name and library name cannot be empty.",
                                    )
                                )
                            if namespace == lib_name:
                                callee = f"{lib_name}_{func_part}"
                            elif (
                                "/" in lib_name and namespace == lib_name.split("/")[0]
                            ):
                                callee = f"{namespace}_{func_part}"
                            elif namespace in self._alias_to_lib:
                                actual_lib = self._alias_to_lib[namespace]
                                callee = f"{actual_lib}_{func_part}"
                            else:
                                raise SyntaxError(
                                    error_msgs.get_error_msg(
                                        "E804",
                                        alias=namespace,
                                        fallback=f"Invalid alias '{namespace}'. Library not imported or does not exist.",
                                    )
                                )
                        else:
                            raise SyntaxError(
                                error_msgs.get_error_msg(
                                    "E805",
                                    callee=callee,
                                    fallback=f"Malformed '@' syntax in '{callee}'. Expected format: function@library",
                                )
                            )
                    elif func_name is None:
                        # Bare name call to an imported plib function - resolve to
                        # the prefixed name {lib_name}_{base_callee}.
                        # This handles exposed libraries where bare names should
                        # resolve to the generated C function name.
                        callee = f"{lib_name}_{base_callee}"
                elif "&" in str(lib_name):
                    # Chain like a&b&c - transform
                    scope_chain = lib_name
                    callee = scope_chain.replace("&", "_") + "_" + func_name
                elif lib_name != func_name:
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
                # First check if function is exposed - if so, resolve to prefixed name
                exposed_funcs = getattr(self, "_exposed_funcs", {})
                if base_callee in exposed_funcs:
                    # Exposed function - resolve to the imported library wrapper.
                    lib_key = exposed_funcs[base_callee]
                    callee = f"{lib_key}_{base_callee}"
                else:
                    # Check if function exists in any imported plib's top-level functions
                    for lib_name, funcs in getattr(
                        self, "_top_level_lib_functions", {}
                    ).items():
                        if base_callee in funcs or f"{lib_name}_{base_callee}" in funcs:
                            raise SyntaxError(
                                error_msgs.get_error_msg(
                                    "E802",
                                    lib=lib_name,
                                    func=base_callee,
                                    fallback=f"Function '{base_callee}' requires '{base_callee}@{lib_name}()' syntax (library '{lib_name}' not exposed). Use 'expose {base_callee}@{lib_name}' before calling.",
                                )
                            )

            # When generating plib code, prefix internal calls to other plib functions
            # Don't add prefix if callee already contains underscore (already prefixed)
            elif (
                getattr(self, "_generating_plib", False)
                and "@" not in callee
                and "_" not in base_callee
            ):
                top_level_funcs = getattr(self, "_top_level_lib_functions", {})
                current_lib = getattr(self, "_current_lib_name", None)
                if current_lib:
                    # Check if current_lib matches a key with generated names containing the bare func
                    matching_key = None
                    # First, try exact match (prefer current_lib key)
                    if current_lib in top_level_funcs:
                        for func in top_level_funcs[current_lib]:
                            # Must end with _base_callee and start with key_
                            if func == f"{current_lib}_{base_callee}":
                                matching_key = current_lib
                                break
                    # If no exact match, try prefix matches (prefer longer matches)
                    if not matching_key:
                        best_match = None
                        best_len = 0
                        for key, funcs in top_level_funcs.items():
                            if key == current_lib:
                                continue  # Already checked
                            is_match = key.startswith(
                                f"{current_lib}_"
                            ) or key.startswith(f"{current_lib}/")
                            if is_match and len(key) > best_len:
                                for func in funcs:
                                    # Must be key_prefix + _ + base_callee
                                    if func == f"{key}_{base_callee}":
                                        best_match = key
                                        best_len = len(key)
                                        break
                        matching_key = best_match
                    if matching_key:
                        callee = f"{matching_key}_{base_callee}"

            # Handle namespace prefix like "func@lib" or "func@space" -> "prefix_func"
            # @ is for calling space-local functions or top-level library functions
            elif "@" in callee:
                parts = callee.split("@")
                if len(parts) == 2:
                    func, namespace = parts
                    # Check if this is a space-local function (preferred)
                    if namespace in self._space_prefix_map:
                        actual_prefix = self._space_prefix_map[namespace]
                        # If we're already inside this space, don't add prefix again
                        if self._current_space == actual_prefix:
                            callee = func  # Function is already prefixed
                        else:
                            callee = f"{actual_prefix}_{func}"
                    elif namespace in self._alias_to_lib:
                        # @lib or other valid alias
                        actual_lib = self._alias_to_lib[namespace]
                        found = False
                        # Use library name as prefix
                        # Search through all matching lib_keys (handles folder plibs and space-prefixed funcs)
                        for lib_key, funcs in self._top_level_lib_functions.items():
                            if not (
                                lib_key == actual_lib
                                or lib_key.startswith(f"{actual_lib}_")
                            ):
                                continue
                            for generated_name in funcs:
                                # Check if this generated name ends with _func (original function name)
                                suffix = f"_{func}"
                                if generated_name.endswith(suffix):
                                    callee = generated_name
                                    found = True
                                    break
                            if found:
                                break
                        if not found:
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
                        found = False
                        for generated_name in self._top_level_lib_functions[namespace]:
                            suffix = f"_{func}"
                            if generated_name.endswith(suffix):
                                callee = generated_name
                                found = True
                                break
                        if not found:
                            raise SyntaxError(
                                error_msgs.get_error_msg(
                                    "E803",
                                    func=func,
                                    lib=namespace,
                                    fallback=f"Function '{func}' not found in library '{namespace}'.",
                                )
                            )
                    else:
                        # Invalid alias
                        raise SyntaxError(
                            error_msgs.get_error_msg(
                                "E804",
                                alias=namespace,
                                fallback=f"Invalid alias '{namespace}'. Library not imported or does not exist.",
                            )
                        )
                else:
                    # Malformed @ syntax (e.g., func@@lib or func@lib@extra)
                    raise SyntaxError(
                        error_msgs.get_error_msg(
                            "E805",
                            callee=callee,
                            fallback=f"Malformed '@' syntax in '{callee}'. Expected format: function@library",
                        )
                    )
            # Track this function call for tree-shaking plibs
            # Only track external calls, not internal plib calls
            if not getattr(self, "_generating_plib", False):
                self._used_functions.add(base_callee)
                # Also track prefixed name when @ alias was used (function generated as lib_func)
                if callee != base_callee:
                    self._used_functions.add(callee)

            # On macOS, asm functions need _ prefix for C linkage
            # This must happen AFTER @ resolution
            if platform.system() == "Darwin" and callee in self._asm_function_names:
                callee = f"_{callee}"

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

    def _gen_program_code(self, node):
        # Now emit collected includes at the very beginning (prepend)
        includes_to_emit = []
        for inc in sorted(self._collected_includes):
            includes_to_emit.append(inc)
        # Prepend includes before any existing code
        self._lines = includes_to_emit + self._lines
        # Now generate rest of code (plib functions included via _gen_plib_code)
        for line in self._scoped_var_globals:
            self._emit(line)
        if self._scoped_var_globals:
            self._emit("")

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
            self._emit("void " + safe_name + "_init(void) {")
            for init_line, push_lines in self._plib_global_inits:
                self._emit(f"    {init_line}")
                for p_line in push_lines:
                    self._emit(f"    {p_line}")
            self._emit("}")

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
                # Handle intra-file imports: using owner&symbol or using a&b&c&symbol.
                parts = source.split("&")
                if len(parts) >= 2:
                    symbol_name = parts[-1]
                    scope_chain = "&".join(parts[:-1])
                    imported_name = imp.alias or symbol_name
                    generated_name = self._resolve_scoped_var_import(
                        scope_chain, symbol_name
                    )
                    if generated_name:
                        self._scoped_var_imports[imported_name] = (
                            scope_chain,
                            symbol_name,
                            generated_name,
                        )
                    if imp.alias:
                        self._specific_imports[symbol_name] = (imp.alias, imp.alias)
                    else:
                        self._specific_imports[symbol_name] = (scope_chain, symbol_name)
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
            else:
                # No explicit alias - use lib name itself for @libname syntax
                self._alias_to_lib[lib_name] = lib_name
            # "lib" is an alias for the standard library (plstd)
            if lib_name == "plstd" and "lib" not in self._alias_to_lib:
                self._alias_to_lib["lib"] = "plstd"
                # When using <plstd>, also scan folder for all plibs
                self._scan_plib_folder("plstd")
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
                # Track exposed function: bare_name -> actual_prefix
                # Find the actual lib key in _top_level_lib_functions
                prefixed_lib = actual_lib  # Default prefix
                for lib_key in self._top_level_lib_functions:
                    # Check if this is a folder plib (e.g., plstd_printd from plstd/printd)
                    if lib_key.replace("_", "/").endswith(
                        f"/{func_name}"
                    ) or lib_key.endswith(f"_{func_name}"):
                        if any(
                            name.endswith(f"_{func_name}")
                            for name in self._top_level_lib_functions[lib_key]
                        ):
                            # Extract the actual prefix from the compound key
                            if lib_key.startswith(f"{actual_lib}_"):
                                prefixed_lib = lib_key[len(actual_lib) + 1:]
                            else:
                                prefixed_lib = lib_key
                            self._exposed_libs.add(prefixed_lib)
                            break
                self._exposed_funcs[func_name] = prefixed_lib
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
            # Add all functions from this library to _exposed_funcs
            for lib_key in list(self._top_level_lib_functions.keys()):
                matches = (
                    lib_key == exp_base
                    or lib_key.startswith(f"{exp_base}_")
                    or lib_key.replace("_", "/") == exp_base
                    or lib_key == exp_base.replace("/", "_")
                )
                if matches:
                    # Determine the actual prefix used for function names
                    if lib_key == exp_base:
                        actual_prefix = lib_key
                    elif lib_key.startswith(f"{exp_base}_"):
                        actual_prefix = lib_key[len(exp_base) + 1:]
                    else:
                        actual_prefix = lib_key
                    self._exposed_libs.add(actual_prefix)
                    for full_func_name in self._top_level_lib_functions[lib_key]:
                        expected_prefix = f"{actual_prefix}_"
                        if full_func_name.startswith(expected_prefix):
                            bare_name = full_func_name[len(expected_prefix) :]
                            self._exposed_funcs[bare_name] = actual_prefix

    def _resolve_scoped_var_import(self, owner, symbol):
        """Return the generated C name for an intra-file variable import."""
        if self.structor is None:
            return None

        objects = getattr(self.structor, "objects", {})
        owner_node = objects.get(f"{owner}::{symbol}")
        program_node = objects.get(f"program::{symbol}")
        if owner_node is None or not getattr(owner_node, "is_variable", False):
            return None

        if program_node is not None and getattr(program_node, "is_variable", False):
            return symbol

        generated_name = f"{owner.replace('&', '_')}_{symbol}"
        if generated_name not in self._emitted_scoped_var_globals:
            c_type = self._map_type(getattr(owner_node, "var_type", None) or "int")
            value = getattr(owner_node, "value", None)
            if value is None:
                self._scoped_var_globals.append(f"{c_type} {generated_name};")
            else:
                self._scoped_var_globals.append(
                    f"{c_type} {generated_name} = {self._literal_to_c(value)};"
                )
            self._emitted_scoped_var_globals.add(generated_name)
        return generated_name

    def _literal_to_c(self, value):
        if isinstance(value, str):
            stripped = value.lstrip("-")
            if (
                value.startswith('"')
                or value.startswith("'")
                or stripped.isdigit()
                or stripped.replace(".", "", 1).isdigit()
            ):
                return value
            return f'"{value}"'
        return str(value)

    def _gen_plib_code(
        self, lib_name: str, alias: str = None, plib_ast=None, plib_path=None
    ):
        """Generate code from a local plib file."""
        import os
        import lexer
        import parser as p

        # Bypass checks when generating plib code itself
        old_generating = self._generating_plib
        old_imported_inits = list(self._imported_plib_inits)  # Save imported plib inits
        old_lib_name = self._current_lib_name
        old_plib_dir = getattr(self, "_current_plib_dir", None)
        self._generating_plib = True
        # Compute prefix same way as function generation (use last path component)
        if "/" in lib_name:
            parts = [p for p in lib_name.split("/") if p and p != "." and p != ".."]
            self._current_lib_name = parts[-1] if parts else lib_name.split("/")[-1]
        else:
            self._current_lib_name = lib_name
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
                if not current_dir:
                    current_dir = "."
                search_paths = [current_dir]
                parent = os.path.dirname(current_dir)
                while parent and parent != current_dir:
                    search_paths.append(parent)
                    current_dir = parent
                    parent = os.path.dirname(parent)
                search_paths.append(".")  # Always include CWD
                # Also include the current plib's directory for recursive imports
                plib_dir = getattr(self, "_current_plib_dir", None)
                if plib_dir and plib_dir not in search_paths:
                    search_paths.insert(0, plib_dir)
            search_paths.extend(self._get_plibs_search_dirs())

            # Handle path with folder: lib/func -> import first .plib in folder
            if "/" in lib_name:
                folder, filename = lib_name.split("/", 1)
                target_name = f"{filename}.plib"
                for base in search_paths:
                    candidate = os.path.join(base, folder, target_name)
                    if os.path.exists(candidate):
                        plib_path = candidate
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

        # Track current plib directory for recursive using resolution
        self._current_plib_dir = (
            os.path.dirname(plib_path)
            if plib_path
            else getattr(self, "_current_plib_dir", None)
        )

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

        # Determine the prefix to use - always use lib_name (alias is just for call resolution)
        if "/" in lib_name:
            # Folder import - extract last meaningful path component as prefix
            parts = [p for p in lib_name.split("/") if p and p != "." and p != ".."]
            prefix = parts[-1] if parts else lib_name.split("/")[-1]
        else:
            prefix = lib_name

        for decl in plib_ast.declarations:
            # Skip includes/defines - already handled above
            if isinstance(decl, (p.Include, p.Define)):
                continue

            # Apply prefix to top-level declarations
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
            elif isinstance(decl, p.AsmBlock):
                # Prefix asm function names
                if decl.is_function and decl.name:
                    decl.name = f"{prefix}_{decl.name}"
                    # Track for internal calls within plib
                    lib_key = lib_name.split("/")[-1]
                    if lib_key not in self._top_level_lib_functions:
                        self._top_level_lib_functions[lib_key] = set()
                    self._top_level_lib_functions[lib_key].add(decl.name)
                    # Track for macOS _ prefix resolution
                    self._asm_function_names.add(decl.name)
                self._gen_asm_block(decl)
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
                lib_key = prefix  # Use the computed prefix
                is_exposed = lib_key in self._exposed_libs
                if isinstance(decl, p.Function) and not is_exposed:
                    # Get the bare function name (original before prefixing)
                    # The function name is already prefixed as "prefix_funcname"
                    if decl.name.startswith(f"{lib_key}_"):
                        bare_name = decl.name[len(lib_key) + 1 :]
                    else:
                        bare_name = decl.name
                    # Check if function is used: any form of the name
                    if (
                        bare_name not in self._used_functions
                        and decl.name not in self._used_functions
                    ):
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
            self._emit("}")
            # Only add to _plib_init_funcs if this is a top-level plib (not nested)
            # Nested plibs' inits are chained via _imported_plib_inits
            if not old_generating:
                self._plib_init_funcs.append(init_func_name)
            # Add this plib's init to parent's imported list
            self._imported_plib_inits.append(init_func_name)
            self._plib_global_inits = []  # Clear for next plib

        # Restore the flag after generating plib code
        self._generating_plib = old_generating
        self._current_lib_name = old_lib_name  # Restore library name
        self._current_plib_dir = old_plib_dir  # Restore plib directory
        # Restore imported plib inits for parent's context
        # Accumulate: parent's inits + this plib's inits
        self._imported_plib_inits = old_imported_inits + [
            i for i in self._imported_plib_inits if i not in old_imported_inits
        ]

    def _collect_plib_for_tree_shake(self, lib_name: str, alias: str = None):
        """Collect plib AST for tree-shaking - don't generate yet."""
        import os

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

            if "/" in lib_name:
                folder, filename = lib_name.split("/", 1)
                target_name = f"{filename}.plib"
                for base in search_paths:
                    candidate = os.path.join(base, folder, target_name)
                    if os.path.exists(candidate):
                        plib_path = candidate
                        break
            else:
                for base in search_paths:
                    candidate = os.path.join(base, f"{search_name}.plib")
                    if os.path.exists(candidate):
                        plib_path = candidate
                        break

                if not plib_path:
                    # Check if this is a folder containing plibs
                    for base in search_paths:
                        folder_path = os.path.join(base, search_name)
                        if os.path.isdir(folder_path):
                            # Collect ALL plibs in the folder
                            for f in sorted(os.listdir(folder_path)):
                                if f.endswith(".plib"):
                                    full_plib_path = os.path.join(folder_path, f)
                                    plib_name = f[:-5]  # Remove .plib extension
                                    full_lib_name = f"{search_name}/{plib_name}"
                                    self._collect_single_plib(
                                        full_plib_path, full_lib_name, alias
                                    )
                            return  # All plibs collected, return

        if not plib_path:
            return

        self._collect_single_plib(plib_path, lib_name, alias)

    def _collect_single_plib(self, plib_path: str, lib_name: str, alias: str = None):
        """Collect a single plib file for tree-shaking."""
        import lexer
        import parser as p

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
        # Use computed prefix (same as in _gen_plib_code)
        # For "plstd/streamer", prefix is "streamer"; for "streamer", prefix is "streamer"
        # FIX: Use the LAST part of the path as the library name
        if "/" in lib_name:
            parts = lib_name.split("/")
            clean_parts = [p for p in parts if p and p != "." and p != ".."]
            prefix = clean_parts[-1] if clean_parts else lib_name
        else:
            prefix = lib_name
        for decl in plib_ast.declarations:
            if isinstance(decl, p.Function):
                # Top-level functions get prefix_ prefix
                if prefix not in self._top_level_lib_functions:
                    self._top_level_lib_functions[prefix] = set()
                self._top_level_lib_functions[prefix].add(f"{prefix}_{decl.name}")
            elif isinstance(decl, p.AsmBlock) and decl.is_function and decl.name:
                # Asm functions get prefix_ prefix
                if prefix not in self._top_level_lib_functions:
                    self._top_level_lib_functions[prefix] = set()
                self._top_level_lib_functions[prefix].add(f"{prefix}_{decl.name}")
                # Track for macOS _ prefix resolution
                self._asm_function_names.add(f"{prefix}_{decl.name}")
            elif isinstance(decl, p.SpaceDecl):
                # Functions inside a space get prefix_space_ prefix
                if prefix not in self._top_level_lib_functions:
                    self._top_level_lib_functions[prefix] = set()
                space_prefix = f"{prefix}_{decl.name}"
                for nested_decl in decl.declarations:
                    if isinstance(nested_decl, p.Function):
                        self._top_level_lib_functions[prefix].add(
                            f"{space_prefix}_{nested_decl.name}"
                        )
                    elif (
                        isinstance(nested_decl, p.AsmBlock)
                        and nested_decl.is_function
                        and nested_decl.name
                    ):
                        self._top_level_lib_functions[prefix].add(
                            f"{space_prefix}_{nested_decl.name}"
                        )

        # Mark this AST as coming from a plib
        self._mark_plib_ast(plib_ast)

        self._pending_plibs.append(
            {
                "lib_name": lib_name,
                "alias": alias,
                "ast": plib_ast,
                "plib_path": plib_path,
            }
        )

    def _mark_plib_ast(self, plib_ast):
        """Mark all declarations in a plib AST as coming from a plib."""
        for decl in plib_ast.declarations:
            decl._from_plib = True
            if hasattr(decl, "body") and hasattr(decl.body, "statements"):
                self._mark_plib_body(decl.body)
            if hasattr(decl, "declarations"):
                for nested in decl.declarations:
                    nested._from_plib = True
                    if hasattr(nested, "body") and hasattr(nested.body, "statements"):
                        self._mark_plib_body(nested.body)

    def _mark_plib_body(self, body):
        """Recursively mark all statements in a body as from plib."""
        if not hasattr(body, "statements"):
            return
        for stmt in body.statements:
            stmt._from_plib = True
            if hasattr(stmt, "body") and hasattr(stmt.body, "statements"):
                self._mark_plib_body(stmt.body)
            if hasattr(stmt, "else_branch") and stmt.else_branch:
                if hasattr(stmt.else_branch, "statements"):
                    self._mark_plib_body(stmt.else_branch)

    def _emit_pending_plibs(self):
        """Emit pending plib code with tree-shaking."""
        import copy

        plib_lines = []
        for plib_info in self._pending_plibs:
            # Temporarily redirect emit to capture plib code
            old_lines = self._lines
            old_indent = self._indent
            self._lines = []
            self._indent = 0

            # Make a deep copy of the AST to avoid mutating the original
            plib_ast_copy = copy.deepcopy(plib_info["ast"])

            self._gen_plib_code(
                plib_info["lib_name"],
                plib_info["alias"],
                plib_ast_copy,
                plib_info.get("plib_path"),
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

    def _scan_plib_folder(self, folder_name: str):
        """Scan a folder for plib files and collect their top-level functions."""
        import os
        import lexer
        import parser as p

        search_dirs = []
        if self.source_path:
            src_dir = os.path.dirname(self.source_path)
            search_dirs.append(src_dir)
            parent = os.path.dirname(src_dir)
            while parent and parent != src_dir:
                search_dirs.append(parent)
                src_dir = parent
                parent = os.path.dirname(parent)
        search_dirs.extend(self._get_plibs_search_dirs())

        # Search for the folder in search dirs
        folder_path = None
        for base in search_dirs:
            candidate = os.path.join(base, folder_name)
            if os.path.isdir(candidate):
                folder_path = candidate
                break

        if not folder_path:
            return

        # Scan for all .plib files in the folder
        for filename in sorted(os.listdir(folder_path)):
            if filename.endswith(".plib"):
                plib_name = filename[:-5]  # Remove .plib extension
                plib_path = os.path.join(folder_path, filename)
                # Use underscores for consistent prefixing (e.g., plstd_streamer)
                full_lib_name = f"{folder_name}_{plib_name}"

                try:
                    with open(plib_path, "r") as f:
                        plib_content = f.read()

                    tokens = lexer.Lexer(plib_content).lex()
                    tokens.append(("EOF", "EOF", 0, 0))
                    plib_ast = p.Parser(tokens).parse_program()

                    # Collect top-level functions (prefixed with plib_name)
                    if full_lib_name not in self._top_level_lib_functions:
                        self._top_level_lib_functions[full_lib_name] = set()
                    for decl in plib_ast.declarations:
                        if isinstance(decl, p.Function):
                            self._top_level_lib_functions[full_lib_name].add(
                                f"{plib_name}_{decl.name}"
                            )
                        elif (
                            isinstance(decl, p.AsmBlock)
                            and decl.is_function
                            and decl.name
                        ):
                            self._top_level_lib_functions[full_lib_name].add(
                                f"{plib_name}_{decl.name}"
                            )
                except Exception:
                    continue

    def _collect_plib_includes(self, lib_name: str, alias: str = None):
        """Collect includes from a plib file into self._collected_includes."""
        import os

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
        elif isinstance(node, (UsingDecl, ExposeDecl, LibAccess)) or node is None:
            return
        elif isinstance(node, SpaceDecl):
            old_space = self._current_space
            old_local_funcs = self._space_local_functions.copy()
            self._current_space = node.name
            self._space_local_functions = set()
            for decl in node.declarations:
                if isinstance(decl, Function):
                    self._space_local_functions.add(decl.name)
            for decl in node.declarations:
                self._gen_node(decl)
            self._current_space = old_space
            self._space_local_functions = old_local_funcs
        elif isinstance(node, Alloc):
            self._gen_alloc(node)
        elif isinstance(node, Free):
            self._gen_free(node)
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
        func_name = node.name
        # Add lib prefix only for non-plib top-level functions
        # (plib functions are already prefixed in _gen_plib_code)
        if (
            self._current_lib_name
            and not self._is_plib_source
            and not self._current_space
            and not self._generating_plib
        ):
            func_name = f"{self._current_lib_name}_{func_name}"
        self._emit(f"{ret_type} {func_name}({param_str}) {{")
        self._indent += 1
        old_function_name = self._current_function_name
        self._current_function_name = node.name

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

        try:
            if isinstance(node.body, Compound):
                for stmt in node.body.stmts:
                    self._gen_node(stmt)
            else:
                self._gen_node(node.body)
        finally:
            self._current_function_name = old_function_name
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
                    init_line = f"{name}.data = __ctri_malloc({init_capacity} * sizeof({mapped_elem})); {name}.size = 0; {name}.capacity = {init_capacity};"
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
                        f"{struct_name} {name} = {{__ctri_malloc({init_capacity} * sizeof({mapped_elem})), 0, {init_capacity}}};"
                    )
                    for v in init_vals:
                        self._emit(f"{struct_name}_push(&{name}, {v});")
            elif node.initializer and isinstance(node.initializer, Call):
                init_expr = self._expr(node.initializer)

                if self._in_global_scope:
                    self._emit(f"{struct_name} {name};")
                    init_line = f"{name}.data = __ctri_malloc(4 * sizeof({mapped_elem})); {name}.size = 0; {name}.capacity = 4;"
                    push_line = f"{struct_name}_push(&{name}, {init_expr});"
                    if is_plib:
                        self._plib_global_inits.append((init_line, [push_line]))
                    else:
                        self._global_dynam_inits.append(init_line)
                        self._global_dynam_inits.append(push_line)
                else:
                    self._emit(
                        f"{struct_name} {name} = {{__ctri_malloc(4 * sizeof({mapped_elem})), 0, 4}};"
                    )
                    self._emit(f"{struct_name}_push(&{name}, {init_expr});")
            else:
                if self._in_global_scope:
                    self._emit(f"{struct_name} {name};")
                    init_line = f"{name}.data = __ctri_malloc(4 * sizeof({mapped_elem})); {name}.size = 0; {name}.capacity = 4;"
                    if is_plib:
                        self._plib_global_inits.append((init_line, []))
                    else:
                        self._global_dynam_inits.append(init_line)
                else:
                    self._emit(
                        f"{struct_name} {name} = {{__ctri_malloc(4 * sizeof({mapped_elem})), 0, 4}};"
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
                    self._ensure_ctri_string_helpers()
                    left_expr = self._expr(left)
                    right_expr = self._expr(right)
                    var_name = node.name

                    # Emit the concatenation sequence
                    self._emit(
                        f"char* _tmp = __ctri_malloc(__ctri_strlen({left_expr}) + __ctri_strlen({right_expr}) + 1);"
                    )
                    self._emit(f"__ctri_strcpy(_tmp, {left_expr});")
                    self._emit(f"__ctri_strcat(_tmp, {right_expr});")
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
                    self._ensure_ctri_string_helpers()
                    self._emit(f"char* {name} = __ctri_strdup({init_val});")
                    return
            # Empty string
            self._ensure_ctri_string_helpers()
            self._emit(f'char* {name} = __ctri_strdup("");')
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
        self._helper_lines.append("typedef struct {")
        self._helper_lines.append("    " + elem_type + "* data;")
        self._helper_lines.append("    int size;")
        self._helper_lines.append("    int capacity;")
        self._helper_lines.append("} " + struct_name + ";")
        self._helper_lines.append("")

        # Generate push function
        self._helper_lines.append(
            "void "
            + struct_name
            + "_push("
            + struct_name
            + "* arr, "
            + elem_type
            + " val) {"
        )
        self._helper_lines.append("    if (arr->size >= arr->capacity) {")
        self._helper_lines.append("        arr->capacity *= 2;")
        self._helper_lines.append(
            f"        arr->data = __ctri_realloc(arr->data, arr->capacity * sizeof({elem_type}));"
        )
        self._helper_lines.append("    }")
        self._helper_lines.append("    arr->data[arr->size++] = val;")
        self._helper_lines.append("}")
        self._helper_lines.append("")

        # Generate pop function
        self._helper_lines.append(
            elem_type + " " + struct_name + "_pop(" + struct_name + "* arr) {"
        )
        self._helper_lines.append("    return arr->data[--arr->size];")
        self._helper_lines.append("}")
        self._helper_lines.append("")

        # Generate len function
        self._helper_lines.append(
            "int " + struct_name + "_len(" + struct_name + "* arr) {"
        )
        self._helper_lines.append("    return arr->size;")
        self._helper_lines.append("}")
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
                            self._emit(f"__ctri_free({var_name}.data);")
                            init_capacity = max(4, len(init_vals))
                            self._emit(
                                f"{var_name}.data = __ctri_malloc({init_capacity} * sizeof({mapped_elem}));"
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
                            self._ensure_ctri_string_helpers()
                            self._emit(f"__ctri_free({var_name});")
                            self._emit(f"{var_name} = __ctri_strdup({value.value});")
                            return
                        elif isinstance(value, Binary) and value.op == "+":
                            self._ensure_ctri_string_helpers()
                            right = self._expr(value.right)
                            self._emit(
                                f"{var_name} = __ctri_realloc({var_name}, __ctri_strlen({var_name}) + __ctri_strlen({right}) + 1);"
                            )
                            self._emit(f"__ctri_strcat({var_name}, {right});")
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
        """Generate C declaration stub for asm block and store for .asm file generation."""
        if node.is_function:
            self._asm_blocks.append(node)
            self._asm_function_names.add(node.name)
            ret_type = self._map_type(node.ret_type)
            params = []
            for ptype, pname in node.params:
                mapped_type = self._map_type(ptype)
                params.append(f"{mapped_type} {pname}")
            param_str = ", ".join(params) if params else "void"
            # On macOS, asm functions need _ prefix for C linkage
            is_macos = platform.system() == "Darwin"
            func_name = f"_{node.name}" if is_macos else node.name
            self._emit(f"{ret_type} {func_name}({param_str});")
            self._gen_asm_variable_externs(node)
        else:
            self._asm_blocks.append(node)
            self._gen_asm_variable_externs(node)
            if not node.variables:
                self._emit("/* bare asm block */")

    def _gen_asm_variable_externs(self, node):
        """Emit C extern declarations for variables owned by an asm block."""
        for var_info in node.variables:
            var_name = var_info["name"]
            var_type = var_info["type"]
            var_size = var_info.get("size")
            self._asm_function_names.add(var_name)
            if var_type == "string":
                initializer = var_info.get("initializer", "")
                str_size = len(initializer) + 1 if isinstance(initializer, str) else 0
                self._emit(f"extern char {var_name}[{str_size}];")
            elif var_size:
                c_type = self._map_type(var_type)
                self._emit(f"extern {c_type} {var_name}[{var_size}];")
            else:
                c_type = self._map_type(var_type)
                self._emit(f"extern {c_type} {var_name};")

    def _gen_alloc(self, node: Alloc):
        mapped_type = self._map_type(node.alloc_type)
        if node.count is not None:
            self._ensure_ctri_allocator_helpers()
            count_expr = self._expr(node.count)
            self._emit(
                f"{mapped_type}* {node.name} = ({mapped_type}*)__ctri_malloc({count_expr} * sizeof({mapped_type}));"
            )
        elif node.byte_size is not None:
            self._ensure_ctri_allocator_helpers()
            size_expr = self._expr(node.byte_size)
            self._validate_byte_sized_initializer(node)
            self._emit(
                f"{mapped_type}* {node.name} = ({mapped_type}*)__ctri_malloc({size_expr});"
            )
            if node.initializer:
                init_expr = self._expr(node.initializer)
                self._emit(f"*{node.name} = {init_expr};")
        else:
            self._ensure_ctri_allocator_helpers()
            self._emit(
                f"{mapped_type}* {node.name} = ({mapped_type}*)__ctri_malloc(sizeof({mapped_type}));"
            )
            if node.initializer:
                init_expr = self._expr(node.initializer)
                self._emit(f"*{node.name} = {init_expr};")

    def _gen_free(self, node: Free):
        self._ensure_ctri_allocator_helpers()
        expr = self._expr(node.expr)
        self._emit(f"__ctri_free({expr});")

    def _validate_byte_sized_initializer(self, node: Alloc):
        """Validate literal initializers for byte-sized scalar allocations."""
        scalar_types = {
            "char",
            "short",
            "int",
            "long",
            "signed",
            "unsigned",
            "float",
            "double",
        }
        if node.alloc_type not in scalar_types or node.initializer is None:
            return
        if not isinstance(node.byte_size, Literal) or not isinstance(node.initializer, Literal):
            return

        try:
            byte_size = int(node.byte_size.value)
        except (TypeError, ValueError):
            return

        if byte_size <= 0:
            raise SyntaxError(f"allocate {node.alloc_type} {node.name} byte size must be positive")

        if node.alloc_type in ("float", "double"):
            self._validate_float_allocation_initializer(node, byte_size)
            return

        value = self._parse_integer_initializer(node.initializer.value)
        if value is None:
            return

        native_min, native_max = self._native_integer_range(node.alloc_type)
        type_label = f"native C {node.alloc_type} range"
        if value < native_min or value > native_max:
            raise SyntaxError(
                f"initializer {value} for allocate {node.alloc_type} {node.name} exceeds {type_label} "
                f"({native_min}..{native_max})"
            )

        bit_count = byte_size * 8
        if node.alloc_type == "unsigned":
            byte_min = 0
            byte_max = (2 ** bit_count) - 1
        else:
            byte_min = -(2 ** (bit_count - 1))
            byte_max = (2 ** (bit_count - 1)) - 1
        if value < byte_min or value > byte_max:
            raise SyntaxError(
                f"initializer {value} for allocate {node.alloc_type} {node.name} exceeds "
                f"{byte_size}-byte {node.alloc_type} range "
                f"({byte_min}..{byte_max})"
            )

    def _validate_float_allocation_initializer(self, node: Alloc, byte_size: int):
        native_size = 4 if node.alloc_type == "float" else 8
        if byte_size < native_size:
            raise SyntaxError(
                f"allocate {node.alloc_type} {node.name} byte size {byte_size} is smaller than "
                f"native C {node.alloc_type} size {native_size}"
            )

        raw_value = str(node.initializer.value).rstrip("fFlL")
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return

        native_max = 3.4028235e38 if node.alloc_type == "float" else 1.7976931348623157e308
        if value < -native_max or value > native_max:
            raise SyntaxError(
                f"initializer {node.initializer.value} for allocate {node.alloc_type} {node.name} "
                f"exceeds native C {node.alloc_type} range ({-native_max}..{native_max})"
            )

    def _parse_integer_initializer(self, raw_value):
        raw = str(raw_value)
        if raw.startswith("'") and raw.endswith("'"):
            inner = raw[1:-1]
            if len(inner) == 1:
                return ord(inner)
            escapes = {"\\0": 0, "\\n": 10, "\\r": 13, "\\t": 9}
            return escapes.get(inner)

        stripped = raw.rstrip("uUlL")
        try:
            return int(stripped, 0)
        except ValueError:
            return None

    def _native_integer_range(self, type_name: str):
        ranges = {
            "char": (-(2 ** 7), (2 ** 7) - 1),
            "short": (-(2 ** 15), (2 ** 15) - 1),
            "int": (-(2 ** 31), (2 ** 31) - 1),
            "signed": (-(2 ** 31), (2 ** 31) - 1),
            "unsigned": (0, (2 ** 32) - 1),
            "long": (-(2 ** 63), (2 ** 63) - 1),
        }
        return ranges[type_name]
