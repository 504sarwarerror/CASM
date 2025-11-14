A contemporary high-level front-end for NASM (Windows x64 focused) that accepts a C-like/assembly hybrid language and generates NASM assembly code. Write high-level constructs like loops, and conditionals while maintaining the power of assembly.

## Features

- High-level constructs: `if/elif/else`, `for`, `while`, `print`
- Built-in standard library: I/O, strings, math, arrays, memory operations
- Seamless inline assembly passthrough
- Windows x64 NASM output (adaptable to other platforms)
- Automatic register allocation for parameters and temporaries

## Prerequisites

- **Python 3.8+**
- **NASM** - for assembling produced `.asm` files into object files
- **Linker toolchain** (optional, for producing executables):
  - Windows: MSVC, MinGW-w64, or similar
  - macOS/Linux: `clang` or `gcc`
  - macOS cross-compile to Windows: `mingw-w64` (via Homebrew)

## Quick Start

### Basic Usage

```bash
# Compile to assembly only
python3 main.py examples/hello.asm -o out_compiled.asm

# Compile, build, and run
python3 main.py examples/hello.asm --build --run
```

### Install globally (optional)

You can install CASM system-wide using the provided installer script `inshall.sh` (optional). The installer will place a small wrapper/entrypoint in a system `PATH` directory (for example `/usr/local/bin`) so you can run the compiler from anywhere using the `casm` command.

Basic usage:

```bash
# make the installer executable
chmod +x inshall.sh

# run the installer (may require sudo to write to /usr/local/bin)
sudo ./inshall.sh

# afterwards you can run casm globally
casm examples/hello.asm --build --run
```

What the installer does (typical behavior):

- Copies an executable wrapper or entrypoint script to `/usr/local/bin/casm` (or another destination you pass to the script).
- Makes the wrapper executable and ensures the `build/` directory exists under the project when run from a repository clone.
- Optionally updates permissions and prints instructions for uninstallation.

If you prefer a manual install instead of using the script, you can create a symlink yourself:

```bash
# from the project root
sudo ln -s "$(pwd)/main.py" /usr/local/bin/casm
sudo chmod +x /usr/local/bin/casm
```

Notes:

- The installer is optional and provided as a convenience. Review the `inshall.sh` script before running it and adjust the destination if you do not want to write to `/usr/local/bin`.
- On systems where `/usr/local/bin` is not in the PATH for non-login shells, you may need to add it or choose a different location.

## Language Reference

### File Structure

Files are plain text assembly-like source files. The compiler recognizes:

- **High-level statements** - Recognized keywords that generate assembly
- **NASM passthrough** - Lines not starting with high-level keywords are emitted as raw NASM

### NASM Sections

Standard NASM sections are forwarded to the generated output:

```nasm
section .data    ; Initialized data (labels, strings)
section .bss     ; Uninitialized storage (resb/resq/etc.)
section .text    ; Assembly code and high-level constructs
```

## High-Level Constructs

### 1. Overview

This compiler exposes a small set of high-level control-flow constructs while allowing raw NASM lines to pass through unchanged. The high-level constructs are intentionally simple and operate on registers, immediates, identifiers and simple memory operands.

Key rules:

- Operands may be registers (e.g. `rax`, `al`), identifiers (labels/variables), numeric immediates, memory expressions (`[ident]` or `dword [ident]`), or string literals (quoted).
- String literals are emitted into the `.data` section as generated labels when used as arguments to stdlib functions (e.g. `call print "Hello"`).
- Comparisons support immediates and register/memory operands. A small convenience: comparing a single-character string literal to a byte-sized register (e.g. `if al == "."`) is supported — the compiler converts `"."` to the ASCII immediate `46` so the emitted `cmp` is valid.

### 2. Printing & I/O

Use the high-level `call` form to invoke runtime I/O helpers.

```nasm
; Print without newline
call print "Hello"

; Print with newline
call println "Hello, World!"

; Print register value
call println rax

; Print blank newline
call println
```

Notes:

- When you pass a string literal the compiler creates a data label and loads its address for you.
- When you pass a register or identifier the compiler moves the value into the appropriate calling-register before invoking the helper.

