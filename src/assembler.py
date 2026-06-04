"""Assembly and linking for C triangle compiler."""



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
        if is_arm64:
            # ARM64: map ALL parameters to stack slots [sp, #N]
            param_map[param_name] = f"[sp, #{offset}]"
            offset += 8
        elif param_type in ("float", "double"):
            if float_idx < len(float_regs):
                param_map[param_name] = float_regs[float_idx]
                float_idx += 1
            else:
                param_map[param_name] = f"[rbp-{offset}]"
                offset += 8
        else:
            if int_idx < len(int_regs):
                param_map[param_name] = int_regs[int_idx]
                int_idx += 1
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


def assemble_asm_blocks(asm_blocks, source_path, target_arch=None, output_format=None):
    """Generate .asm files from asm blocks and assemble with NASM.

    Args:
        asm_blocks: List of AsmBlock nodes
        source_path: Path to source file
        target_arch: Override target architecture ('x86_64' or 'arm64').
                    Defaults to auto-detect from platform.
        output_format: Override object file format ('macho', 'elf', 'win64').
                      Defaults to auto-detect from platform.
    """
    import subprocess
    import shutil
    import os
    import platform

    if not asm_blocks:
        return []

    base_dir = os.path.dirname(source_path) or "."
    object_files = []

    # Determine if we're on macOS (for symbol naming)
    is_macos = platform.system() == "Darwin"
    current_arch = platform.machine()
    len_label_counter = 0
    emitted_asm_stems = set()

    def expand_write_call(instr, is_arm64_target):
        """Replace _write calls with pure syscalls."""
        return _expand_write_call(instr, is_arm64_target)

    def expand_len_instruction(instr, is_arm64_target):
        """Expand `mov <reg>, len(<ptr>)` into inline assembly."""
        nonlocal len_label_counter
        label_id = len_label_counter
        len_label_counter += 1
        return _expand_len_instruction(instr, is_arm64_target, str(label_id))

    def emit_return_expr(f, asm_block, is_arm64_target):
        if asm_block.return_expr is None or asm_block.return_expr == "":
            return
        if asm_block.ret_type in ("float", "double"):
            if is_arm64_target:
                f.write(f"    fmov v0, {asm_block.return_expr}\n")
            else:
                f.write(f"    movq xmm0, {asm_block.return_expr}\n")
        else:
            if is_arm64_target:
                _emit_integer_expr_arm64(f, asm_block.return_expr, "x0")
            else:
                _emit_integer_expr_x86(f, asm_block.return_expr, "rax")

    def build_data_lines(asm_block, is_arm64_target):
        """Build target-specific data declarations for asm variables."""
        lines = []
        symbol_prefix = "_" if is_arm64_target else ""

        for var_info in asm_block.variables:
            name = var_info["name"]
            var_type = var_info["type"]
            array_size = var_info.get("size")
            initializer = var_info.get("initializer")
            symbol_name = f"{symbol_prefix}{name}"

            if is_arm64_target:
                lines.append(f".globl {symbol_name}")
                lines.append(f"{symbol_name}:")
                if var_type == "string":
                    escaped = _escape_string(initializer or "")
                    lines.append(f'.asciz "{escaped}"')
                elif var_type == "char":
                    if array_size:
                        init_val = initializer or "0"
                        lines.append(f".fill {array_size}, 1, {init_val}")
                    else:
                        lines.append(f".byte {initializer or '0'}")
                elif var_type == "short":
                    init_val = initializer or "0"
                    if array_size:
                        lines.append(f".fill {array_size}, 2, {init_val}")
                    else:
                        lines.append(f".short {init_val}")
                elif var_type in ("int", "long"):
                    init_val = initializer or "0"
                    if array_size:
                        lines.append(f".fill {array_size}, 4, {init_val}")
                    else:
                        lines.append(f".long {init_val}")
                elif var_type == "float":
                    init_val = initializer or "0"
                    if array_size:
                        values = ", ".join([init_val] * array_size)
                        lines.append(f".float {values}")
                    else:
                        lines.append(f".float {init_val}")
                elif var_type == "double":
                    init_val = initializer or "0"
                    if array_size:
                        values = ", ".join([init_val] * array_size)
                        lines.append(f".double {values}")
                    else:
                        lines.append(f".double {init_val}")
            else:
                lines.append(f"global {symbol_name}")
                data_decl = var_info.get("asm_line", "")
                if data_decl:
                    if data_decl.startswith(f"{name}:"):
                        data_decl = f"{symbol_name}:{data_decl[len(name) + 1 :]}"
                    lines.append(data_decl)

        return lines

    def normalize_arm64_directive(directive):
        """Translate generic section directives to Apple as syntax."""
        stripped = directive.strip()
        lowered = stripped.lower()
        if lowered == "section .text":
            return ".section __TEXT,__text"
        if lowered == "section .data":
            return ".section __DATA,__data"
        return stripped

    # Determine target architecture for filtering
    if target_arch:
        target_is_arm64 = (target_arch == "arm64")
    else:
        # Auto-detect from platform
        if is_macos:
            target_is_arm64 = (current_arch == "arm64")
        else:
            target_is_arm64 = False  # Linux defaults to x86_64

    for asm_index, asm_block in enumerate(asm_blocks):
        # Determine config for this asm block
        is_arm64, asm_format = get_asm_config(
            asm_block.syntax, target_arch, output_format, is_macos, current_arch
        )

        # Skip blocks that don't match current target architecture
        if asm_block.syntax:
            # Check block's own syntax to determine its architecture
            block_is_arm64, _ = get_asm_config(
                asm_block.syntax, None, None, is_macos, current_arch
            )
            if target_is_arm64 and not block_is_arm64:
                continue
            if not target_is_arm64 and block_is_arm64:
                continue

        if is_macos and asm_format == "elf64":
            block_name = asm_block.name or "<asm>"
            raise RuntimeError(
                f"asm block '{block_name}' targets ELF, but macOS native compilation expects Mach-O objects. "
                "Use 'syntax arm64_macho' for Apple Silicon, 'syntax x86_64_macho' for Intel macOS, or compile on Linux for 'x86_64_elf'."
            )

        asm_stem = asm_block.name if asm_block.name else f"asm_block_{asm_index}"
        if asm_stem in emitted_asm_stems:
            continue
        emitted_asm_stems.add(asm_stem)
        asm_path = os.path.join(base_dir, f"{asm_stem}.s")
        obj_path = os.path.join(base_dir, f"{asm_stem}.o")

        if is_arm64:
            # ARM64: Use Apple as
            # AAPCS64: integer params in x0-x7, float params in v0-v7

            # Collect directives and instructions
            directives = []
            instructions = []
            for line in asm_block.lines:
                stripped = line.strip()
                # Skip syntax declaration and empty lines
                if not stripped or stripped.startswith("syntax"):
                    continue
                # Labels end with : and are not directives
                if stripped.endswith(":"):
                    instructions.append(stripped)
                elif (
                    stripped.startswith("section")
                    or stripped.startswith(".")
                    or stripped.startswith("global")
                ):
                    directives.append(stripped)
                else:
                    instructions.append(stripped)

            # Generate parameter mapping based on type
            param_map = _build_param_map(
                asm_block.params, ARM64_INT_REGS, ARM64_FLOAT_REGS, is_arm64=True
            )

            # Update instructions to use register names or stack offsets
            updated_instructions = _process_instructions(
                instructions, param_map, is_arm64=True
            )
            # Expand _write calls and len() instructions
            final_instructions = []
            for instr in updated_instructions:
                for expanded in expand_write_call(instr, is_arm64_target=True):
                    final_instructions.extend(
                        expand_len_instruction(expanded, is_arm64_target=True)
                    )
            updated_instructions = final_instructions

            # Generate .s file for Apple as
            with open(asm_path, "w") as f:
                f.write("// Generated by Hypotenuse Compiler\n")
                # Write data section variables first if any
                data_lines = build_data_lines(asm_block, is_arm64_target=True)
                if data_lines:
                    f.write(".section __DATA,__data\n")
                    for data_line in data_lines:
                        f.write(f"{data_line}\n")
                # Section directives (text section)
                normalized_directives = [
                    normalize_arm64_directive(directive) for directive in directives
                ]
                has_text_section = any(
                    "__TEXT" in d or ".text" in d for d in normalized_directives
                )
                if not has_text_section:
                    f.write(".section __TEXT,__text\n")
                for directive in normalized_directives:
                    if directive == ".section __DATA,__data" and data_lines:
                        continue
                    if not directive.startswith("syntax"):
                        f.write(f"{directive}\n")
                if asm_block.is_function:
                    # On macOS, C compiler adds underscore to all symbols
                    # So _add becomes __add in the final binary
                    global_name = f"__{asm_block.name}"
                    f.write(f".global {global_name}\n")
                    f.write(f"{global_name}:\n")
                    num_params = len(asm_block.params)
                    frame_size = 16 + num_params * 8
                    # Allocate frame + param save area
                    f.write(f"    sub sp, sp, #{frame_size}\n")
                    # Save frame pointer and link register at top of frame
                    f.write(f"    stp x29, x30, [sp, #{num_params * 8}]\n")
                    f.write(f"    add x29, sp, #{num_params * 8}\n")
                    # Save parameter registers to stack slots
                    int_idx = 0
                    float_idx = 0
                    for param_type, param_name in asm_block.params:
                        if param_type in ("float", "double"):
                            if float_idx < 8:
                                slot = param_map[param_name]
                                reg = ARM64_FLOAT_REGS[float_idx]
                                f.write(f"    str {reg}, {slot}\n")
                            float_idx += 1
                        else:
                            if int_idx < 8:
                                slot = param_map[param_name]
                                reg = ARM64_INT_REGS[int_idx]
                                f.write(f"    str {reg}, {slot}\n")
                            int_idx += 1
                    # Write instructions (skip user's ret, we add our own)
                    for instr in updated_instructions:
                        instr_lower = instr.strip().lower()
                        if instr_lower == "ret":
                            continue  # Skip user's ret, we add our own
                        f.write(f"    {instr}\n")
                    emit_return_expr(f, asm_block, is_arm64_target=True)
                    # Epilogue (restore x29/x30 and deallocate frame)
                    f.write(f"    ldp x29, x30, [sp, #{num_params * 8}]\n")
                    f.write(f"    add sp, sp, #{frame_size}\n")
                    f.write("    ret\n")
                else:
                    for instr in updated_instructions:
                        f.write(f"{instr}\n")
                    if asm_block.return_expr is not None:
                        emit_return_expr(f, asm_block, is_arm64_target=True)
                        f.write("    ret\n")

            # Assemble with Apple as
            result = subprocess.run(
                ["as", "-arch", "arm64", asm_path, "-o", obj_path],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"as failed: {result.stderr}")
        else:
            # x86_64: Use NASM
            if not shutil.which("nasm"):
                raise RuntimeError(
                    "nasm not found in PATH. Install NASM to use inline assembly."
                )

            # Collect directives and instructions
            directives = []
            instructions = []
            for line in asm_block.lines:
                stripped = line.strip()
                # Skip syntax declaration and empty lines
                if not stripped or stripped.startswith("syntax"):
                    continue
                # Labels end with : and are not directives
                if stripped.endswith(":"):
                    instructions.append(stripped)
                elif stripped.startswith("section ") or stripped.startswith("."):
                    directives.append(stripped)
                else:
                    instructions.append(stripped)

            # Generate parameter mapping based on type
            param_map = _build_param_map(
                asm_block.params, X86_INT_REGS, X86_FLOAT_REGS, is_arm64=False
            )

            # Update instructions to use register names
            updated_instructions = _process_instructions(
                instructions, param_map, is_arm64=False
            )
            # Expand _write calls and len() instructions
            final_instructions = []
            for instr in updated_instructions:
                for expanded in expand_write_call(instr, is_arm64_target=False):
                    final_instructions.extend(
                        expand_len_instruction(expanded, is_arm64_target=False)
                    )
            updated_instructions = final_instructions

            # Generate .asm file
            with open(asm_path, "w") as f:
                f.write("; Generated by Hypotenuse Compiler\n")
                # Write data section variables first if any
                data_lines = build_data_lines(asm_block, is_arm64_target=False)
                if data_lines:
                    # Check if there's already a .data section in directives
                    has_data_section = any(".data" in d for d in directives)
                    if not has_data_section:
                        f.write("section .data\n")
                    for data_line in data_lines:
                        f.write(f"{data_line}\n")
                # Write section directives (skip data, we already handled it)
                for directive in directives:
                    if ".data" not in directive:
                        f.write(f"{directive}\n")
                # Ensure we have a text section
                has_text_section = any(
                    ".text" in d or ".section" in d for d in directives
                )
                if not has_text_section:
                    f.write("section .text\n")
                if asm_block.is_function:
                    # Global declaration and function label
                    # On macOS, C compiler adds underscore to all symbols
                    global_name = f"__{asm_block.name}" if is_macos else asm_block.name
                    f.write(f"global {global_name}\n")
                    f.write(f"{global_name}:\n")
                    # Add prologue
                    f.write("    push rbp\n")
                    f.write("    mov rbp, rsp\n")
                    # Save float registers that will be used (if any float params)
                    for param_type, param_name in asm_block.params:
                        if param_type in ("float", "double"):
                            # Get the register for this param
                            reg = param_map.get(param_name, "")
                            if reg.startswith("xmm"):
                                f.write("    sub rsp, 8\n")
                                f.write(f"    movsd [rsp], {reg}\n")
                    # Write instructions (skip user's ret, we add our own)
                    for instr in updated_instructions:
                        instr_lower = instr.strip().lower()
                        if instr_lower == "ret":
                            continue  # Skip user's ret, we add our own
                        f.write(f"    {instr}\n")
                    emit_return_expr(f, asm_block, is_arm64_target=False)
                    # Epilogue (always needed)
                    f.write("    pop rbp\n")
                    f.write("    ret\n")
                else:
                    for instr in updated_instructions:
                        f.write(f"{instr}\n")
                    if asm_block.return_expr is not None:
                        emit_return_expr(f, asm_block, is_arm64_target=False)
                        f.write("    ret\n")

            # Assemble with NASM
            result = subprocess.run(
                ["nasm", "-f", asm_format, asm_path, "-o", obj_path],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"nasm failed: {result.stderr}")

        object_files.append(obj_path)

    return object_files


