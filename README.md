A contemporary, high-level assembly compiler with cross-platform support. Write assembly with high-level constructs (loops, conditionals, functions) while maintaining the power and control of assembly language.

## Key Features

- **High-Level Constructs**: `if/elif/else`, `for`, `while`, `func`, nested loops
- **Backend Abstraction**: Modular architecture supporting multiple platforms
- **Cross-Platform**: Native support for Windows, Linux, and macOS (x86-64)
- **ARM64 Support**: In-progress native Apple Silicon support
- **Standard Library**: Automatic dependency injection - only includes what you use
- **Inline Assembly**: Seamless NASM passthrough for low-level control
- **Smart Register Allocation**: Automatic allocation with callee-saved register preference

### Enhanced Cross-Compilation
- Windows (x86-64) - Working
- macOS (x86-64) - Working
- Linux (x86-64) - Partial (requires cross-linker)
- macOS (ARM64) - In progress

## Prerequisites

- **Python 3.8+**
- **NASM** - Assembly generation (x86-64)
- **GCC/Clang** - Linking executables
- **Cross-platform toolchains** (optional):
  - Windows: MinGW-w64 (`brew install mingw-w64`)
  - macOS: Xcode Command Line Tools
  - ARM64: Clang with ARM64 support

## Quick Start

### Basic Usage

```bash
# Compile and run
python3 main.py examples/hello.asm --build --run

# Cross-compile for different platforms
python3 main.py code.asm --build --target windows
python3 main.py code.asm --build --target macos
python3 main.py code.asm --build --target linux

# Specify architecture (x86_64 or arm64)
python3 main.py code.asm --build --target macos --arch arm64
```

### Global Installation (Optional)

```bash
chmod +x inshall.sh
sudo ./inshall.sh

# Use globally
casm examples/hello.asm --build --run
```

## Language Reference

### Control Flow

#### IF/ELIF/ELSE
```nasm
if rax == 10
    call println "Equal to 10"
elif rax > 10
    call println "Greater than 10"
else
    call println "Less than 10"
endif
```

#### FOR Loops
```nasm
; Simple range
for i = 0, 5
    call println i
endfor

; Nested loops
for outer = 1, 3
    for inner = 1, 2
        call print inner
    endfor
endfor
```

#### WHILE Loops
```nasm
mov rbx, 3
while rbx > 0
    call println rbx
    dec rbx
endwhile
```

### Functions

```nasm
func greet(name)
    call printf("Hello, %s\n", name)
    return
endfunc

func calculate_sum(a, b)
    mov rax, a
    add rax, b
    return
endfunc

; Call functions
call greet("World")
```

### I/O Operations

```nasm
; Print without newline
call print "Hello"

; Print with newline  
call println "Hello, World!"

; Print register values
call println rax

; Printf with formatting
call printf("Value: %d\n", 42)
```

### Inline Assembly

Any line not recognized as a high-level keyword passes through to NASM:

```nasm
section .text
    mov rax, 5          ; Raw NASM
    add rax, rbx        ; Raw NASM
    call println rax    ; High-level
```

### Project Structure

```
.
├── src/
│   ├── lexer.py          # Tokenization
│   ├── token.py          # Token definitions
│   ├── codegen.py        # Code generation
│   ├── backend.py        # Backend abstraction
│   └── builder.py        # Assembly & linking
├── utils/
│   ├── syntax.py         # Compiler & syntax checker
│   ├── cli.py            # CLI interface
│   └── formatter.py      # Output formatting
├── libs/
│   └── stdio.py          # Standard library
├── examples/             # Example programs
└── main.py              # Entry point
```

## Standard Library

The compiler automatically injects only the functions you use:

### I/O Functions
- `print` - Print without newline
- `println` - Print with newline
- `scan` - Read string input
- `scanint` - Read integer input

### String Functions
- `strlen` - String length
- `strcpy` - Copy string
- `strcmp` - Compare strings
- `strcat` - Concatenate strings

### Math Functions
- `abs` - Absolute value
- `min` - Minimum of two values
- `max` - Maximum of two values
- `pow` - Power/exponentiation

### Memory Functions
- `memset` - Set memory region
- `memcpy` - Copy memory region

## Cross-Platform Support

### Platform Matrix

| Platform | Arch    | Compile | Link | Execute |
|----------|---------|---------|------|---------|
| Windows  | x86-64  | Yes     | Yes  | Yes     |
| macOS    | x86-64  | Yes     | Yes  | Yes     |
| Linux    | x86-64  | Yes     | Partial | -    |
| macOS    | ARM64   | Partial | Partial | Partial |

### Cross-Compilation Examples

```bash
# From macOS to Windows
brew install mingw-w64 nasm
python3 main.py code.asm --build --target windows

# Native macOS
python3 main.py code.asm --build --target macos

# ARM64 (in progress)
python3 main.py code.asm --build --target macos --arch arm64
```

## Advanced Features

### Register Allocation
- Automatic allocation for loop variables and parameters
- Prefers callee-saved registers (r12-r15, rbx) for loop counters
- Prevents register clobbering across function calls

### String Handling
- Automatic `.data` section generation for string literals
- Single-character string comparisons converted to ASCII
- Support for multi-line strings with escape sequences

### Debug Mode
```bash
python3 main.py code.asm --build --debug
```
Generates debug symbols for GDB/LLDB debugging.

## Troubleshooting

### NASM not found
```bash
# macOS
brew install nasm

# Linux
sudo apt-get install nasm

# Windows
# Download from https://www.nasm.us/
```

### Linker errors
Ensure you have a working C compiler:
```bash
# macOS
xcode-select --install

# Linux
sudo apt-get install build-essential
```

### Windows executable won't run
Use Wine on macOS/Linux:
```bash
wine build/program.exe
```

## Future Roadmap

- Complete ARM64 standard library
- Implement `break` and `continue` statements
- Add array and pointer support
- Implement proper return value handling
- Add file I/O operations
- Memory allocation functions
- Optimization passes

## Contributing

Contributions welcome! Areas for improvement:

- **ARM64 Support**: Complete stdlib implementation
- **Optimization**: Register allocation, dead code elimination
- **Features**: Arrays, pointers, structs
- **Documentation**: More examples and tutorials
- **Testing**: Additional test cases

### How to Contribute

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## License

Experimental compiler project. See LICENSE for details.

## Contact

- **Issues**: Open an issue on GitHub
- **Pull Requests**: Contributions welcome
- **Questions**: Use discussions or issues

Made with care for assembly enthusiasts <3
