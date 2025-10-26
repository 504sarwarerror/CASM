This is an contemporary high-level front-end for NASM (Windows x64 focused) that accepts a small, C-like/assembly hybrid language and generates NASM assembly. It supports high-level constructs (if/for/while/func/call), a standard library (print/scan/strings/math)

## Prerequisites

- Python 3.8+
- NASM (for assembling produced .asm into object files)
- A linker toolchain if you want to produce executables (on macOS/Linux: clang/gcc; on macOS to cross-compile Windows: mingw-w64 via Homebrew)

To compile a sample program:

```bash
# compile to assembly only
python3 main.py examples/hello.asm -o out_compiled.asm

# compile and attempt to build and run (requires nasm + linker)
python3 main.py examples/hello.asm --build --run
```

```bash
export PYTHONDONTWRITEBYTECODE=1
```

## Language overview and syntax

Files are plain text assembly-like source files. The compiler recognizes two coarse areas: NASM sections and high-level statements. Lines that don't start with a recognized high-level keyword are treated as raw NASM lines (ASM passthrough).

## Sections (these are forwarded to the generated NASM):

- `section .data` — initialized data (define labels and strings)
- `section .bss` — uninitialized storage (resb/resq/etc.)
- `section .text` — low-level assembly / user-visible code (mostly optional: high-level constructs are emitted into .text)

## High-level statements

- Printing

  - call print "Hello" ; prints without newline
  - call println "Line" ; prints and appends a newline
  - call println rax ; print numeric register value then newline
  - call println ; prints a blank newline

- Functions

  - Define:

    func my_function(name)
    call println name
    return
    endfunc

  - Call (two forms supported):

    - `call my_function "hello"` (space-separated args)
    - `call my_function("hello")` (parenthesized args)

  - Notes:
    - Up to 4 parameters are supported (mapped to RCX, RDX, R8, R9 on the call site).
    - Parameter names become local identifiers inside the function and are remapped to callee-saved registers (r12/r13/...).
    - Functions return with `ret` in generated assembly (use `return` in high-level code to finish early).

- Control flow

  - If/Elif/Else:

    if rax == 0
    call println "zero"
    elif rax == 1
    call println "one"
    else
    call println "other"
    endif

    Supported comparison operators: `==`, `!=`, `<`, `>`, `<=`, `>=`.

  - For loops (inclusive end):

    for rcx = 1, 5
    call println rcx
    endfor

    The loop variable is assigned a register internally so it survives function calls.

  - While loops:

    while rbx > 0
    ; body
    endwhile

  - `break` and `continue` supported inside loops.

- Variable/register usage

  - The language expects you to use registers for storage (`rax`, `rbx`, `rcx`, etc.).
  - High-level constructs will move values between registers and generated temporaries as needed.

- Inline assembly
  - Any line not recognized as a high-level keyword is passed through verbatim into the generated assembly as an ASM line. This allows you to write low-level NASM instructions directly.

## Standard library

The compiler injects needed standard-library routines into the generated assembly only when used. Major helpers include:

- I/O: `print`, `println`, `scan`, `scan_int`
- Strings: `strlen`, `strcpy`, `strcmp`, `strcat`
- Math: `abs`, `min`, `max`, `pow`
- Arrays: `array_sum`, `array_fill`, `array_copy`
- Memory: `memset`, `memcpy`
- Other: `rand`, `sleep`

## Examples

1. Simple function and call:

   func greet(name)
   call print "Hello, "
   call println name
   return
   endfunc

   call greet("world")

2. For loop:

   for rcx = 1, 3
   call println rcx
   endfor

3. Inline ASM passthrough:

   section .text
   mov rax, 5 ; This is raw NASM emitted as-is

## Limitations & caveats

- Parameter passing supports up to 4 args (RCX/RDX/R8/R9). Additional args are not yet supported.
- The compiler focuses on Windows x64 NASM output. Some stdlib functions assume Windows APIs (WriteConsoleA, etc.). You can adapt the StandardLibrary in `libs/stdio.py` for other platforms.
- Strings passed as literal arguments are emitted into the `.data` section with generated labels.
- Variables are represented by registers and the simplistic register allocator used may clash if you try heavy variable usage; consider reviewing `src/codegen.py` if you add complex features.

## Extending the compiler

- Lexer: `src/lexer.py`
- Parser / syntax checks & compiler entrypoint: `utils/syntax.py` (contains `Compiler`)
- Codegen: `src/codegen.py`
- Standard library: `libs/stdio.py`

To add features, modify the lexer/token types in `src/token.py`, then update parsing/generation in `src/codegen.py` and the syntax checker.

Troubleshooting

- If compilation fails with external tool errors (nasm/gcc/clang missing), install the required tools for your platform.

## Contact / Contribution

Feel free to open issues or PRs. This project is a small experimental compiler front-end — contributions to the lexer, parser robustness, codegen (better register allocation), and cross-platform stdlib are all welcome.
