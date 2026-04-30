"""NASM code generator for C△ compiler asm blocks.

This module generates NASM-compatible assembly files (.s) from AsmBlock AST nodes
and provides shell integration to assemble them with NASM.

Supports:
- x86_64 (System V ABI): params in rdi, rsi, rdx, rcx, r8, r9; return in rax
- Labels and jumps
- Data sections (.data, .rodata, .bss)
"""

import os
import re
import platform
import subprocess
from typing import List, Optional, Tuple

X86_INT_REGS = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
X86_FLOAT_REGS = ["xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7"]
SYS_WRITE_X86 = 1
SYS_READ_X86 = 0
SYS_OPEN_X86 = 2
SYS_CLOSE_X86 = 3
SYS_EXIT_X86 = 60
SYS_WRITE_ARM64_MACOS = 4
SYS_READ_ARM64_MACOS = 3
SYS_OPEN_ARM64_MACOS = 5
SYS_CLOSE_ARM64_MACOS = 6
SYS_EXIT_ARM64_MACOS = 1

def emit_syscall(
    syscall_num: int,
    args: Optional[List[str]] = None,
    is_arm64: bool = False,
    is_macos: bool = False,
):
    """Emit syscall instruction sequence for current architecture."""
    if args is None:
        args = []

    if is_arm64:
        if is_macos:
            lines = [f"mov x16, #{syscall_num}"]
            for i, arg in enumerate(args[:6]):
                lines.append(f"mov x{i}, {arg}")
            lines.append("svc #0x80")
            return lines
        else:
            lines = [f"mov x8, {syscall_num}"]
            for i, arg in enumerate(args[:6]):
                lines.append(f"mov x{i}, {arg}")
            lines.append("svc #0")
            return lines
    else:
        lines = [f"mov rax, {syscall_num}"]
        for i, arg in enumerate(args[:6]):
            reg = X86_INT_REGS[i]
            lines.append(f"mov {reg}, {arg}")
        lines.append("syscall")
        return lines


def get_asm_config(
    asm_block_syntax: Optional[str],
    target_arch: Optional[str] = None,
    output_format: Optional[str] = None,
    is_macos: bool = False,
    current_arch: Optional[str] = None,
):
    """Determine architecture and format for an asm block."""
    is_arm64_current = False
    format_current = "elf64"

    if target_arch == "arm64":
        is_arm64_current = True
        format_current = "macho64" if is_macos else "elf64"
    elif target_arch == "x86_64":
        is_arm64_current = False
        format_current = "macho64" if is_macos else "elf64"

    if output_format == "macho":
        is_arm64_current = True
        format_current = "macho64"
    elif output_format == "elf":
        is_arm64_current = False
        format_current = "elf64"

    if asm_block_syntax:
        syntax = asm_block_syntax.lower()
        if "arm64" in syntax:
            is_arm64_current = True
            if "macho" in syntax:
                format_current = "macho64"
            else:
                format_current = "elf64"
        elif "x86_64" in syntax:
            is_arm64_current = False
            if "macho" in syntax:
                format_current = "macho64"
            else:
                format_current = "elf64"

    if not target_arch and not output_format and not asm_block_syntax:
        if is_macos:
            if current_arch == "arm64":
                is_arm64_current = True
                format_current = "macho64"
            else:
                is_arm64_current = False
                format_current = "macho64"
        else:
            is_arm64_current = False
            format_current = "elf64"

    return is_arm64_current, format_current


def _escape_string(value: str) -> str:
    """Escape a string for assembly."""
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace('"', '\\"')
    )


def _expand_write_call(instr: str, is_arm64: bool) -> List[str]:
    """Replace _write calls with pure syscalls."""
    stripped = instr.strip()
    if "bl" in stripped.lower() and "_write" in stripped:
        if is_arm64:
            return ["mov x16, #4", "svc #0x80"]
        else:
            return ["mov rax, 1", "syscall"]
    return [instr]


