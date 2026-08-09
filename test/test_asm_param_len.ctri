asm void print(string text) {
    syntax x86_64_linux
    section .text
    mov rax, 1
    mov rdi, 1
    mov rsi, text
    mov rdx, len(text)
    syscall
}

int main() {
    print("hello\n");
    return 0;
}
