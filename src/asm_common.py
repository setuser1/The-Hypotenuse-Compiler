"""Common assembly utilities shared between assembler.py and nasmgen.py."""

import re
from typing import List, Optional, Tuple

X86_INT_REGS = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
X86_FLOAT_REGS = ["xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7"]

ARM64_INT_REGS = ["x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7"]
ARM64_FLOAT_REGS = ["v0", "v1", "v2", "v3", "v4", "v5", "v6", "v7"]

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
) -> Tuple[bool, str]:
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