def _expand_len_instruction(instr: str, is_arm64: bool, label_suffix: str = "") -> List[str]:
    """Expand len() into inline assembly.

    Args:
        instr: The instruction string to process
        is_arm64: True for ARM64, False for x86_64
        label_suffix: Optional suffix for labels to make them unique
    """
    match = re.match(r"^\s*mov\s+([^,]+),\s*len\(([^)]+)\)\s*$", instr)
    if not match:
        return [instr]

    dest = match.group(1).strip()
    src = match.group(2).strip()

    if label_suffix:
        loop_label = f".Lhyp_len_loop_{label_suffix}" if is_arm64 else f".hyp_len_loop_{label_suffix}"
        done_label = f".Lhyp_len_done_{label_suffix}" if is_arm64 else f".hyp_len_done_{label_suffix}"
    else:
        loop_label = ".Lhyp_len_loop" if is_arm64 else ".hyp_len_loop"
        done_label = ".Lhyp_len_done" if is_arm64 else ".hyp_len_done"

    if is_arm64:
        return [
            f"mov x10, {src}",
            f"mov {dest}, #0",
            f"{loop_label}:",
            f"ldrb w11, [x10, {dest}]",
            f"cbz w11, {done_label}",
            f"add {dest}, {dest}, #1",
            f"b {loop_label}",
            f"{done_label}:",
        ]
    else:
        return [
            f"mov r10, {src}",
            f"xor {dest}, {dest}",
            f"{loop_label}:",
            f"cmp byte [r10 + {dest}], 0",
            f"je {done_label}",
            f"inc {dest}",
            f"jmp {loop_label}",
            f"{done_label}:",
        ]


def _split_binary_expr(expr: str):
    parts = expr.split()
    if len(parts) == 3 and parts[1] in ("+", "-", "*", "/", "%"):
        return parts[0], parts[1], parts[2]
    return None


def _emit_integer_expr_x86(f, expr: str, dst: str):
    binary = _split_binary_expr(expr)
    if not binary:
        f.write(f"    mov {dst}, {expr}\n")
        return
    left, op, right = binary
    f.write(f"    mov {dst}, {left}\n")
    if op == "+":
        f.write(f"    add {dst}, {right}\n")
    elif op == "-":
        f.write(f"    sub {dst}, {right}\n")
    elif op == "*":
        f.write(f"    imul {dst}, {right}\n")
    elif op in ("/", "%"):
        f.write("    cqo\n")
        f.write(f"    mov r10, {right}\n")
        f.write("    idiv r10\n")
        if op == "%":
            f.write(f"    mov {dst}, rdx\n")


def _emit_integer_expr_arm64(f, expr: str, dst: str):
    binary = _split_binary_expr(expr)
    if not binary:
        f.write(f"    mov {dst}, {expr}\n")
        return
    left, op, right = binary
    f.write(f"    mov {dst}, {left}\n")
    if op == "+":
        f.write(f"    add {dst}, {dst}, {right}\n")
    elif op == "-":
        f.write(f"    sub {dst}, {dst}, {right}\n")
    elif op == "*":
        f.write(f"    mul {dst}, {dst}, {right}\n")
    elif op in ("/", "%"):
        f.write(f"    sdiv x9, {dst}, {right}\n")
        if op == "/":
            f.write(f"    mov {dst}, x9\n")
        else:
            f.write(f"    msub {dst}, x9, {right}, {dst}\n")


def _emit_return_expr(f, return_expr, ret_type, is_arm64: bool):
    """Emit instructions that place a simple return expression in the ABI register."""
    if return_expr is None or return_expr == "":
        return
    if ret_type in ("float", "double"):
        dst = "v0" if is_arm64 else "xmm0"
        op = "fmov" if is_arm64 else "movq"
        f.write(f"    {op} {dst}, {return_expr}\n")
        return
    if is_arm64:
        _emit_integer_expr_arm64(f, return_expr, "x0")
    else:
        _emit_integer_expr_x86(f, return_expr, "rax")


def _build_param_map(
    params: List[Tuple[str, str]],
    int_regs: List[str],
    float_regs: List[str],
    is_arm64: bool,
):
    """Build parameter to register mapping based on ABI."""
    param_map = {}
    int_idx = 0
    float_idx = 0
    offset = 8 if not is_arm64 else 0

    for param_type, param_name in params:
        if param_type in ("float", "double"):
            if float_idx < len(float_regs):
                param_map[param_name] = float_regs[float_idx]
                float_idx += 1
            else:
                if is_arm64:
                    param_map[param_name] = f"[sp, #{offset}]"
                else:
                    param_map[param_name] = f"[rbp-{offset}]"
                offset += 8
        else:
            if int_idx < len(int_regs):
                param_map[param_name] = int_regs[int_idx]
                int_idx += 1
            else:
                if is_arm64:
                    param_map[param_name] = f"[sp, #{offset}]"
                else:
                    param_map[param_name] = f"[rbp-{offset}]"
                offset += 8

    return param_map


def _process_instructions(
    instructions: List[str], param_map: dict, is_arm64: bool,
):
    """Process instructions, replacing parameter names with registers."""
    updated = []
    for instr in instructions:
        result = instr
        for param_name, addr in param_map.items():
            pattern = r"\b" + re.escape(param_name) + r"\b"
            result = re.sub(pattern, addr, result)
        updated.append(result)
    return updated