### 3. Control Flow (if / elif / else)

Syntax:

```nasm
if <left> <comp> <right>
    ; true block
elif <left> <comp> <right>
    ; elif block
else
    ; else block
endif
```

Where:

- `<left>` / `<right>` are operands: registers, identifiers, numbers, or (in some cases) string literals.
- `<comp>` is one of: `==`, `!=`, `<`, `>`, `<=`, `>=`.

Examples:

```nasm
if rax == 0
    call println "zero"
elif rax == 1
    call println "one"
else
    call println "other"
endif

; Single-character string comparison against a byte register
if al == "."
    ; this is treated as `cmp al, 46` ('.' == 46)
endif
```

Behavior details:

- If both sides are numeric immediates (e.g. `if 1 == 0`) the compiler evaluates the condition at compile-time and may elide the branch.
- If one side is a register or memory operand the compiler emits a `cmp` followed by an appropriate conditional jump.
- Multi-character string comparisons are not supported by emitting a direct `cmp` to immediates — they require a runtime string-compare helper. See the "String comparisons" note below.

String comparisons:

- Only single-character string literals compared to a register are automatically converted to their ASCII numeric value.
- Comparing two strings (or a multi-character literal against a buffer/identifier) requires a runtime helper such as `strcmp`. You can call such helpers from high-level code, but you must ensure the helper is available (see "Stdlib & externs" below).

### 4. For Loops

Syntax (inclusive-range):

```nasm
for <var> = <start>, <end>
    ; loop body
endfor
```

Alternative comparison-style:

```nasm
for <var> <comp> <operand>
    ; treated as start=0, end=<operand>
endfor
```

Examples:

```nasm
for rcx = 1, 3
    call println rcx
endfor

; Using a specific register name (try to request r12d as loop counter)
for r12d = 0, [n_vis_tiles_x]
    ; loop body
endfor
```

Register allocation notes:

- The compiler will try to reserve the register you specify (e.g. `r12d`) when possible. If the requested register is unavailable because the compiler already used it for other mappings, the allocator will choose an alternative callee-saved register (e.g. `r9d`). If you require strict use of a particular register, avoid conflicting uses elsewhere in the function or use raw assembly lines to manage registers explicitly.
- By default the compiler prefers callee-saved registers (r8..r15, rbx) for loop counters so they survive function calls inside the loop body.

### 5. While Loops

Syntax:

```nasm
while <left> <comp> <right>
    ; loop body
endwhile
```

Example:

```nasm
while rbx > 0
    dec rbx
endwhile
```

The same operand and comparison rules from `if` apply to `while`.

### 6. Loop Control

Inside loops you may use:

```nasm
break       ; Exit the loop immediately
continue    ; Skip to next iteration
```

These keywords are validated by the compiler and generate the appropriate jumps.

### 7. Variables & Registers

- Use registers as your primary storage (`rax`, `rbx`, `rcx`, `al`, `r12d`, ...).
- The compiler performs simple register allocation for loop variables and function parameters; for predictable register usage prefer explicit raw assembly where needed.

### 8. Inline Assembly

Any line not recognized as a high-level keyword is passed through verbatim. This lets you drop down to raw NASM for performance-sensitive code.

```nasm
section .text
    mov rax, 5          ; Raw NASM instruction
    add rax, rbx        ; Another raw instruction
    call println rax    ; High-level call
```

## Standard Library

The compiler automatically injects only the standard library routines you actually use. No bloat.

### I/O Functions

| Function  | Description                        |
| --------- | ---------------------------------- |
| `print`   | Print string/value without newline |
| `println` | Print string/value with newline    |
| `scan`    | Read string input                  |
| `scanint` | Read integer input                 |

Important: including stdlib helper implementations in the generated asm
file requires an explicit `extern` declaration in your source. For
example, to ensure the `print` helper is defined in the output, add this
near the top of your file:

```nasm
extern print
extern println
```

This repository's build step only emits stdlib wrapper implementations when
the user explicitly declares them with `extern`. This avoids auto-defining
library stubs unexpectedly when analyzing multiple sources or included files.

### String Functions

