"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.prototype.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = void 0;
const vscode = __importStar(require("vscode"));
// Keywords recognized by the C△ compiler
const KEYWORDS = [
    // Control flow
    'if', 'else', 'while', 'for', 'do', 'switch', 'case', 'default', 'break', 'continue', 'return', 'goto',
    // Primitive types
    'int', 'char', 'void', 'float', 'double', 'short', 'long', 'signed', 'unsigned',
    // C△ types
    'dynam', 'string', 'struct', 'union', 'enum', 'typedef', 'auto', 'size_t',
    // Storage modifiers
    'const', 'volatile', 'static', 'extern', 'inline', 'register',
    // Imports
    'using', 'from', 'expose', 'space', 'as',
    // Other
    'sizeof',
];
const KEYWORD_DOCS = {
    // Control flow
    'if': 'If statement\n\n`if (condition) { }`',
    'else': 'Else clause\n\n`else { }`',
    'while': 'While loop\n\n`while (condition) { }`',
    'for': 'For loop\n\n`for (init; cond; incr) { }`',
    'do': 'Do-while loop\n\n`do { } while (cond)`',
    'switch': 'Switch statement\n\n`switch (x) { case 1: }`',
    'case': 'Case label\n\n`case value:`',
    'default': 'Default case\n\n`default:`',
    'break': 'Break out of loop or switch',
    'continue': 'Skip to next iteration',
    'return': 'Return from function\n\n`return value;`',
    'goto': 'Jump to label\n\n`goto label;`',
    // Primitive types
    'int': 'Integer type',
    'char': 'Character type',
    'void': 'Void type',
    'float': 'Floating point type',
    'double': 'Double precision float',
    'short': 'Short integer',
    'long': 'Long integer',
    'signed': 'Signed modifier',
    'unsigned': 'Unsigned modifier',
    // C△ types
    'dynam': 'Dynamic array\n\n`dynam int arr = [1, 2, 3]`\nMethods: `.push()`, `.pop()`, `.len()`',
    'string': 'First-class string\nSupports `+` concatenation and `{expr}` f-strings',
    'struct': 'Structure type\n\n`struct Point { int x; int y; }`',
    'union': 'Union type',
    'enum': 'Enumeration type',
    'typedef': 'Type definition',
    'auto': 'Auto type (inferred)',
    'size_t': 'Unsigned size type',
    // Storage modifiers
    'const': 'Constant qualifier\n\n`const int x = 5;`',
    'volatile': 'Volatile qualifier\n\n`volatile int* ptr;`',
    'static': 'Static storage duration',
    'extern': 'External linkage',
    'inline': 'Inline function hint',
    'register': 'Register storage hint',
    // Imports
    'using': 'Import\n\n`using "module"`, `using x from <plstd>`',
    'from': 'Import source\n\n`using printd from <plstd>`',
    'expose': 'Globalize symbols\n\n`expose plstd`',
    'space': 'Namespace block\n\n`space myname { }`\nAccess via `@`: `func@myname`',
    'as': 'Alias at import\n\n`using printd as pd from <plstd>`',
    // Other
    'sizeof': 'Size of expression or type',
};
function activate(context) {
    const selector = 'ctriangle';
    // Completion provider
    const comp = vscode.languages.registerCompletionItemProvider(selector, {
        provideCompletionItems(document, position) {
            const line = document.lineAt(position);
            const text = line.text.substring(0, position.character);
            const wordMatch = text.match(/[a-zA-Z_][a-zA-Z0-9_]*$/);
            const prefix = wordMatch ? wordMatch[0] : '';
            const items = [];
            for (const kw of KEYWORDS) {
                if (!prefix || kw.startsWith(prefix)) {
                    const item = new vscode.CompletionItem(kw, vscode.CompletionItemKind.Keyword);
                    item.detail = KEYWORD_DOCS[kw]?.split('\n')[0] || `Keyword: ${kw}`;
                    item.documentation = KEYWORD_DOCS[kw]
                        ? new vscode.MarkdownString(KEYWORD_DOCS[kw])
                        : undefined;
                    items.push(item);
                }
            }
            return items;
        }
    }, '.');
    // Hover provider
    const hover = vscode.languages.registerHoverProvider(selector, {
        provideHover(document, position) {
            const range = document.getWordRangeAtPosition(position);
            if (!range)
                return null;
            const word = document.getText(range);
            const doc = KEYWORD_DOCS[word];
            if (!doc)
                return null;
            return new vscode.Hover(new vscode.MarkdownString(`**${word}**\n\n${doc}`));
        }
    });
    context.subscriptions.push(comp, hover);
}
exports.activate = activate;
//# sourceMappingURL=extension.js.map