#include <stdio.h>
#include <stdlib.h>
#include "compiler.h"

char **lexsize(char *source, size_t *out_count) {
    if (!source || !out_count) return NULL;

    char **arr = NULL;
    size_t capacity = 16, count = 0;

    Lexer lexer = {source, {TOK_UNKNOWN, NULL}};
    arr = malloc(sizeof(char *) * capacity);
    if (!arr) {
        fprintf(stderr, "Failed to allocate token array\n");
        free(source);
        *out_count = 0;
        return NULL;
    }

    while (1) {
        const Token tok = lexer_next(&lexer);

        /* EOF cleanup */
        if (tok.type == TOK_EOF) {
            if (tok.text)
                free(tok.text);
            break;
        }

        /* Expand array dynamically */
        if (count >= capacity) {
            capacity *= 2;
            char **new_arr = realloc(arr, sizeof(char *) * capacity);
            if (!new_arr) {
                fprintf(stderr, "Failed to resize token array\n");
                for (size_t i = 0; i < count; i++)
                    free(arr[i]);
                free(arr);
                free(source);
                if (tok.text) free(tok.text);
                *out_count = 0;
                return NULL;
            }
            arr = new_arr;
        }

        arr[count++] = tok.text; /* take ownership of tok.text */
    }

    free(source); /* lexsize takes ownership of source */
    *out_count = count;
    return arr;
}

int main(const int argc, char *argv[]) {
    char *source = NULL;

    if (argc < 2) {
        fprintf(stderr, "Usage: %s <source_file>\n", argv[0]);
        return 1;
    }

    source = read_file(argv[1]);
    if (!source) {
        fprintf(stderr, "Failed to read file: %s\n", argv[1]);
        return 1;
    }

    size_t token_count = 0;
    char **tokens = lexsize(source, &token_count);
    if (!tokens && token_count == 0) {
        return 1;
    }

    printf("Tokens:\n");
    for (size_t i = 0; i < token_count; i++)
        printf("%3zu : '%s'\n", i, tokens[i] ? tokens[i] : "(null)");

    for (size_t i = 0; i < token_count; i++)
        free(tokens[i]);
    free(tokens);

    return 0;
}
