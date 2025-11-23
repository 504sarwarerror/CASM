from abc import ABC, abstractmethod

class Backend(ABC):
    def __init__(self, target='windows', bits=64):
        self.target = target
        self.bits = bits
        self.output = []
        self.data_section = []
        self.label_counter = 0

    def get_output(self):
        return self.output

    def get_data_section(self):
        return self.data_section

    def get_label(self):
        label = f".L{self.label_counter}"
        self.label_counter += 1
        return label

    @abstractmethod
    def prologue(self, name, params):
        pass

    @abstractmethod
    def epilogue(self):
        pass

    @abstractmethod
    def mov(self, dest, src):
        pass

    @abstractmethod
    def add(self, dest, src):
        pass

    @abstractmethod
    def sub(self, dest, src):
        pass
    
    @abstractmethod
    def mul(self, dest, src):
        pass

    @abstractmethod
    def call(self, name):
        pass

    @abstractmethod
    def ret(self):
        pass

    @abstractmethod
    def label(self, name):
        pass

    @abstractmethod
    def jump(self, label):
        pass

    @abstractmethod
    def compare(self, op1, op2):
        pass

    @abstractmethod
    def cond_jump(self, condition, label):
        pass
    
    @abstractmethod
    def push(self, reg):
        pass
        
    @abstractmethod
    def pop(self, reg):
        pass
    
    @abstractmethod
    def emit_raw(self, line):
        pass
    
    @abstractmethod
    def emit_string_data(self, label, string_value):
        """Emit a string data declaration with architecture-specific syntax"""
        pass
    
    @abstractmethod
    def load_address(self, dest_reg, label):
        """Load the address of a label into a register"""
        pass
    
    @abstractmethod
    def call_function(self, name):
        """Call a function by name"""
        pass
    
    @abstractmethod
    def emit_extern(self, name):
        """Emit an external symbol declaration"""
        pass
    
    @abstractmethod
    def emit_data_section(self):
        """Emit data section directive"""
        pass
    
    @abstractmethod
    def emit_text_section(self):
        """Emit text section directive"""
        pass


class X86Backend(Backend):
    def __init__(self, target='windows', bits=64):
        super().__init__(target, bits)
        self.register_map = {}
        # Calling convention registers
        if self.target == 'windows':
            self.arg_regs = ['rcx', 'rdx', 'r8', 'r9']
        else:
            # System V AMD64 (Linux/macOS)
            self.arg_regs = ['rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9']

    def emit_raw(self, line):
        self.output.append(line)

    def label(self, name):
        self.output.append(f"{name}:")

    def prologue(self, name, params):
        self.output.append(f"\nglobal {name}")
        self.output.append(f"{name}:")
        if self.bits == 64:
            self.output.append("    push rbp")
            self.output.append("    mov rbp, rsp")
        else:
            self.output.append("    push ebp")
            self.output.append("    mov ebp, esp")

    def epilogue(self):
        if self.bits == 64:
            self.output.append("    pop rbp")
        else:
            self.output.append("    pop ebp")
        self.output.append("    ret")

    def mov(self, dest, src):
        self.output.append(f"    mov {dest}, {src}")

    def add(self, dest, src):
        self.output.append(f"    add {dest}, {src}")

    def sub(self, dest, src):
        self.output.append(f"    sub {dest}, {src}")
        
    def mul(self, dest, src):
        # x86 imul is complex, simplified for now
        self.output.append(f"    imul {dest}, {src}")

    def call(self, name):
        self.output.append(f"    call {name}")

    def ret(self):
        self.epilogue()

    def jump(self, label):
        self.output.append(f"    jmp {label}")

    def compare(self, op1, op2):
        self.output.append(f"    cmp {op1}, {op2}")

    def cond_jump(self, condition, label):
        # condition map: 'eq' -> 'je', 'ne' -> 'jne', etc.
        cond_map = {
            '==': 'je', '!=': 'jne',
            '<': 'jl', '<=': 'jle',
            '>': 'jg', '>=': 'jge'
        }
        asm_op = cond_map.get(condition, 'jmp')
        self.output.append(f"    {asm_op} {label}")
        
    def push(self, reg):
        self.output.append(f"    push {reg}")
        
    def pop(self, reg):
        self.output.append(f"    pop {reg}")
    
    def emit_string_data(self, label, string_value):
        """Emit NASM-style string data"""
        self.data_section.append(f"{label} db `{string_value}`, 0")
    
    def load_address(self, dest_reg, label):
        """Load effective address (LEA) for x86-64"""
        self.output.append(f"    lea {dest_reg}, [rel {label}]")
    
    def call_function(self, name):
        """Call a function (x86-64)"""
        self.output.append(f"    call {name}")
    
    def emit_extern(self, name):
        """Emit NASM extern declaration"""
        self.output.append(f"extern {name}")
    
    def emit_data_section(self):
        """Emit NASM data section"""
        self.output.append("section .data")
    
    def emit_text_section(self):
        """Emit NASM text section"""
        self.output.append("section .text")


