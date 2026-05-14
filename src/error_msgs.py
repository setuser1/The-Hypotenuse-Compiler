"""Error messages for the C△ compiler.

Error codes are organized by category:
- E0xx: Syntax errors
- E1xx: Type errors
- E2xx: Include/Import errors
- E3xx: Function call errors
- E4xx: Return statement errors
- E5xx: Struct/type errors
- E6xx: Parse errors
- E7xx: ASM/Array errors
- E8xx: Import/Library errors
- E9xx: General/Internal errors
"""

import os

_ERRORS: dict[str, list[str]] = {}
_ERROR_CATEGORIES = {
    "SYNTAX": "Syntax errors (E0xx)",
    "TYPE": "Type errors (E1xx)",
    "INCLUDE": "Include errors (E2xx)",
    "CALL": "Function call errors (E3xx)",
    "RETURN": "Return statement errors (E4xx)",
    "STRUCT": "Struct/type errors (E5xx)",
    "PARSE": "Parse errors (E6xx)",
    "ASM": "Assembly block errors (E7xx)",
    "ARRAY": "Array errors (E7xx)",
    "IMPORT": "Import/library errors (E8xx)",
    "GENERAL": "General errors (E9xx)",
}

ERROR_MESSAGES = {
    # =========================================================================
    # SYNTAX (E0xx)
    # =========================================================================
    "E001": [
        "Unexpected token {found} at {line}:{col}",
        "Found {found} but expected {expected}",
        "Syntax error: unexpected {found}",
    ],
    "E002": [
        "Missing semicolon after {statement} at {line}:{col}",
        "Syntax error: expected ';' before {found}",
    ],
    "E003": [
        "Invalid expression syntax near {found}",
        "Expression expected, found {found}",
    ],
    "E004": [
        "Invalid statement syntax: {found}",
        "Malformed statement near {found}",
    ],
    "E005": [
        "Unmatched parenthesis in expression at {line}:{col}",
        "Extra closing parenthesis found",
    ],
    "E006": [
        "Missing closing brace at {line}:{col}",
        "Expected '}' after {statement}",
    ],
    "E007": [
        "Invalid token {found} in declaration",
        "Cannot start declaration with {found}",
    ],
    "E008": [
        "Missing identifier after {keyword} at {line}:{col}",
        "Expected identifier, found {found}",
    ],
    # =========================================================================
    # TYPE (E1xx)
    # =========================================================================
    "E101": [
        "Type mismatch: cannot convert {type1} to {type2}",
        "Cannot assign {type1} value to variable of type {type2}",
        "Operand of type {type1} cannot be used with {type2}",
    ],
    "E102": [
        "Invalid type {type} in this context",
        "Unknown type {type} at {line}:{col}",
    ],
    "E103": [
        "sizeof cannot be applied to type {type}",
        "Invalid operand for sizeof: {type}",
    ],
    "E104": [
        "Cannot cast {type1} to {type2}",
        "Invalid type cast from {type1} to {type2}",
    ],
    "E105": [
        "Arithmetic operands must have numeric types, found {type}",
        "Invalid operands for binary operator: {type1} and {type2}",
    ],
    "E106": [
        "Logical operands must have scalar types, found {type}",
    ],
    "E107": [
        "Operand of type {type} cannot be used as boolean",
    ],
    # =========================================================================
    # INCLUDE (E2xx)
    # =========================================================================
    "E201": [
        "Include file not found: {file}",
        "Cannot open include file '{file}'",
    ],
    "E202": [
        "Invalid include path: {path}",
        "Malformed include directive at {line}:{col}",
    ],
    "E203": [
        "System include not found: {file}",
        "Header file {file} not found in system directories",
    ],
    "E204": [
        "Circular include detected: {file}",
        "Include nesting too deep in {file}",
    ],
    # =========================================================================
    # CALL (E3xx)
    # =========================================================================
    "E301": [
        "Too few arguments to function {name}: expected {expected}, got {count}",
        "Missing argument {count} for parameter {expected} in {name}",
    ],
    "E302": [
        "Too many arguments to function {name}: expected {expected}, got {count}",
        "Excess arguments passed to {name}, expected {expected}",
    ],
    "E303": [
        "Argument {count} type mismatch in call to {name}: expected {expected}, got {type}",
        "Type error: argument {count} of {name} expects {expected}, found {type}",
    ],
    "E304": [
        "Unknown function {name} at {line}:{col}",
        "Function {name} is not defined",
    ],
    "E305": [
        "Cannot call non-function {name}",
        "Variable {name} is not callable",
    ],
    # =========================================================================
    # RETURN (E4xx)
    # =========================================================================
    "E401": [
        "Missing return statement in non-void function {name}",
        "Control reaches end of function {name} without returning a value",
    ],
    "E402": [
        "Invalid return type: expected {expected}, got {type}",
        "Return type mismatch in function {name}: cannot return {type}",
    ],
    "E403": [
        "Return statement in void function {name}",
        "Void function {name} cannot return a value",
    ],
    "E404": [
        "Return outside of function context",
    ],
    "E405": [
        "Expected expression in return statement",
    ],
    # =========================================================================
    # STRUCT (E5xx)
    # =========================================================================
    "E501": [
        "Unknown struct name {name} at {line}:{col}",
        "Struct {name} is not defined",
    ],
    "E502": [
        "Invalid field access on type {type}",
        "Cannot access field {field} of non-struct type {type}",
    ],
    "E503": [
        "Struct {name} redefinition at {line}:{col}",
        "Multiple definition of struct {name}",
    ],
    "E504": [
        "Invalid struct initialization for type {type}",
        "Cannot initialize struct {name} with these values",
    ],
    "E505": [
        "Field {field} not found in struct {name}",
        "Struct {name} has no member named {field}",
    ],
    # =========================================================================
    # PARSE (E6xx)
    # =========================================================================
    "E601": [
        "Parse failure at token {found} on line {line}",
        "Failed to parse {found} at {line}:{col}",
    ],
    "E602": [
        "Unexpected end of input",
        "Unexpected end of file in {file}",
    ],
    "E603": [
        "Invalid declaration near {found}",
        "Malformed declaration: {found}",
    ],
    "E604": [
        "Expected {expected} at {line}:{col}, found {found}",
        "Garbage at end of input: {found}",
    ],
    "E605": [
        "Cannot parse expression starting with {found}",
    ],
    "E606": [
        "Missing token {expected} after {found}",
    ],
    # =========================================================================
    # ASM (E7xx)
    # =========================================================================
    "E701": [
        "Invalid asm syntax near {found}",
        "Malformed assembly block at {line}:{col}",
    ],
    "E702": [
        "Unknown syntax in asm block: {found}",
        "Invalid assembly instruction: {found}",
    ],
    "E703": [
        "Unclosed asm block: missing closing '}'",
        "Assembly block started at {line} is never closed",
    ],
    "E704": [
        "Invalid operand in asm: {found}",
        "Assembly constraint {found} is not supported",
    ],
    "E705": [
        "Empty asm block at {line}:{col}",
    ],
    # =========================================================================
    # ARRAY (E7xx)
    # =========================================================================
    "E751": [
        "Cannot infer dimension {dim} for array '{name}'",
        "Provide explicit size or ensure initializer has values at this level",
    ],
    "E752": [
        "Invalid array dimension: {dim} for array '{name}'",
        "Array dimension must be a positive integer constant",
    ],
    # =========================================================================
    # IMPORT (E8xx)
    # =========================================================================
    "E801": [
        "Library {lib} must be imported before exposing. "
        "Use: using <{lib}> or using {item} from <{lib}>",
    ],
    "E802": [
        "Library {lib} is not exposed. Use 'expose {lib}' before calling functions directly.",
        "Function {func} requires 'expose {lib}' before direct calls.",
    ],
    "E803": [
        "Function {func} not found in library {lib}",
        "Library {lib} does not export function {func}",
    ],
    "E804": [
        "Invalid alias '{alias}'. Library not imported or does not exist.",
    ],
    "E805": [
        "Multiple @ signs not allowed in '{func}'. Use 'func@lib()' for library functions.",
        "Invalid call syntax for {func}. Use '{func}()' directly or '{func}@lib()' for library functions.",
        "Malformed '@' syntax in '{callee}'. Expected format: function@library",
    ],
    "E806": [
        "Library not found: {lib}",
        "Cannot find plib for library {lib}",
    ],
    "E807": [
        "Cannot import library {lib} - plib file not found in search paths",
    ],
    # =========================================================================
    # GENERAL (E9xx)
    # =========================================================================
    "E901": [
        "Internal compiler error at {line}:{col}",
        "Compiler bug detected while processing {file}",
    ],
    "E902": [
        "Compilation failed due to errors",
        "Build failed with {count} error(s)",
    ],
    "E903": [
        "Unexpected error occurred: {message}",
        "An error occurred while processing {name}: {message}",
    ],
    "E904": [
        "Cannot open file {file} for reading",
        "File {file} does not exist or is not accessible",
    ],
    "E905": [
        "Out of memory during compilation",
        "Memory allocation failed at {line}:{col}",
    ],
}


