asm int sys_read_char() {
    syntax x86_64_linux
    section .data
    char buf = 0
    section .text
    mov rax, 0
    mov rdi, 0
    lea rsi, [buf]
    mov rdx, 1
    syscall
    movzx eax, byte [buf]
    ret
}

int main() {
    return sys_read_char();
}
