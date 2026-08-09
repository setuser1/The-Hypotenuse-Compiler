#include <stdio.h>

struct Wrapper {
    string value;
};

int main() {
    Wrapper w;
    w.value = "hello";
    printf("Initial: %s\n", w.value);

    // Test 1: String literal reassignment (should free old, strdup new)
    w.value = "world";
    printf("After literal: %s\n", w.value);

    // Test 2: String concatenation reassignment (should free old, alloc new)
    w.value = w.value + "!";
    printf("After concat: %s\n", w.value);

    // Test 3: Multiple reassignments to verify no leaks
    w.value = "first";
    w.value = "second";
    w.value = "third";
    printf("After multiple: %s\n", w.value);

    // Test 4: Concatenation with string variable
    string suffix = "ified";
    w.value = "cert" + suffix;
    printf("After var concat: %s\n", w.value);

    // Test 5: Verify string equality still works
    if (w.value == "certified") {
        printf("String equality: PASS\n");
    }

    // Free final string
    __ctri_free(w.value);

    printf("All string field reassignment tests passed\n");
    return 0;
}
