asm void sys_write_test() {
    syntax x86_64_linux
    section .data
    string msg = "test"
    section .text
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg]
    mov rdx, 4
    syscall
    ret
}

int main() {
    sys_write_test();
    return 0;
}
