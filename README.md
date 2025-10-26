A contemporary high-level front-end for NASM (Windows x64 focused) that accepts a C-like/assembly hybrid language and generates NASM assembly code. Write high-level constructs like functions, loops, and conditionals while maintaining the power of assembly.

## Features

- High-level constructs: `if/elif/else`, `for`, `while`, `func`, `call`
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

### 1. Printing & I/O

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

### 2. Functions

#### Defining Functions

```nasm
func my_function(name)
    call println name
    return
endfunc
```

#### Calling Functions

Two calling conventions are supported:

```nasm
; Space-separated arguments
call my_function "hello"

; Parenthesized arguments
call my_function("hello")
```

#### Function Details

- **Parameter limit**: Up to 4 parameters supported
- **Parameter mapping**: Mapped to `RCX`, `RDX`, `R8`, `R9` on Windows x64
- **Local parameters**: Parameter names become local identifiers, remapped to callee-saved registers (`r12`, `r13`, etc.)
- **Return**: Use `return` keyword to exit early; functions end with `ret` in generated assembly

### 3. Control Flow

#### If/Elif/Else

```nasm
if rax == 0
    call println "zero"
elif rax == 1
    call println "one"
else
    call println "other"
endif
```

**Supported operators**: `==`, `!=`, `<`, `>`, `<=`, `>=`

#### For Loops

Inclusive range loops:

```nasm
for rcx = 1, 5
    call println rcx
endfor
```

The loop variable is assigned a register internally to survive function calls.

#### While Loops

```nasm
while rbx > 0
    ; loop body
    dec rbx
endwhile
```

#### Loop Control

```nasm
break       ; Exit the loop immediately
continue    ; Skip to next iteration
```

### 4. Variables & Registers

- The language expects you to use **registers** for storage (`rax`, `rbx`, `rcx`, etc.)
- High-level constructs automatically manage value movement between registers and temporaries
- No explicit variable declaration needed - registers are your variables

### 5. Inline Assembly

Any line not recognized as a high-level keyword is passed through verbatim:

```nasm
section .text
    mov rax, 5          ; Raw NASM instruction
    add rax, rbx        ; Another raw instruction
    ; Mix with high-level constructs
    call println rax
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

- **Parameter limit**: Function calls support up to 4 arguments (Windows x64 calling convention: `RCX`, `RDX`, `R8`, `R9`)
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
