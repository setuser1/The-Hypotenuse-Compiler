"""Auto-generated error messages from errors.txt."""

import os
import random

_ERRORS = None

ERROR_MESSAGES = {
    "E001": [
        'Unexpected token {found} at {line}:{col}',
        'Found {found} but expected {expected}',
        'Syntax error: unexpected {found}',
    ],
    "E002": [
        'Missing semicolon after {statement} at {line}:{col}. PUT THE DAMN SEMICOLON!',
        "Syntax error: expected ';' before {found} -- we serious right?",
    ],
    "E003": [
        'Invalid expression syntax near {found}, try again buddy.',
        'Expression expected, found {found}, DO BETTER.',
    ],
    "E004": [
        'Invalid statement syntax: {found}; programmers like you need to die.',
        'Malformed statement near {found}, maybe you just suck.',
    ],
    "E005": [
        'Unmatched parenthesis in expression at {line}:{col}, try putting them there next time.',
        'Extra closing parenthesis found',
    ],
    "E006": [
        'Missing closing brace at {line}:{col}',
        "Expected '}' after {statement}",
    ],
    "E007": [
        'Invalid token {found} in declaration',
        'Cannot start declaration with {found}',
    ],
    "E008": [
        'Missing identifier after {keyword} at {line}:{col}',
        'Expected identifier, found {found}',
    ],
    "E101": [
        'Type mismatch: cannot convert {type1} to {type2}',
        'Cannot assign {type1} value to variable of type {type2}',
        'Operand of type {type1} cannot be used with {type2}',
    ],
    "E102": [
        'Invalid type {type} in this context',
        'Unknown type {type} at {line}:{col}',
    ],
    "E103": [
        'sizeof cannot be applied to type {type}',
        'Invalid operand for sizeof: {type}',
    ],
    "E104": [
        'Cannot cast {type1} to {type2}',
        'Invalid type cast from {type1} to {type2}',
    ],
    "E105": [
        'Arithmetic operands must have numeric types, found {type}',
        'Invalid operands for binary operator: {type1} and {type2}',
    ],
    "E106": [
        'Logical operands must have scalar types, found {type}',
    ],
    "E107": [
        'Operand of type {type} cannot be used as boolean',
    ],
    "E201": [
        'Include file not found: {file}',
        "Cannot open include file '{file}'",
    ],
    "E202": [
        'Invalid include path: {path}',
        'Malformed include directive at {line}:{col}',
    ],
    "E203": [
        'System include not found: {file}',
        'Header file {file} not found in system directories',
    ],
    "E204": [
        'Circular include detected: {file}',
        'Include nesting too deep in {file}',
    ],
    "E301": [
        'Too few arguments to function {name}: expected {expected}, got {count}',
        'Missing argument {count} for parameter {expected} in {name}',
    ],
    "E302": [
        'Too many arguments to function {name}: expected {expected}, got {count}',
        'Excess arguments passed to {name}, expected {expected}',
    ],
    "E303": [
        'Argument {count} type mismatch in call to {name}: expected {expected}, got {type}',
        'Type error: argument {count} of {name} expects {expected}, found {type}',
    ],
    "E304": [
        'Unknown function {name} at {line}:{col}',
        'Function {name} is not defined',
    ],
    "E305": [
        'Cannot call non-function {name}',
        'Variable {name} is not callable',
    ],
    "E401": [
        'Missing return statement in non-void function {name}',
        'Control reaches end of function {name} without returning a value',
    ],
    "E402": [
        'Invalid return type: expected {expected}, got {type}',
        'Return type mismatch in function {name}: cannot return {type}',
    ],
    "E403": [
        'Return statement in void function {name}',
        'Void function {name} cannot return a value',
    ],
    "E404": [
        'Return outside of function context',
    ],
    "E405": [
        'Expected expression in return statement',
    ],
    "E501": [
        'Unknown struct name {name} at {line}:{col}',
        'Struct {name} is not defined',
    ],
    "E502": [
        'Invalid field access on type {type}',
        'Cannot access field {field} of non-struct type {type}',
    ],
    "E503": [
        'Struct {name} redefinition at {line}:{col}',
        'Multiple definition of struct {name}',
    ],
    "E504": [
        'Invalid struct initialization for type {type}',
        'Cannot initialize struct {name} with these values',
    ],
    "E505": [
        'Field {field} not found in struct {name}',
        'Struct {name} has no member named {field}',
    ],
    "E601": [
        'Parse failure at token {found} on line {line}',
        'Failed to parse {found} at {line}:{col}',
    ],
    "E602": [
        'Unexpected end of input',
        'Unexpected end of file in {file}',
    ],
    "E603": [
        'Invalid declaration near {found}',
        'Malformed declaration: {found}',
    ],
    "E604": [
        'Expected {expected} at {line}:{col}, found {found}',
        'Garbage at end of input: {found}',
    ],
    "E605": [
        'Cannot parse expression starting with {found}',
    ],
    "E606": [
        'Missing token {expected} after {found}',
    ],
    "E701": [
        'Invalid asm syntax near {found}',
        'Malformed assembly block at {line}:{col}',
    ],
    "E702": [
        'Unknown syntax in asm block: {found}',
        'Invalid assembly instruction: {found}',
    ],
    "E703": [
        "Unclosed asm block: missing closing '}'",
        'Assembly block started at {line} is never closed',
    ],
    "E704": [
        'Invalid operand in asm: {found}',
        'Assembly constraint {found} is not supported',
    ],
    "E705": [
        'Empty asm block at {line}:{col}',
    ],
    "E901": [
        'Internal compiler error at {line}:{col}',
        'Compiler bug detected while processing {file}',
    ],
    "E902": [
        'Compilation failed due to errors',
        'Build failed with {count} error(s)',
    ],
    "E903": [
        'Unexpected error occurred: {message}',
        'An error occurred while processing {name}: {message}',
    ],
    "E904": [
        'Cannot open file {file} for reading',
        'File {file} does not exist or is not accessible',
    ],
    "E905": [
        'Out of memory during compilation',
        'Memory allocation failed at {line}:{col}',
    ],
}


def _load_errors():
    """Load errors.txt if present (dev mode) or use embedded."""
    global _ERRORS
    if _ERRORS is not None:
        return
    _ERRORS = ERROR_MESSAGES.copy()
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


def get_error_msg(code: str, fallback: str = None, **kwargs) -> str:
    """Get random error message for code, format with kwargs."""
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