PLATFORM = platform.system()
IS_MACOS = PLATFORM == "Darwin"
IS_LINUX = PLATFORM == "Linux"

X86_INT_REGS = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
X86_FLOAT_REGS = ["xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7"]


def get_asm_config(syntax: Optional[str]) -> Tuple[bool, str]:
    """Determine architecture and format for an asm block.

    NASM only supports x86_64, so is_arm64 is always False.
    """
    is_arm64 = False
    if IS_MACOS:
        format_str = "macho64"
    else:
        format_str = "elf64"

    if syntax:
        syntax_lower = syntax.lower()
        if "macho" in syntax_lower:
            format_str = "macho64"
        elif "elf" in syntax_lower:
            format_str = "elf64"

    return is_arm64, format_str


def _escape_string(value: str) -> str:
    """Escape a string for assembly."""
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace('"', '\\"')
    )


def _expand_write_call(instr: str, is_arm64: bool) -> List[str]:
    """Replace _write calls with pure syscalls."""
    stripped = instr.strip()
    if "bl" in stripped.lower() and "_write" in stripped:
        if is_arm64:
            return ["mov x16, #4", "svc #0x80"]
        else:
            return ["mov rax, 1", "syscall"]
    return [instr]


def _expand_len_instruction(instr: str, is_arm64: bool, label_suffix: str = "") -> List[str]:
    """Expand len() into inline assembly.

    Args:
        instr: The instruction string to process
        is_arm64: True for ARM64, False for x86_64
        label_suffix: Optional suffix for labels to make them unique
    """
    match = re.match(r"^\s*mov\s+([^,]+),\s*len\(([^)]+)\)\s*$", instr)
    if not match:
        return [instr]

    dest = match.group(1).strip()
    src = match.group(2).strip()

    if label_suffix:
        loop_label = f".Lhyp_len_loop_{label_suffix}" if is_arm64 else f".hyp_len_loop_{label_suffix}"
        done_label = f".Lhyp_len_done_{label_suffix}" if is_arm64 else f".hyp_len_done_{label_suffix}"
    else:
        loop_label = ".Lhyp_len_loop" if is_arm64 else ".hyp_len_loop"
        done_label = ".Lhyp_len_done" if is_arm64 else ".hyp_len_done"

    if is_arm64:
        return [
            f"mov x10, {src}",
            f"mov {dest}, #0",
            f"{loop_label}:",
            f"ldrb w11, [x10, {dest}]",
            f"cbz w11, {done_label}",
            f"add {dest}, {dest}, #1",
            f"b {loop_label}",
            f"{done_label}:",
        ]
    else:
        return [
            f"mov r10, {src}",
            f"xor {dest}, {dest}",
            f"{loop_label}:",
            f"cmp byte [r10 + {dest}], 0",
            f"je {done_label}",
            f"inc {dest}",
            f"jmp {loop_label}",
            f"{done_label}:",
        ]


def _split_binary_expr(expr: str):
    parts = expr.split()
    if len(parts) == 3 and parts[1] in ("+", "-", "*", "/", "%"):
        return parts[0], parts[1], parts[2]
    return None


def _emit_integer_expr_x86(f, expr: str, dst: str):
    binary = _split_binary_expr(expr)
    if not binary:
        f.write(f"    mov {dst}, {expr}\n")
        return
    left, op, right = binary
    f.write(f"    mov {dst}, {left}\n")
    if op == "+":
        f.write(f"    add {dst}, {right}\n")
    elif op == "-":
        f.write(f"    sub {dst}, {right}\n")
    elif op == "*":
        f.write(f"    imul {dst}, {right}\n")
    elif op in ("/", "%"):
        f.write("    cqo\n")
        f.write(f"    mov r10, {right}\n")
        f.write("    idiv r10\n")
        if op == "%":
            f.write(f"    mov {dst}, rdx\n")


def _emit_return_expr(f, return_expr, ret_type):
    """Emit instructions that place a simple return expression in the ABI register."""
    if return_expr is None or return_expr == "":
        return
    if ret_type in ("float", "double"):
        f.write(f"    movq xmm0, {return_expr}\n")
        return
    _emit_integer_expr_x86(f, return_expr, "rax")