def _load_errors():
    """Load errors from errors.txt if present (dev mode) or use embedded."""
    global _ERRORS
    if _ERRORS is not None:
        return
    _ERRORS = {}
    for code, messages in ERROR_MESSAGES.items():
        _ERRORS[code] = messages.copy()

    path = os.path.join(os.path.dirname(__file__), "errors.txt")
    if os.path.exists(path):
        current_category = None
        with open(path) as fp:
            for line in fp:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    current_category = line[1:-1]
                    continue
                if "|" in line and current_category:
                    code, msg = line.split("|", 1)
                    code = code.strip()
                    if code not in _ERRORS:
                        _ERRORS[code] = []
                    _ERRORS[code].append(msg.strip())


def get_error_msg(code: str, fallback: str | None = None, **kwargs) -> str:
    """Get an error message for code, format with kwargs.

    Args:
        code: Error code (e.g., "E001")
        fallback: Fallback message if code not found
        **kwargs: Format arguments for the message template

    Returns:
        Formatted error message string
    """
    _load_errors()
    messages = _ERRORS.get(code, [])
    if not messages:
        return fallback or f"Unknown error: {code}"
    msg = messages[0]
    try:
        return msg.format(**kwargs)
    except KeyError:
        return msg


def get_random_error_msg(code: str, fallback: str | None = None, **kwargs) -> str:
    """Get a random error message for code, format with kwargs.

    Args:
        code: Error code (e.g., "E001")
        fallback: Fallback message if code not found
        **kwargs: Format arguments for the message template

    Returns:
        Formatted error message string (randomly selected)
    """
    import random

    _load_errors()
    messages = _ERRORS.get(code, [])
    if not messages:
        return fallback or f"Unknown error: {code}"
    msg = random.choice(messages)
    try:
        return msg.format(**kwargs)
    except KeyError:
        return msg


