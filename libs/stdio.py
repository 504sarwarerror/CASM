class StandardLibrary:
    
    def __init__(self, target='windows', arch='x86_64'):
        self.target = target
        self.arch = arch
        self.functions = {}
        self._init_library()
    
    def get_dependencies(self, used_functions):
        """Recursively get all dependencies"""
        code = []
        data = []
        bss = []
        externs = set()
        processed = set()
        
        def process_function(func_name):
            if func_name in processed or func_name not in self.functions:
                return
            
            processed.add(func_name)
            func_data = self.functions[func_name]
            
            # Process dependencies first
            if 'requires' in func_data:
                for req in func_data['requires']:
                    process_function(req)
            
            # Add function code
            if func_data['code']:
                code.append(func_data['code'])
            
            if 'data' in func_data:
                data.extend(func_data['data'])
            if 'bss' in func_data:
                bss.extend(func_data['bss'])
            if 'externs' in func_data:
                externs.update(func_data['externs'])
        
        for func in used_functions:
            process_function(func)
        
        return {
            'code': '\n\n'.join(code),
            'data': data,
            'bss': bss,
            'externs': externs
        }
    
    def _init_library(self):
        """Initialize all library functions"""
        if self.target == 'windows':
            self._init_windows()
        else:
            self._init_libc()

    def _init_libc(self):
        # === I/O INITIALIZATION (libc handles this) ===
        self.functions['initstdio'] = {
            'code': '''_initstdio:
    ret''',
            'externs': set()
        }

        # === PRINT FUNCTIONS ===
        if self.arch == 'arm64':
            # ARM64 version using printf from libc
            # Note: printf is variadic, so arguments must be passed on the stack
            self.functions['print'] = {
                'code': '''_print_string:
    ; x0 has string pointer
    ; printf("%s", str) - variadic, so arg goes on stack
    sub sp, sp, #32
    stp x29, x30, [sp, #16]
    add x29, sp, #16
    mov x8, x0          ; save string pointer
    mov x9, sp
    str x8, [x9]        ; store string pointer on stack
    adrp x0, _fmt_str@PAGE
    add x0, x0, _fmt_str@PAGEOFF
    bl _printf
    ldp x29, x30, [sp, #16]
    add sp, sp, #32
    ret

_print_number:
    ; x0 has number
    ; printf("%lld", num) - variadic, so arg goes on stack
    sub sp, sp, #32
    stp x29, x30, [sp, #16]
    add x29, sp, #16
    mov x8, x0          ; save number
    mov x9, sp
    str x8, [x9]        ; store number on stack
    adrp x0, _fmt_num@PAGE
    add x0, x0, _fmt_num@PAGEOFF
    bl _printf
    ldp x29, x30, [sp, #16]
    add sp, sp, #32
    ret

_print_hex:
    ; x0 has number
    sub sp, sp, #32
    stp x29, x30, [sp, #16]
    add x29, sp, #16
    mov x8, x0
    mov x9, sp
    str x8, [x9]
    adrp x0, _fmt_hex@PAGE
    add x0, x0, _fmt_hex@PAGEOFF
    bl _printf
    ldp x29, x30, [sp, #16]
    add sp, sp, #32
    ret''',
                'data': ['_fmt_str: .asciz "%s"', '_fmt_num: .asciz "%lld"', '_fmt_hex: .asciz "0x%llX"'],
                'externs': {'printf'},
                'requires': ['initstdio']
            }
        else:
            # x86-64 version
            self.functions['print'] = {
                'code': '''_print_string:
    ; RDI/RCX has string pointer
    ; printf("%s", str)
    sub rsp, 8
    mov rsi, rdi  ; string to 2nd arg
    lea rdi, [rel .fmt] ; format to 1st arg
    xor rax, rax  ; no vector args
    call printf
    add rsp, 8
    ret
.fmt db "%s", 0

_print_number:
    ; RDI/RCX has number
    sub rsp, 8
    mov rsi, rdi  ; number to 2nd arg
    lea rdi, [rel .fmt]
    xor rax, rax
    call printf
    add rsp, 8
    ret
.fmt db "%lld", 0

_print_hex:
    sub rsp, 8
    mov rsi, rdi
    lea rdi, [rel .fmt]
    xor rax, rax
    call printf
    add rsp, 8
    ret
.fmt db "0x%llX", 0''',
                'externs': {'printf'},
                'requires': ['initstdio']
            }


        if self.arch == 'arm64':
            self.functions['println'] = {
                'code': '',
                'data': ['_newline_str: .asciz "\\n"'],
                'requires': ['print']
            }
        else:
            self.functions['println'] = {
                'code': '',
                'data': ['_newline_str db 10, 0'],
                'requires': ['print']
            }

        # === INPUT FUNCTIONS ===
        self.functions['scan'] = {
            'code': '''_scan_string:
    ; RDI = buffer, RSI = size
    ; fgets(buffer, size, stdin)
    sub rsp, 8
    mov rdx, [rel stdin] ; 3rd arg
    ; rdi and rsi are already correct for fgets(char *s, int size, FILE *stream)
    call fgets
    
    ; Remove newline if present
    mov rdi, rax ; result buffer
    test rdi, rdi
    jz .done
    call _strlen
    cmp rax, 0
    je .done
    mov rdx, rax
    dec rdx
    cmp byte [rdi + rdx], 10
    jne .done
    mov byte [rdi + rdx], 0
.done:
    add rsp, 8
    ret''',
            'externs': {'fgets', 'stdin', 'strlen'},
            'requires': ['initstdio']
        }
        # Note: _strlen is internal, no prefix needed from libc

        self.functions['scanint'] = {
            'code': '''_scanint:
    ; RDI = int pointer
    sub rsp, 8
    mov rsi, rdi ; pointer to 2nd arg
    lea rdi, [rel .fmt]
    xor rax, rax
    call scanf
    add rsp, 8
    ret
.fmt db "%lld", 0''',
            'externs': {'scanf'},
            'requires': ['initstdio']
        }

        # === STRING FUNCTIONS ===
        self._init_common_string_ops()

        # === MATH FUNCTIONS ===
        self._init_common_math_ops()

        # === ARRAY/MEMORY FUNCTIONS ===
        self._init_common_memory_ops()

        # === RANDOM NUMBER ===
        self.functions['rand'] = {
            'code': '''_rand:
    sub rsp, 8
    call rand
    add rsp, 8
    ret''',
            'externs': {'rand'}
        }

        # === SLEEP FUNCTION ===
        self.functions['sleep'] = {
            'code': '''_sleep:
    ; RDI has milliseconds
    ; usleep(ms * 1000)
    sub rsp, 8
    imul rdi, 1000
    call usleep
    add rsp, 8
    ret''',
            'externs': {'usleep'}
        }

    def _init_windows(self):
        # === I/O INITIALIZATION ===
        self.functions['initstdio'] = {
            'code': '''_initstdio:
    push rbp
    mov rbp, rsp
    sub rsp, 32
    mov rcx, -11
    call GetStdHandle
    mov [rel _stdout_handle], rax
    mov rcx, -10
    call GetStdHandle
    mov [rel _stdin_handle], rax
    add rsp, 32
    pop rbp
    ret''',
            'bss': ['_stdout_handle resq 1', '_stdin_handle resq 1'],
            'externs': {'GetStdHandle'}
        }
        
        # === PRINT FUNCTIONS ===
        self.functions['print'] = {
            'code': '''_print_string:
    push rbp
    mov rbp, rsp
    sub rsp, 32
    mov rdx, rcx  ; string to 2nd arg (rdx)
    lea rcx, [rel .fmt] ; format to 1st arg (rcx)
    call printf
    add rsp, 32
    pop rbp
    ret
.fmt db "%s", 0

_print_number:
    push rbp
    mov rbp, rsp
    sub rsp, 32
    mov rdx, rcx  ; number to 2nd arg (rdx)
    lea rcx, [rel .fmt] ; format to 1st arg (rcx)
    call printf
    add rsp, 32
    pop rbp
    ret
.fmt db "%lld", 0

_print_hex:
    push rbp
    mov rbp, rsp
    sub rsp, 32
    mov rdx, rcx
    lea rcx, [rel .fmt]
    call printf
    add rsp, 32
    pop rbp
    ret
.fmt db "0x%llX", 0''',
            'externs': {'printf'},
            'requires': []
        }
        
        self.functions['println'] = {
            'code': '',
            'data': ['_newline_str db 10, 0'],
            'requires': ['print']
        }
        
        # === INPUT FUNCTIONS ===
        self.functions['scan'] = {
            'code': '''_scan_string:
    push rbp
    mov rbp, rsp
    sub rsp, 64
    push r12
    push r13
    mov r12, rcx
    mov r13, rdx
    mov rcx, [rel _stdin_handle]
    mov rdx, r12
    mov r8, r13
    lea r9, [rel _bytes_read]
    mov qword [rsp+32], 0
    call ReadConsoleA
    mov rax, [rel _bytes_read]
    cmp rax, 0
    jle .done
    lea rdi, [r12 + rax - 1]
.trim:
    cmp rax, 0
    jle .done
    movzx rcx, byte [rdi]
    cmp cl, 13
    je .cut
    cmp cl, 10
    je .cut
    jmp .done
.cut:
    mov byte [rdi], 0
    dec rdi
    dec rax
    jmp .trim
.done:
    mov byte [r12 + rax], 0
    pop r13
    pop r12
    add rsp, 64
    pop rbp
    ret

_scan_int:
    push rbp
    mov rbp, rsp
    sub rsp, 288
    push r12
    mov r12, rcx
    lea rcx, [rsp+32]
    mov rdx, 256
    call _scan_string
    lea rcx, [rsp+32]
    lea rdx, [rel .fmt]
    mov r8, r12
    call sscanf
    pop r12
    add rsp, 288
    pop rbp
    ret
.fmt db "%lld", 0''',
            'bss': ['_bytes_read resd 1'],
            'externs': {'ReadConsoleA', 'sscanf'},
            'requires': ['initstdio']
        }

        self._init_common_string_ops()
        self._init_common_math_ops()
        self._init_common_memory_ops()

        # === RANDOM NUMBER ===
        self.functions['rand'] = {
            'code': '''_rand:
    push rbp
    mov rbp, rsp
    sub rsp, 32
    call rand
    add rsp, 32
    pop rbp
    ret''',
            'externs': {'rand'}
        }
        
        # === SLEEP FUNCTION ===
        self.functions['sleep'] = {
            'code': '''_sleep:
    push rbp
    mov rbp, rsp
    sub rsp, 32
    call Sleep
    add rsp, 32
    pop rbp
    ret''',
            'externs': {'Sleep'}
        }

    def _init_common_string_ops(self):
        # === STRING FUNCTIONS ===
        self.functions['strlen'] = {
            'code': '''_strlen:
    xor rax, rax
    mov rdi, rcx
.loop:
    cmp byte [rdi], 0
    je .done
    inc rax
    inc rdi
    jmp .loop
.done:
    ret''',
            'externs': set()
        }
        
        self.functions['scanint'] = {
            'code': '''_scanint:
    push r12
    mov r12, rcx
.loop:
    mov al, [rdx]
    mov [rcx], al
    test al, al
    jz .done
    call _scan_string
    inc rdx
    jmp .loop
.done:
    call sscanf
    pop r12
    ret''',
            'externs': set()
        }
        
        self.functions['strcmp'] = {
            'code': '''_strcmp:
.loop:
    mov al, [rcx]
    mov dl, [rdx]
    cmp al, dl
    jne .neq
    test al, al
    jz .eq
    inc rcx
    inc rdx
    jmp .loop
.eq:
    xor rax, rax
    ret
.neq:
    movzx rax, al
    movzx rdx, dl
    sub rax, rdx
    ret''',
            'externs': set()
        }
        
        self.functions['strcat'] = {
            'code': '''_strcat:
    push r12
    push r13
    mov r12, rcx
    mov r13, rdx
.find:
    cmp byte [rcx], 0
    je .copy
    inc rcx
    jmp .find
.copy:
    mov al, [r13]
    mov [rcx], al
    test al, al
    jz .done
    inc rcx
    inc r13
    jmp .copy
.done:
    mov rax, r12
    pop r13
    pop r12
    ret''',
            'externs': set()
        }

    def _init_common_math_ops(self):
        # === MATH FUNCTIONS ===
        self.functions['abs'] = {
            'code': '''_abs:
    mov rax, rcx
    test rax, rax
    jns .done
    neg rax
.done:
    ret''',
            'externs': set()
        }
        
        self.functions['min'] = {
            'code': '''_min:
    mov rax, rcx
    cmp rcx, rdx
    jle .done
    mov rax, rdx
.done:
    ret''',
            'externs': set()
        }
        
        self.functions['max'] = {
            'code': '''_max:
    mov rax, rcx
    cmp rcx, rdx
    jge .done
    mov rax, rdx
.done:
    ret''',
            'externs': set()
        }
        
        self.functions['pow'] = {
            'code': '''_pow:
    push r12
    push r13
    mov r12, rcx
    mov r13, rdx
    mov rax, 1
    test r13, r13
    jz .done
.loop:
    imul rax, r12
    dec r13
    jnz .loop
.done:
    pop r13
    pop r12
    ret''',
            'externs': set()
        }

    def _init_common_memory_ops(self):
        # === ARRAY FUNCTIONS ===
        self.functions['arraysum'] = {
            'code': '''_arraysum:
    xor rax, rax
    test rdx, rdx
    jz .done
.loop:
    add rax, [rcx]
    add rcx, 8
    dec rdx
    jnz .loop
.done:
    ret''',
            'externs': set()
        }
        
        self.functions['arrayfill'] = {
            'code': '''_arrayfill:
    test rdx, rdx
    jz .done
.loop:
    mov [rcx], r8
    add rcx, 8
    dec rdx
    jnz .loop
.done:
    ret''',
            'externs': set()
        }
        
        self.functions['arraycopy'] = {
            'code': '''_arraycopy:
    test r8, r8
    jz .done
.loop:
    mov rax, [rdx]
    mov [rcx], rax
    add rcx, 8
    add rdx, 8
    dec r8
    jnz .loop
.done:
    ret''',
            'externs': set()
        }
        
        # === MEMORY FUNCTIONS ===
        self.functions['memset'] = {
            'code': '''_memset:
    push r12
    mov r12, rcx
    test r8, r8
    jz .done
.loop:
    mov [rcx], dl
    inc rcx
    dec r8
    jnz .loop
.done:
    mov rax, r12
    pop r12
    ret''',
            'externs': set()
        }
        
        self.functions['memcpy'] = {
            'code': '''_memcpy:
    push r12
    mov r12, rcx
    test r8, r8
    jz .done
.loop:
    mov al, [rdx]
    mov [rcx], al
    inc rcx
    inc rdx
    dec r8
    jnz .loop
.done:
    mov rax, r12
    pop r12
    ret''',
            'externs': set()
        }