def _build_param_map(
    params: List[Tuple[str, str]],
    int_regs: List[str],
    float_regs: List[str],
    is_arm64: bool,
) -> dict:
    """Build parameter to register mapping based on ABI."""
    param_map = {}
    int_idx = 0
    float_idx = 0
    offset = 8 if not is_arm64 else 0

    for param_type, param_name in params:
        if param_type in ("float", "double"):
            if float_idx < len(float_regs):
                param_map[param_name] = float_regs[float_idx]
                float_idx += 1
            else:
                if is_arm64:
                    param_map[param_name] = f"[sp, #{offset}]"
                else:
                    param_map[param_name] = f"[rbp-{offset}]"
                offset += 8
        else:
            if int_idx < len(int_regs):
                param_map[param_name] = int_regs[int_idx]
                int_idx += 1
            else:
                if is_arm64:
                    param_map[param_name] = f"[sp, #{offset}]"
                else:
                    param_map[param_name] = f"[rbp-{offset}]"
                offset += 8

    return param_map


def _process_instructions(
    instructions: List[str], param_map: dict, is_arm64: bool
) -> List[str]:
    """Process instructions, replacing parameter names with registers."""
    updated = []
    for instr in instructions:
        result = instr
        for param_name, addr in param_map.items():
            pattern = r"\b" + re.escape(param_name) + r"\b"
            result = re.sub(pattern, addr, result)
        updated.append(result)
    return updated


def generate_nasm_file(
    asm_block, output_path: str, is_arm64: bool = False, format_str: str = "elf64"
):
    """Generate a NASM-compatible .s file from an AsmBlock node.

    Args:
        asm_block: AsmBlock AST node
        output_path: Path to write the .s file
        is_arm64: True for ARM64, False for x86_64 (ignored - NASM is x86 only)
        format_str: Object format ('macho64' or 'elf64')
    """
    is_macos = IS_MACOS and format_str == "macho64"
    symbol_prefix = "_" if is_macos else ""

    with open(output_path, "w") as f:
        f.write("; Generated by Hypotenuse Compiler\n")
        f.write(f"; Target: x86_64 format: {format_str}\n\n")

        _generate_x86_asm(asm_block, f, symbol_prefix, is_macos)


def _generate_x86_asm(asm_block, f, symbol_prefix: str, is_macos: bool = False):
    """Generate x86_64 NASM assembly."""
    directives = []
    instructions = []

    for line in asm_block.lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("syntax"):
            continue
        # Labels end with : and are not directives
        if stripped.endswith(":"):
            instructions.append(stripped)
        elif (
            "section" in stripped
            or stripped.startswith(".")
            or stripped.startswith("global")
        ):
            directives.append(stripped)
        else:
            instructions.append(stripped)

    param_map = _build_param_map(
        asm_block.params, X86_INT_REGS, X86_FLOAT_REGS, is_arm64=False
    )

    updated_instructions = _process_instructions(
        instructions, param_map, is_arm64=False
    )

    data_lines = _build_data_section(asm_block.variables, symbol_prefix)
    if data_lines:
        f.write("section .data\n")
        for dl in data_lines:
            f.write(f"{dl}\n")
        f.write("\n")

    has_text_section = any(".text" in d or "section" in d for d in directives)
    if not has_text_section:
        f.write("section .text\n")

    for d in directives:
        if ".data" not in d.lower():
            f.write(f"{d}\n")

    if asm_block.is_function and asm_block.name:
        global_name = f"{symbol_prefix}{asm_block.name}"
        f.write(f"global {global_name}\n")
        f.write(f"{global_name}:\n")

        f.write("    push rbp\n")
        f.write("    mov rbp, rsp\n")

        for param_type, param_name in asm_block.params:
            if param_type in ("float", "double"):
                reg = param_map.get(param_name, "")
                if reg.startswith("xmm"):
                    f.write("    sub rsp, 8\n")
                    f.write(f"    movsd [rsp], {reg}\n")

        for instr in updated_instructions:
            instr_lower = instr.strip().lower()
            if instr_lower == "ret":
                continue
            f.write(f"    {instr}\n")

        _emit_return_expr(f, asm_block.return_expr, asm_block.ret_type, is_arm64=False)

        f.write("    pop rbp\n")
        f.write("    ret\n")
    else:
        for instr in updated_instructions:
            f.write(f"{instr}\n")
        if asm_block.return_expr is not None:
            _emit_return_expr(f, asm_block.return_expr, asm_block.ret_type, is_arm64=False)
            f.write("    ret\n")


def _build_data_section(
    variables: List[dict], symbol_prefix: str
) -> List[str]:
    """Build data section lines for variables."""
    lines = []
    if not variables:
        return lines

    for var_info in variables:
        name = var_info["name"]
        var_type = var_info["type"]
        array_size = var_info.get("size")
        initializer = var_info.get("initializer")

        symbol_name = f"{symbol_prefix}{name}"
        lines.append(f"global {symbol_name}")
        lines.append(f"{symbol_name}:")

        type_to_nasm = {
            "string": "db",
            "char": "db",
            "short": "dw",
            "int": "dd",
            "long": "dd",
            "float": "dd",
            "double": "dq",
        }
        nasm_directive = type_to_nasm.get(var_type, "dd")
        if array_size:
            lines.append(
                f"    times {array_size} {nasm_directive} {initializer or 0}"
            )
        else:
            lines.append(f"    {nasm_directive} {initializer or 0}")

        lines.append("")

    return lines[:-1] if lines else lines