def compile_with_gcc(c_path, output_path=None, extra_flags=None, asm_objects=None):
    """Compile C file to executable with gcc or the compiler named by CC."""
    import subprocess
    import shutil
    import os
    import shlex

    compiler = os.environ.get("CC", "gcc")
    compiler_cmd = shlex.split(compiler)
    if not compiler_cmd:
        raise RuntimeError("C compiler command is empty. Set CC or install GCC to use --compile.")

    if not shutil.which(compiler_cmd[0]):
        raise RuntimeError(f"{compiler_cmd[0]} not found in PATH. Set CC or install GCC to use --compile.")

    if output_path is None:
        output_path = os.path.splitext(c_path)[0]
    # else: output_path is already set correctly, no need for reassignment

    cmd = compiler_cmd + [c_path, "-o", output_path]
    # Add asm object files
    if asm_objects:
        cmd.extend(asm_objects)
    # Basic validation for extra_flags to prevent obvious injection attempts
    if extra_flags:
        # Split and filter out any empty strings or potentially dangerous flags
        flags = [flag for flag in extra_flags.split() if flag.strip()]
        # Additional safety: reject flags that try to change output file or perform dangerous operations
        safe_flags = []
        skip_next = False
        for i, flag in enumerate(flags):
            if skip_next:
                skip_next = False
                continue
            # Skip -o and its argument as we control the output file
            if flag == "-o":
                skip_next = True  # Skip the next argument (output file)
                continue
            # Allow library/include/linker flags
            if (
                flag.startswith("-l")
                or flag.startswith("-L")
                or flag.startswith("-I")
                or flag.startswith("-D")
            ):
                safe_flags.append(flag)
            # Allow linker flags
            elif flag.startswith("-Wl,"):
                safe_flags.append(flag)
            # Allow common warning/optimization/debug flags
            elif (
                flag in ["-Wall", "-Wextra", "-Werror", "-pedantic"]
                or flag in ["-m32", "-m64"]
                or flag.startswith("-march=")
                or flag.startswith("-mcpu=")
                or flag.startswith("-mtune=")
                or flag.startswith("-std=")
                or flag in ["-O0", "-O1", "-O2", "-O3", "-Os", "-Ofast"]
                or flag == "-g"
            ):
                safe_flags.append(flag)
            # Ignore other flags for safety

        cmd.extend(safe_flags)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"{compiler_cmd[0]} failed: {result.stderr}")

    return output_path