| Function | Description         |
| -------- | ------------------- |
| `strlen` | Get string length   |
| `strcpy` | Copy string         |
| `strcmp` | Compare strings     |
| `strcat` | Concatenate strings |

### Math Functions

| Function | Description           |
| -------- | --------------------- |
| `abs`    | Absolute value        |
| `min`    | Minimum of two values |
| `max`    | Maximum of two values |
| `pow`    | Power/exponentiation  |

### Array Functions

| Function    | Description           |
| ----------- | --------------------- |
| `arraysum`  | Sum array elements    |
| `arrayfill` | Fill array with value |
| `arraycopy` | Copy array            |

### Memory Functions

| Function | Description        |
| -------- | ------------------ |
| `memset` | Set memory region  |
| `memcpy` | Copy memory region |

### Utility Functions

| Function | Description            |
| -------- | ---------------------- |
| `rand`   | Generate random number |
| `sleep`  | Sleep/delay execution  |

## Examples

### Example 1: Simple Function and Call

```nasm
func greet(name)
    call print "Hello, "
    call println name
    return
endfunc

call greet("world")
```

### Example 2: For Loop

```nasm
for rcx = 1, 3
    call println rcx
endfor
```

**Output:**

```
1
2
3
```

### Example 3: Inline Assembly Passthrough

```nasm
section .text
    mov rax, 5      ; Raw NASM instruction
    add rax, 10     ; Another raw instruction
    call println rax ; High-level construct
```

### Example 4: Conditional Logic

```nasm
mov rax, 42

if rax > 40
    call println "Greater than 40"
elif rax > 20
    call println "Greater than 20"
else
    call println "20 or less"
endif
```

## Limitations & Caveats

- **Platform focus**: Primarily designed for Windows x64 NASM output
- **Windows API dependencies**: Some stdlib functions assume Windows APIs (`WriteConsoleA`, etc.)
- **Register allocation**: Simple register allocator may have conflicts with heavy variable usage
- **String literals**: Automatically emitted into `.data` section with generated labels

### Adapting for Other Platforms

To target Linux/macOS, modify the standard library in `libs/stdio.py` to use appropriate syscalls or libc functions instead of Windows API calls.

## Project Structure

```
.
├── src/
│   ├── lexer.py          # Tokenization
│   ├── token.py          # Token type definitions
│   └── codegen.py        # Code generation
├── utils/
│   └── syntax.py         # Compiler & syntax checker
├── libs/
│   └── stdio.py          # Standard library
├── examples/             # Example programs
└── main.py              # Entry point
```

## Extending the Compiler

### Adding New Features

1. **Define tokens**: Add token types in `src/token.py`
2. **Update lexer**: Modify tokenization logic in `src/lexer.py`
3. **Update syntax checker**: Add validation in `utils/syntax.py`
4. **Implement codegen**: Add generation logic in `src/codegen.py`

### Adding Standard Library Functions

Add new functions to `libs/stdio.py` following the existing pattern. The compiler will automatically inject them when used.

## Troubleshooting

### Common Issues

**Problem**: `nasm: command not found`  
**Solution**: Install NASM for your platform:

- Windows: Download from [nasm.us](https://www.nasm.us/)
- macOS: `brew install nasm`
- Linux: `sudo apt-get install nasm` or `sudo yum install nasm`

**Problem**: Linker errors during build  
**Solution**: Ensure you have a working C compiler/linker:

- Windows: Install Visual Studio Build Tools or MinGW-w64
- macOS/Linux: Install Xcode Command Line Tools or GCC

**Problem**: Compilation succeeds but executable doesn't run  
**Solution**: Verify your target platform matches your execution environment (Windows x64)

## Contributing

Contributions are welcome! Areas for improvement:

- **Lexer enhancements**: Better error messages, more token types
- **Parser robustness**: Edge case handling, error recovery
- **Code generation**: Improved register allocation, optimization passes
- **Cross-platform support**: Linux/macOS stdlib implementations
- **Documentation**: More examples, tutorials

### How to Contribute

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## License

This project is a small experimental compiler front-end. See LICENSE file for details.

## Contact

- Issues: Open an issue on the project repository
- Pull Requests: Contributions welcome
- Questions: Use the discussion board or issues
