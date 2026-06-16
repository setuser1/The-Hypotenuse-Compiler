"""NASM code generation for inline assembly blocks.

This module handles both x86_64 and arm64 asm blocks.
arm64 blocks are passed through to the GCC assembler;
x86_64 blocks are assembled with NASM.
"""

import os
import platform
import re
import subprocess
from typing import List, Optional, Tuple

PLATFORM = platform.system()
IS_MACOS = PLATFORM == "Darwin"
IS_LINUX = PLATFORM == "Linux"

X86_INT_REGS = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
X86_FLOAT_REGS = ["xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7"]


def _normalize_directive_to_nasm(directive: str) -> str:   #changed
    """Convert GAS-style directives to NASM syntax.
    
    Converts:
        .section .text -> section .text
        .section .data -> section .data
        Other directives are returned as-is
    """
    directive = directive.strip()
    if directive.startswith(".section "):
        return directive[1:]  # Remove leading dot
    return directive


def emit_syscall(
    syscall_num: int,
    args: Optional[List[str]] = None,
    is_arm64: bool = False,
    is_macos: bool = False,
) -> List[str]:
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
            lines = [f"mov x8, #{syscall_num}"]
            for i, arg in enumerate(args[:6]):
                lines.append(f"mov x{i}, {arg}")
            lines.append("svc #0")
            return lines
    else:
        syscall_abi = {
            0: "read",
            1: "write",
            2: "open",
            3: "close",
            60: "exit",
        }
        name = syscall_abi.get(syscall_num, f"syscall_{syscall_num}")
        lines = [f"; {name} (syscall {syscall_num})"]
        regs = ["rdi", "rsi", "rdx", "r10", "r8", "r9"]
        for i, arg in enumerate(args[:6]):
            lines.append(f"    mov {regs[i]}, {arg}")
        lines.append(f"    mov rax, {syscall_num}")
        lines.append("    syscall")
        return lines


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


def _expand_len_instruction(
    instr: str, is_arm64: bool, label_suffix: str = ""
) -> List[str]:
    """Expand len() into inline assembly.

    Args:
        instr: The instruction string to process
        is_arm64: True for ARM64, False for x86_64
        label_suffix: Optional suffix for labels to make them unique
    """
    match = re.match(r"^\s*mov\s+([^,]+),\s*len\(([^)]+)\)\s*$", instr)
    if not match:
        return [instr]
    dst = match.group(1).strip()
    src = match.group(2).strip()

    if label_suffix:
        loop_label = (
            f".Lhyp_len_loop_{label_suffix}"
            if is_arm64
            else f".hyp_len_loop_{label_suffix}"
        )
        done_label = (
            f".Lhyp_len_done_{label_suffix}"
            if is_arm64
            else f".hyp_len_done_{label_suffix}"
        )
    else:
        loop_label = ".Lhyp_len_loop" if is_arm64 else ".hyp_len_loop"
        done_label = ".Lhyp_len_done" if is_arm64 else ".hyp_len_done"

    if is_arm64:
        return [
            f"mov x10, {src}",
            f"mov {dst}, x10",
            "mov x11, #0",
            f"{loop_label}:",
            "ldrb w12, [x10], #1",
            f"cbz w12, {done_label}",
            "add x11, x11, #1",
            f"b {loop_label}",
            f"{done_label}:",
            f"mov {dst}, x11",
        ]
    else:
        return [
            f"mov rcx, {src}",
            f"mov {dst}, rcx",
            "xor rax, rax",
            f".{label_suffix if label_suffix else ''}hyp_len_loop:",
            "cmp byte [rcx], 0",
            f"je .{label_suffix if label_suffix else ''}hyp_len_done",
            "inc rcx",
            f"jmp .{label_suffix if label_suffix else ''}hyp_len_loop",
            f".{label_suffix if label_suffix else ''}hyp_len_done:",
            f"sub rcx, {src}",
            f"mov {dst}, rcx",
        ]


def _split_binary_expr(expr: str) -> Optional[Tuple[str, str, str]]:
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
        f.write(f"    sdiv {dst}, {dst}, {right}\n")
        if op == "%":
            f.write(f"    msub {dst}, {dst}, {right}, {left}\n")


