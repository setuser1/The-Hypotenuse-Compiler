"""Assembly and linking for C triangle compiler."""

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
    args: list = [],
    is_arm64: bool = False,
    is_macos: bool = False,
) -> list:
    """Emit syscall instruction sequence for current architecture.

    Args:
        syscall_num: Syscall number
        args: List of register arguments (will be placed in order)
        is_arm64: True for ARM64, False for x86_64
        is_macos: True if targeting macOS

    Returns:
        List of assembly instructions
    """
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
        x86_regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
        lines = [f"mov rax, {syscall_num}"]
        for i, arg in enumerate(args[:6]):
            reg = x86_regs[i]
            lines.append(f"mov {reg}, {arg}")
        lines.append("syscall")
        return lines


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

    def expand_write_call(instr, is_arm64_target):
        """Replace _write calls with pure syscalls."""
        stripped = instr.strip()
        if "bl" in stripped.lower() and "_write" in stripped:
            if is_arm64_target:
                return [
                    "mov x16, #4",
                    "svc #0x80",
                ]
            else:
                return [
                    "mov rax, 1",
                    "syscall",
                ]
        return [instr]

    def expand_len_instruction(instr, is_arm64_target):
        """Expand `mov <reg>, len(<ptr>)` into inline assembly."""
        nonlocal len_label_counter

        match = re.match(r"^\s*mov\s+([^,]+),\s*len\(([^)]+)\)\s*$", instr)
        if not match:
            return [instr]

        dest = match.group(1).strip()
        src = match.group(2).strip()
        label_id = len_label_counter
        len_label_counter += 1

        if is_arm64_target:
            loop_label = f".Lhyp_len_loop_{label_id}"
            done_label = f".Lhyp_len_done_{label_id}"
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

        loop_label = f".hyp_len_loop_{label_id}"
        done_label = f".hyp_len_done_{label_id}"
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

    def split_binary_expr(expr):
        parts = expr.split()
        if len(parts) == 3 and parts[1] in ("+", "-", "*", "/", "%"):
            return parts[0], parts[1], parts[2]
        return None

    def emit_integer_return(f, expr, dst, is_arm64_target):
        binary = split_binary_expr(expr)
        if not binary:
            f.write(f"    mov {dst}, {expr}\n")
            return
        left, op, right = binary
        f.write(f"    mov {dst}, {left}\n")
        if is_arm64_target:
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
            return
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

    def emit_return_expr(f, asm_block, is_arm64_target):
        if asm_block.return_expr is None or asm_block.return_expr == "":
            return
        if asm_block.ret_type in ("float", "double"):
            if is_arm64_target:
                f.write(f"    fmov v0, {asm_block.return_expr}\n")
            else:
                f.write(f"    movq xmm0, {asm_block.return_expr}\n")
        elif is_arm64_target:
            emit_integer_return(f, asm_block.return_expr, "x0", True)
        else:
            emit_integer_return(f, asm_block.return_expr, "rax", False)

    def _escape_quoted_string(value):
        return (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )

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
                    escaped = _escape_quoted_string(initializer or "")
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

    def get_asm_config(asm_block):
        """Determine architecture and format for an asm block.

        Priority:
        1. asm block's explicit syntax (syntax x86_64_elf or syntax arm64_macho)
        2. command-line --target flag
        3. command-line --format flag
        4. auto-detect from platform
        """
        # Check for explicit syntax in asm block
        if asm_block.syntax:
            syntax = asm_block.syntax.lower()
            if "x86_64" in syntax and "elf" in syntax:
                return False, "elf64"
            elif "arm64" in syntax and "macho" in syntax:
                return True, "macho64"
            elif "x86_64" in syntax and "macho" in syntax:
                return False, "macho64"
            elif "arm64" in syntax:
                return True, "macho64"
            elif "elf" in syntax:
                return False, "elf64"

        # Check command-line flags
        if target_arch == "x86_64":
            return False, "macho64" if is_macos else "elf64"
        elif target_arch == "arm64":
            return True, "macho64"
        elif output_format == "macho":
            return True, "macho64"
        elif output_format == "elf":
            return False, "elf64"

        # Auto-detect from platform
        if is_macos and current_arch == "arm64":
            return True, "macho64"
        elif is_macos and current_arch == "x86_64":
            return False, "macho64"
        else:
            return False, "elf64"

    for asm_index, asm_block in enumerate(asm_blocks):
        # Determine config for this asm block
        is_arm64, asm_format = get_asm_config(asm_block)

        if is_macos and asm_format == "elf64":
            block_name = asm_block.name or "<asm>"
            raise RuntimeError(
                f"asm block '{block_name}' targets ELF, but macOS native compilation expects Mach-O objects. "
                "Use 'syntax arm64_macho' for Apple Silicon, 'syntax x86_64_macho' for Intel macOS, or compile on Linux for 'x86_64_elf'."
            )

        asm_stem = asm_block.name if asm_block.name else f"asm_block_{asm_index}"
        asm_path = os.path.join(base_dir, f"{asm_stem}.s")
        obj_path = os.path.join(base_dir, f"{asm_stem}.o")

        import re

        if is_arm64:
            # ARM64: Use Apple as
            # AAPCS64: integer params in x0-x7, float params in v0-v7
            arm64_int_regs = ["x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7"]
            arm64_float_regs = ["v0", "v1", "v2", "v3", "v4", "v5", "v6", "v7"]

            # Collect directives and instructions
            directives = []
            instructions = []
            for line in asm_block.lines:
                stripped = line.strip()
                # Skip syntax declaration and empty lines
                if not stripped or stripped.startswith("syntax"):
                    continue
                if (
                    stripped.startswith("section")
                    or stripped.startswith(".")
                    or stripped.startswith("global")
                ):
                    directives.append(stripped)
                else:
                    instructions.append(stripped)

            # Generate parameter mapping based on type
            param_map = {}
            int_reg_idx = 0
            float_reg_idx = 0
            offset = 0
            for param_type, param_name in asm_block.params:
                # Determine register based on type
                if param_type in ("float", "double"):
                    if float_reg_idx < len(arm64_float_regs):
                        # Float params go in float registers
                        param_map[param_name] = arm64_float_regs[float_reg_idx]
                        float_reg_idx += 1
                    else:
                        # 溢出 to stack
                        param_map[param_name] = f"[sp, #{offset}]"
                        offset += 8
                else:
                    # Integer params go in integer registers
                    if int_reg_idx < len(arm64_int_regs):
                        param_map[param_name] = arm64_int_regs[int_reg_idx]
                        int_reg_idx += 1
                    else:
                        # 溢出 to stack
                        param_map[param_name] = f"[sp, #{offset}]"
                        offset += 8

            # Update instructions to use register names or stack offsets
            updated_instructions = []
            for instr in instructions:
                updated_instr = instr
                for param_name, addr in param_map.items():
                    pattern = r"\b" + re.escape(param_name) + r"\b"
                    updated_instr = re.sub(pattern, addr, updated_instr)
                for expanded in expand_write_call(updated_instr, is_arm64_target=True):
                    updated_instructions.extend(
                        expand_len_instruction(expanded, is_arm64_target=True)
                    )

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
                    # Save frame pointer and link register
                    f.write("    stp x29, x30, [sp, #-16]!\n")
                    f.write("    mov x29, sp\n")
                    # Write instructions (skip user's ret, we add our own)
                    for instr in updated_instructions:
                        instr_lower = instr.strip().lower()
                        if instr_lower == "ret":
                            continue  # Skip user's ret, we add our own
                        f.write(f"    {instr}\n")
                    emit_return_expr(f, asm_block, is_arm64_target=True)
                    # Epilogue (always needed to restore x29/x30)
                    f.write("    ldp x29, x30, [sp], #16\n")
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

            # x86_64 System V ABI: integer and float parameter registers
            x86_int_regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
            x86_float_regs = [
                "xmm0",
                "xmm1",
                "xmm2",
                "xmm3",
                "xmm4",
                "xmm5",
                "xmm6",
                "xmm7",
            ]

            # Collect directives and instructions
            directives = []
            instructions = []
            for line in asm_block.lines:
                stripped = line.strip()
                # Skip syntax declaration and empty lines
                if not stripped or stripped.startswith("syntax"):
                    continue
                if stripped.startswith("section ") or stripped.startswith("."):
                    directives.append(stripped)
                else:
                    instructions.append(stripped)

            # Generate parameter mapping based on type
            param_map = {}
            int_reg_idx = 0
            float_reg_idx = 0
            offset = 8
            for param_type, param_name in asm_block.params:
                # Determine register based on type
                if param_type in ("float", "double"):
                    if float_reg_idx < len(x86_float_regs):
                        # Float params go in xmm registers
                        param_map[param_name] = x86_float_regs[float_reg_idx]
                        float_reg_idx += 1
                    else:
                        # 溢出 to stack
                        param_map[param_name] = f"[rbp-{offset}]"
                        offset += 8
                else:
                    # Integer params go in integer registers
                    if int_reg_idx < len(x86_int_regs):
                        param_map[param_name] = x86_int_regs[int_reg_idx]
                        int_reg_idx += 1
                    else:
                        # 溢出 to stack
                        param_map[param_name] = f"[rbp-{offset}]"
                        offset += 8

            # Update instructions to use register names
            updated_instructions = []
            for instr in instructions:
                updated_instr = instr
                for param_name, addr in param_map.items():
                    pattern = r"\b" + re.escape(param_name) + r"\b"
                    updated_instr = re.sub(pattern, addr, updated_instr)
                for expanded in expand_write_call(updated_instr, is_arm64_target=False):
                    updated_instructions.extend(
                        expand_len_instruction(expanded, is_arm64_target=False)
                    )

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
    """Compile C file to executable with gcc."""
    import subprocess
    import shutil
    import os

    if not shutil.which("gcc"):
        raise RuntimeError("gcc not found in PATH. Install GCC to use --compile.")

    if output_path is None:
        output_path = os.path.splitext(c_path)[0]
    # else: output_path is already set correctly, no need for reassignment

    cmd = ["gcc", c_path, "-o", output_path]
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
                or flag.startswith("-std=")
                or flag in ["-O0", "-O1", "-O2", "-O3", "-Os", "-Ofast"]
                or flag == "-g"
            ):
                safe_flags.append(flag)
            # Ignore other flags for safety

        cmd.extend(safe_flags)

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"gcc failed: {result.stderr}")

    return output_path