class ARM64Backend(Backend):
    def __init__(self, target='macos', bits=64):
        super().__init__(target, bits)
        # ARM64 registers: x0-x7 are args
        self.arg_regs = [f'x{i}' for i in range(8)]

    def emit_raw(self, line):
        self.output.append(line)

    def label(self, name):
        self.output.append(f"{name}:")

    def prologue(self, name, params):
        self.output.append(f"\n.global _{name}")
        self.output.append(f".align 2")
        self.output.append(f"_{name}:")
        # Standard frame: stp fp, lr, [sp, #-16]!
        # fp = x29, lr = x30
        self.output.append("    stp x29, x30, [sp, #-16]!")
        self.output.append("    mov x29, sp")

    def epilogue(self):
        self.output.append("    ldp x29, x30, [sp], #16")
        self.output.append("    ret")

    def mov(self, dest, src):
        # ARM64 mov is 'mov x0, x1' or 'mov x0, #10'
        if str(src).isdigit():
            self.output.append(f"    mov {dest}, #{src}")
        else:
            self.output.append(f"    mov {dest}, {src}")

    def add(self, dest, src):
        if str(src).isdigit():
            self.output.append(f"    add {dest}, {dest}, #{src}")
        else:
            self.output.append(f"    add {dest}, {dest}, {src}")

    def sub(self, dest, src):
        if str(src).isdigit():
            self.output.append(f"    sub {dest}, {dest}, #{src}")
        else:
            self.output.append(f"    sub {dest}, {dest}, {src}")
            
    def mul(self, dest, src):
        self.output.append(f"    mul {dest}, {dest}, {src}")

    def call(self, name):
        # macOS expects underscore prefix for C functions
        self.output.append(f"    bl _{name}")

    def ret(self):
        # Set return value to 0 for main function
        self.output.append("    mov x0, #0")
        self.epilogue()

    def jump(self, label):
        self.output.append(f"    b {label}")

    def compare(self, op1, op2):
        if str(op2).isdigit():
            self.output.append(f"    cmp {op1}, #{op2}")
        else:
            self.output.append(f"    cmp {op1}, {op2}")

    def cond_jump(self, condition, label):
        # condition map: '==' -> 'b.eq', etc.
        cond_map = {
            '==': 'b.eq', '!=': 'b.ne',
            '<': 'b.lt', '<=': 'b.le',
            '>': 'b.gt', '>=': 'b.ge'
        }
        asm_op = cond_map.get(condition, 'b')
        self.output.append(f"    {asm_op} {label}")
        
    def push(self, reg):
        # ARM64 push is str reg, [sp, #-16]! (16-byte aligned)
        self.output.append(f"    str {reg}, [sp, #-16]!")

    def pop(self, reg):
        self.output.append(f"    ldr {reg}, [sp], #16")
    
    def emit_string_data(self, label, string_value):
        """Emit ARM64-style string data"""
        # ARM64 uses .asciz directive
        # Need to escape the string properly for ARM64 assembly
        escaped = string_value.replace('\\', '\\\\').replace('"', '\\"')
        self.data_section.append(f"{label}: .asciz \"{escaped}\"")
    
    def load_address(self, dest_reg, label):
        """Load address using ADRP + ADD for ARM64"""
        # ARM64 uses page-relative addressing
        self.output.append(f"    adrp {dest_reg}, {label}@PAGE")
        self.output.append(f"    add {dest_reg}, {dest_reg}, {label}@PAGEOFF")
    
    def call_function(self, name):
        """Call a function (ARM64) - macOS requires underscore prefix"""
        if name.startswith('_'):
            self.output.append(f"    bl {name}")
        else:
            self.output.append(f"    bl _{name}")
    
    def emit_extern(self, name):
        """Emit ARM64 extern declaration (GAS syntax)"""
        # ARM64 on macOS uses .extern with underscore prefix
        self.output.append(f".extern _{name}")
    
    def emit_data_section(self):
        """Emit ARM64 data section (GAS syntax)"""
        self.output.append(".data")
    
    def emit_text_section(self):
        """Emit ARM64 text section (GAS syntax)"""
        self.output.append(".text")