def has_error_code(code: str) -> bool:
    """Check if error code exists."""
    _load_errors()
    return code in _ERRORS


def list_error_codes() -> list:
    """Get sorted list of all error codes."""
    _load_errors()
    return sorted(_ERRORS.keys())


def get_errors_by_prefix(prefix: str) -> dict:
    """Get all error codes matching a prefix (e.g., 'E8' for IMPORT errors)."""
    _load_errors()
    return {k: v for k, v in _ERRORS.items() if k.startswith(prefix)}


def get_category_for_code(code: str) -> str:
    """Get the category name for an error code."""
    if code.startswith("E0"):
        return "SYNTAX"
    elif code.startswith("E1"):
        return "TYPE"
    elif code.startswith("E2"):
        return "INCLUDE"
    elif code.startswith("E3"):
        return "CALL"
    elif code.startswith("E4"):
        return "RETURN"
    elif code.startswith("E5"):
        return "STRUCT"
    elif code.startswith("E6"):
        return "PARSE"
    elif code.startswith("E70") or code.startswith("E71"):
        return "ASM"
    elif code.startswith("E75"):
        return "ARRAY"
    elif code.startswith("E8"):
        return "IMPORT"
    elif code.startswith("E9"):
        return "GENERAL"
    return "UNKNOWN"