def _emit_return_expr(f, return_expr, ret_type, is_arm64: bool = False):
    """Emit instructions that place a simple return expression in the ABI register."""
    if return_expr is None or return_expr == "":
        return
    if ret_type in ("float", "double"):
        if is_arm64:
            f.write(f"    fmov v0, {return_expr}\n")
        else:
            f.write(f"    movq xmm0, {return_expr}\n")
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
) -> dict:
    """Build parameter to stack slot mapping.

    On x86_64: params map to [rbp-8], [rbp-16], ... (stack slots saved from ABI regs).
    On arm64: params map to [sp, #0], [sp, #8], ... (stack slots saved from ABI regs).
    """
    param_map = {}
    offset = 8

    for param_type, param_name in params:
        if is_arm64:
            param_map[param_name] = f"[sp, #{offset}]"
        else:
            param_map[param_name] = f"[rbp-{offset}]"
        offset += 8

    return param_map


def _process_instructions(
    instructions: List[str],
    param_map: dict,
    is_arm64: bool,
):
    """Process instructions, replacing parameter names with registers."""
    updated = []
    for instr in instructions:
        if instr.strip().endswith(":"):
            updated.append(instr)
            continue
        mnemonic_match = re.match(r"^(\s*[A-Za-z_.][A-Za-z0-9_.]*\b)(.*)$", instr)
        if mnemonic_match:
            prefix = mnemonic_match.group(1)
            result = mnemonic_match.group(2)
        else:
            prefix = ""
            result = instr
        for param_name, addr in param_map.items():
            pattern = r"\b" + re.escape(param_name) + r"\b"
            result = re.sub(pattern, addr, result)
        updated.append(prefix + result)
    return updated


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

    # NASM only supports x86_64; ARM64 asm blocks are handled by assembler.py
    _generate_x86_asm(asm_block, output_path, is_macos)


def _generate_x86_asm(asm_block, output_path: str, is_macos: bool = False):
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

    data_lines = _build_data_section(asm_block.variables, "", is_arm64=False)
    with open(output_path, "w") as f:
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
                normalized = _normalize_directive_to_nasm(d) #changed
                f.write(f"{normalized}\n")

        if asm_block.is_function and asm_block.name:
            symbol_prefix = "_" if is_macos else ""
            global_name = f"{symbol_prefix}{asm_block.name}"
            f.write(f"global {global_name}\n")
            f.write(f"{global_name}:\n")

            f.write("    push rbp\n")
            f.write("    mov rbp, rsp\n")

            # Save parameters from ABI registers to their stack slots
            int_idx = 0
            float_idx = 0
            for param_type, param_name in asm_block.params:
                if param_type in ("float", "double"):
                    if float_idx < len(X86_FLOAT_REGS):
                        reg = X86_FLOAT_REGS[float_idx]
                        slot = param_map[param_name]
                        f.write(f"    movsd {slot}, {reg}\n")
                    float_idx += 1
                else:
                    if int_idx < len(X86_INT_REGS):
                        reg = X86_INT_REGS[int_idx]
                        slot = param_map[param_name]
                        f.write(f"    mov {slot}, {reg}\n")
                    int_idx += 1

            for instr in updated_instructions:
                instr_lower = instr.strip().lower()
                if instr_lower == "ret":
                    continue
                f.write(f"    {instr}\n")

            _emit_return_expr(
                f, asm_block.return_expr, asm_block.ret_type, is_arm64=False
            )

            f.write("    pop rbp\n")
            f.write("    ret\n")
        else:
            for instr in updated_instructions:
                f.write(f"{instr}\n")
            if asm_block.return_expr is not None:
                _emit_return_expr(
                    f, asm_block.return_expr, asm_block.ret_type, is_arm64=False
                )
                f.write("    ret\n")


def _build_data_section(
    variables: List[dict], symbol_prefix: str, is_arm64: bool = False
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
            lines.append(f"    times {array_size} {nasm_directive} {initializer or 0}")
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
        asm_block: AsmBlock AST node from parser
        output_path: Path to write the .s file
        syntax: Optional syntax override (e.g., "x86_64_elf")

    Returns:
        Path to the generated object file
    """
    emit_nasm_file(asm_block, output_path, syntax)
    is_arm64, format_str = get_asm_config(syntax)
    obj_path = output_path.replace(".s", ".o")
    return assemble_with_nasm(output_path, obj_path, format_str)


def print_asm_block(asm_block, is_arm64: bool = False):
    """Print an asm block in a readable format."""
    # Simple print of the block structure
    print(f"  asm block: {asm_block.name or '<anonymous>'}")
    print(f"    syntax: {asm_block.syntax or '<none>'}")
    print(f"    params: {[(t, n) for t, n in asm_block.params]}")
    print(f"    return type: {asm_block.ret_type}")
    if asm_block.variables:
        print(f"    variables: {[v['name'] for v in asm_block.variables]}")
