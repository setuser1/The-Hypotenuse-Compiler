// Test most C11 features
#include <stdio.h>

int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

void test_control(int val) {
    if (val > 0) {
        printf("positive\n");
    } else if (val < 0) {
        printf("negative\n");
    } else {
        printf("zero\n");
    }

    switch (val) {
        case 1: printf("one\n"); break;
        case 2: printf("two\n"); break;
        default: printf("other\n"); break;
    }

    int i = 0;
    while (i < 3) { i++; }

    for (int j = 0; j < 5; j++) {
        if (j == 2) continue;
    }

    do {
        val--;
    } while (val > 0);
}

void test_bitwise(int a, int b) {
    int c = a & b;
    int d = a | b;
    int e = a ^ b;
    int f = ~a;
    int g = a << 2;
    int h = b >> 1;
}

void test_ternary(int a, int b) {
    int max = (a > b) ? a : b;
    int min = (a < b) ? a : b;
}

void test_cast(double d) {
    int i = (int)d;
    char c = (char)i;
    float f = (float)c;
}

void test_sizeof(void) {
    size_t s_int = sizeof(int);
    size_t s_ptr = sizeof(int*);
}

void test_do_while(int n) {
    int count = 0;
    do {
        count++;
    } while (count < n);
}

int main(void) {
    int x = 10;
    int y = 20;
    int result = factorial(5);
    
    int* ptr = &x;
    int val = *ptr;
    
    test_control(5);
    test_ternary(x, y);
    test_bitwise(10, 20);
    test_cast(3.14);
    test_sizeof();
    test_do_while(3);
    
    int hex = 0xFF;
    int octal = 0777;
    long long ll = 123456789LL;
    unsigned int uval = 100U;
    float f = 3.14f;
    double d = 2.718;
    
    printf("Result: %d\n", result);
    return 0;
}