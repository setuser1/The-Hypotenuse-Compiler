#include <stdio.h>

struct Container {
    string label;
    dynam int items;
};

int main() {
    Container c;
    c.label = "test";
    printf("Label: %s\n", c.label);
    
    c.items = [10, 20, 30];
    int count = len(c.items);
    printf("Count: %d\n", count);
    
    c.items.push(40);
    count = len(c.items);
    printf("After push: %d\n", count);
    
    int val = c.items[1];
    printf("Item[1]: %d\n", val);
    
    int popped = c.items.pop();
    printf("Popped: %d\n", popped);
    
    if (c.label == "test") {
        printf("String equality: PASS\n");
    }
    
    c.label = c.label + "ing";
    printf("Concat: %s\n", c.label);
    
    printf("All struct basetype tests passed\n");
    return 0;
}
