asm int syscall_len_test() {
    syntax x86_64_linux
    section .data
    string msg = "hello syscall\n"
    section .text
    mov rax, 1
    mov rdi, 1
    lea rsi, [msg]
    mov rdx, len(msg)
    syscall
    ret
}

int main() {
    return syscall_len_test();
}
