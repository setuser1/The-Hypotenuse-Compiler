int main() {
    asm int addInts(int a, int b) {
        syntax x86_64_linux
        section .text
        mov rax, a
        add rax, b
        return
    }
    return addInts(2, 3);
}