def emit_nasm_file(asm_block, output_path: str, syntax: str) -> str:
    """Emit a NASM-compatible .s file from an AsmBlock node.

    Args:
        asm_block: AsmBlock AST node from parser
        output_path: Path to write the .s file
        syntax: Optional syntax override (e.g., "x86_64_elf")

    Returns:
        The output_path that was written to
    """
    is_arm64, format_str = get_asm_config(syntax)
    generate_nasm_file(asm_block, output_path, is_arm64, format_str)
    return output_path


def assemble_with_nasm(asm_path: str, obj_path: str, format_str: str) -> str:
    """Assemble a .s file with NASM.

    Args:
        asm_path: Path to the .s file
        obj_path: Optional output path for .o file (defaults to same dir with .o extension)
        format_str: Object format ('macho64' or 'elf64'). Auto-detected if not provided.

    Returns:
        Path to the generated object file

    Raises:
        RuntimeError: If NASM is not found or assembly fails
    """
    import shutil

    if not shutil.which("nasm"):
        raise RuntimeError("nasm not found in PATH. Install NASM: brew install nasm")

    if obj_path is None:
        base, _ = os.path.splitext(asm_path)
        obj_path = base + ".o"

    if format_str is None:
        is_arm64, format_str = get_asm_config(None)

    result = subprocess.run(
        ["nasm", "-f", format_str, asm_path, "-o", obj_path],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"NASM assembly failed: {result.stderr}")

    return obj_path


def emit_and_assemble(asm_block, output_path: str, syntax: str) -> str:
    """Generate and assemble an asm block in one step.

    Args:
        asm_block: AsmBlock AST node
        output_path: Optional output path (defaults to <name>.o where name is asm func name)
        syntax: Syntax override

    Returns:
        Path to the generated object file
    """
    _, format_str = get_asm_config(syntax)

    if output_path is None:
        name = asm_block.name or "asm_block"
        output_path = f"{name}.o"

    asm_path = os.path.splitext(output_path)[0] + ".s"

    emit_nasm_file(asm_block, asm_path, syntax)
    return assemble_with_nasm(asm_path, output_path, format_str)


def print_asm_block(asm_block, is_arm64: bool = False):
    """Print an asm block to stdout in assembly format.

    Args:
        asm_block: AsmBlock AST node
        is_arm64: Ignored - NASM is x86_64 only
    """
    directives = []
    instructions = []

    for line in asm_block.lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("syntax"):
            continue
        # Labels end with : and are not directives
        if stripped.endswith(":"):
            instructions.append(stripped)
        elif (
            stripped.startswith("section ")
            or stripped.startswith("global")
        ):
            directives.append(stripped)
        elif stripped.startswith("."):
            directives.append(stripped)
        else:
            instructions.append(stripped)

    if asm_block.is_function:
        # Asm function
        for directive in directives:
            if "data" in directive.lower() and not directive.startswith("syntax"):
                print(directive)
        if asm_block.data_lines:
            for dl in asm_block.data_lines:
                print(dl)
        for directive in directives:
            if "text" in directive.lower() and not directive.startswith("syntax"):
                print(directive)
            elif not (
                "data" in directive.lower() or "text" in directive.lower()
            ) and not directive.startswith("syntax"):
                print(directive)
        print(f"global {asm_block.name}")
        print(f"{asm_block.name}:")
        for instr in instructions:
            if instr.strip().lower() == "ret":
                continue
            for expanded in _expand_write_call(instr, is_arm64=False):
                for final_instr in _expand_len_instruction(expanded, is_arm64=False):
                    print(f"    {final_instr}")
        print("    ret")
    else:
        # Bare asm block
        for directive in directives:
            if "data" in directive.lower() and not directive.startswith("syntax"):
                print(directive)
        if asm_block.data_lines:
            for dl in asm_block.data_lines:
                print(dl)
        for directive in directives:
            if not "data" in directive.lower() and not directive.startswith("syntax"):
                print(directive)
        for line in instructions:
            for expanded in _expand_write_call(line, is_arm64=False):
                for final_instr in _expand_len_instruction(expanded, is_arm64=False):
                    print(final_instr)
