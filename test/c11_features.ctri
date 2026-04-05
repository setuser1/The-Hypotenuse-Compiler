#include <stdio.h>

int add(int a, int b) {
    return a + b;
}

int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

void test_if(int val) {
    if (val > 0) {
        printf("positive\n");
    } else if (val < 0) {
        printf("negative\n");
    } else {
        printf("zero\n");
    }
}

void test_switch(int val) {
    switch (val) {
        case 1: printf("one\n"); break;
        case 2: printf("two\n"); break;
        default: printf("other\n"); break;
    }
}

void test_while(int n) {
    int i = 0;
    while (i < n) {
        i++;
    }
}

void test_for(int n) {
    for (int j = 0; j < n; j++) {
        if (j == 5) continue;
    }
}

void test_bitwise(int a, int b) {
    int c = a & b;
    int d = a | b;
    int e = a ^ b;
    int f = ~a;
    int g = a << 2;
    int h = b >> 1;
}

int max(int a, int b) {
    return (a > b) ? a : b;
}

void test_cast(double d) {
    int i = (int)d;
    char c = (char)i;
    float f = (float)c;
}

void test_sizeof(void) {
    size_t s = sizeof(int);
}

void test_literals(void) {
    int hex = 0xFF;
    int octal = 0777;
    long long ll = 123456789LL;
    unsigned int u = 100U;
    float f = 3.14f;
    double d = 2.718;
}

int main(void) {
    int x = 10;
    int y = 20;
    
    printf("Result: %d\n", add(x, y));
    printf("Max: %d\n", max(x, y));
    printf("Factorial: %d\n", factorial(5));
    
    test_if(5);
    test_switch(2);
    test_while(3);
    test_for(10);
    test_bitwise(10, 20);
    test_cast(3.14);
    test_sizeof();
    test_literals();
    
    return 0;
}