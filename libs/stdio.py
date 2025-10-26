class StandardLibrary:
    
    def __init__(self):
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
        
        # === I/O INITIALIZATION ===
        self.functions['_init_stdio'] = {
            'code': '''_init_stdio:
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
    sub rsp, 64
    push r12
    push r13
    mov r12, rcx
    xor rax, rax
    mov rdi, rcx
.count:
    cmp byte [rdi], 0
    je .write
    inc rax
    inc rdi
    jmp .count
.write:
    mov r13, rax
    test r13, r13
    jz .exit
    mov rcx, [rel _stdout_handle]
    mov rdx, r12
    mov r8, r13
    lea r9, [rel _bytes_written]
    mov qword [rsp+32], 0
    call WriteConsoleA
.exit:
    pop r13
    pop r12
    add rsp, 64
    pop rbp
    ret

_print_number:
    push rbp
    mov rbp, rsp
    sub rsp, 64
    push r12
    mov r12, rcx
    test r12, r12
    jns .pos
    push r12
    mov byte [rsp], 45
    mov byte [rsp+1], 0
    lea rcx, [rsp]
    call _print_string
    pop r12
    neg r12
.pos:
    lea rcx, [rel _number_buffer]
    lea rdx, [rel .fmt]
    mov r8, r12
    call sprintf
    lea rcx, [rel _number_buffer]
    call _print_string
    pop r12
    add rsp, 64
    pop rbp
    ret
.fmt db "%lld", 0

_print_hex:
    push rbp
    mov rbp, rsp
    sub rsp, 64
    lea rcx, [rel _number_buffer]
    lea rdx, [rel .fmt]
    mov r8, rcx
    call sprintf
    lea rcx, [rel _number_buffer]
    call _print_string
    add rsp, 64
    pop rbp
    ret
.fmt db "0x%llX", 0''',
            'bss': ['_bytes_written resd 1', '_number_buffer resb 64'],
            'externs': {'WriteConsoleA', 'sprintf'},
            'requires': ['_init_stdio']
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
            'requires': ['_init_stdio']
        }
        
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
        
        self.functions['strcpy'] = {
            'code': '''_strcpy:
    push r12
    mov r12, rcx
.loop:
    mov al, [rdx]
    mov [rcx], al
    test al, al
    jz .done
    inc rcx
    inc rdx
    jmp .loop
.done:
    mov rax, r12
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
        
        # === ARRAY FUNCTIONS ===
        self.functions['array_sum'] = {
            'code': '''_array_sum:
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
        
        self.functions['array_fill'] = {
            'code': '''_array_fill:
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
        
        self.functions['array_copy'] = {
            'code': '''_array_copy:
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
