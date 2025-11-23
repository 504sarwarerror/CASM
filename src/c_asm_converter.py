import re

class CAsmConverter:
    def __init__(self, source):
        self.source = source
        self.lines = source.split('\n')
        self.output_lines = []
        
        # x86 Register mapping to sizes (for suffix determination)
        self.registers = {
            # 64-bit
            'rax': 'q', 'rbx': 'q', 'rcx': 'q', 'rdx': 'q', 'rsi': 'q', 'rdi': 'q', 'rbp': 'q', 'rsp': 'q',
            'r8': 'q', 'r9': 'q', 'r10': 'q', 'r11': 'q', 'r12': 'q', 'r13': 'q', 'r14': 'q', 'r15': 'q',
            # 32-bit
            'eax': 'l', 'ebx': 'l', 'ecx': 'l', 'edx': 'l', 'esi': 'l', 'edi': 'l', 'ebp': 'l', 'esp': 'l',
            'r8d': 'l', 'r9d': 'l', 'r10d': 'l', 'r11d': 'l', 'r12d': 'l', 'r13d': 'l', 'r14d': 'l', 'r15d': 'l',
            # 16-bit
            'ax': 'w', 'bx': 'w', 'cx': 'w', 'dx': 'w', 'si': 'w', 'di': 'w', 'bp': 'w', 'sp': 'w',
            'r8w': 'w', 'r9w': 'w', 'r10w': 'w', 'r11w': 'w', 'r12w': 'w', 'r13w': 'w', 'r14w': 'w', 'r15w': 'w',
            # 8-bit
            'al': 'b', 'bl': 'b', 'cl': 'b', 'dl': 'b', 'ah': 'b', 'bh': 'b', 'ch': 'b', 'dh': 'b',
            'sil': 'b', 'dil': 'b', 'bpl': 'b', 'spl': 'b',
            'r8b': 'b', 'r9b': 'b', 'r10b': 'b', 'r11b': 'b', 'r12b': 'b', 'r13b': 'b', 'r14b': 'b', 'r15b': 'b',
            # Segment registers
            'cs': 'w', 'ds': 'w', 'es': 'w', 'fs': 'w', 'gs': 'w', 'ss': 'w',
            # Control registers
            'cr0': 'q', 'cr2': 'q', 'cr3': 'q', 'cr4': 'q', 'cr8': 'q',
            # Debug registers
            'dr0': 'q', 'dr1': 'q', 'dr2': 'q', 'dr3': 'q', 'dr6': 'q', 'dr7': 'q',
            # SIMD (MMX, SSE, AVX) - Suffix logic might differ, but mapping them helps identification
            'mm0': 'q', 'mm1': 'q', 'mm2': 'q', 'mm3': 'q', 'mm4': 'q', 'mm5': 'q', 'mm6': 'q', 'mm7': 'q',
            'xmm0': 'x', 'xmm1': 'x', 'xmm2': 'x', 'xmm3': 'x', 'xmm4': 'x', 'xmm5': 'x', 'xmm6': 'x', 'xmm7': 'x',
            'xmm8': 'x', 'xmm9': 'x', 'xmm10': 'x', 'xmm11': 'x', 'xmm12': 'x', 'xmm13': 'x', 'xmm14': 'x', 'xmm15': 'x',
            'ymm0': 'y', 'ymm1': 'y', 'ymm2': 'y', 'ymm3': 'y', 'ymm4': 'y', 'ymm5': 'y', 'ymm6': 'y', 'ymm7': 'y',
            'ymm8': 'y', 'ymm9': 'y', 'ymm10': 'y', 'ymm11': 'y', 'ymm12': 'y', 'ymm13': 'y', 'ymm14': 'y', 'ymm15': 'y',
        }

        # Instructions that write to the first operand (dest)
        self.write_ops = {
            'mov', 'add', 'sub', 'imul', 'idiv', 'inc', 'dec', 'neg', 'not', 
            'and', 'or', 'xor', 'shl', 'shr', 'sar', 'rol', 'ror', 'lea', 'pop',
            'adc', 'sbb', 'movsx', 'movzx', 'xchg', 'cmpxchg', 'xadd',
            'movaps', 'movups', 'movdqa', 'movdqu', 'movss', 'movsd',
            'addps', 'addpd', 'addss', 'addsd', 'subps', 'subpd', 'subss', 'subsd',
            'mulps', 'mulpd', 'mulss', 'mulsd', 'divps', 'divpd', 'divss', 'divsd',
            'xorps', 'xorpd', 'andps', 'andpd', 'orps', 'orpd',
            'fld', 'fst', 'fstp', 'fadd', 'fsub', 'fmul', 'fdiv', 'fild', 'fist', 'fistp',
            'cvtsi2ss', 'cvttss2si', 'cvtsi2sd', 'cvttsd2si',
            'stos', 'stosb', 'stosw', 'stosd', 'stosq',
            'movs', 'movsb', 'movsw', 'movsd', 'movsq',
            'scas', 'scasb', 'scasw', 'scasd', 'scasq',
            'lods', 'lodsb', 'lodsw', 'lodsd', 'lodsq'
        }
        
        # Instructions that read from the first operand (dest) as well (Read-Modify-Write)
        self.rmw_ops = {
            'add', 'sub', 'imul', 'idiv', 'inc', 'dec', 'neg', 'not', 
            'and', 'or', 'xor', 'shl', 'shr', 'sar', 'rol', 'ror',
            'adc', 'sbb', 'xchg', 'cmpxchg', 'xadd',
            'addps', 'addpd', 'addss', 'addsd', 'subps', 'subpd', 'subss', 'subsd',
            'mulps', 'mulpd', 'mulss', 'mulsd', 'divps', 'divpd', 'divss', 'divsd',
            'xorps', 'xorpd', 'andps', 'andpd', 'orps', 'orpd',
            'fadd', 'fsub', 'fmul', 'fdiv'
        }
        
        # Instructions that only read (no write)
        self.read_ops = {
            'cmp', 'test', 'push', 'ucomiss', 'ucomisd', 'comiss', 'comisd',
            'call', 'jmp', 'je', 'jne', 'jg', 'jge', 'jl', 'jle', 'ja', 'jae', 'jb', 'jbe', 'jz', 'jnz',
            'jo', 'jno', 'js', 'jns', 'jp', 'jnp', 'jpe', 'jpo', 'jcxz', 'jecxz', 'jrcxz',
            'loop', 'loope', 'loopne', 'loopz', 'loopnz',
            'nop', 'hlt', 'cli', 'sti', 'cld', 'std', 'wait', 'int', 'iret', 'ret', 'leave',
            'syscall', 'sysenter', 'sysexit', 'cpuid', 'rdtsc',
            'div', 'mul',
            'cmps', 'cmpsb', 'cmpsw', 'cmpsd', 'cmpsq'
        }




    def convert(self):
        i = 0
        while i < len(self.lines):
            line = self.lines[i]
            
            if self.is_assembly_line(line):
                # Start of a block
                block_lines = []
                # Look ahead to capture the full block
                while i < len(self.lines):
                    current_line = self.lines[i]
                    stripped = current_line.strip()
                    
                    # Check if it's an assembly line
                    if self.is_assembly_line(current_line):
                        block_lines.append(current_line)
                        i += 1
                        continue
                    
                    # Check if it's a comment or blank line (sticky if inside block)
                    # But we need to be careful not to consume C comments that are followed by C code
                    if not stripped or stripped.startswith('//') or stripped.startswith('/*'):
                        # Peek next line to see if it's assembly
                        # If next line is assembly, then this comment/blank is part of the block
                        # If next line is C, then this comment/blank ends the block (or belongs to C)
                        
                        # Look ahead for next non-empty/non-comment line
                        j = i + 1
                        next_is_asm = False
                        while j < len(self.lines):
                            next_line = self.lines[j].strip()
                            if not next_line or next_line.startswith('//') or next_line.startswith('/*'):
                                j += 1
                                continue
                            
                            if self.is_assembly_line(self.lines[j]):
                                next_is_asm = True
                            break
                        
                        if next_is_asm:
                            block_lines.append(current_line)
                            i += 1
                            continue
                        else:
                            # End of block
                            break
                    
                    # Not assembly and not sticky -> End of block
                    break
                
                # Process the collected block
                if block_lines:
                    asm_code = self.process_asm_block(block_lines)
                    self.output_lines.append(asm_code)
            else:
                self.output_lines.append(line)
                i += 1
        
        return '\n'.join(self.output_lines)

    def is_assembly_line(self, line):
        stripped = line.strip()
        if not stripped:
            return False
        if stripped.startswith('//') or stripped.startswith('/*'):
            return False
        if stripped.endswith(';'):
            return False
        if '{' in stripped or '}' in stripped:
            return False
        if stripped.startswith('#'):
            return False
        
        # Check for labels (ending with :)
        if stripped.endswith(':'):
            # Ensure it's not a C case label or default
            if stripped.startswith('case ') or stripped == 'default:':
                return False
            return True

        # Check for known mnemonics
        first_word = stripped.split()[0].lower()
        
        # Handle REP prefixes
        if first_word in ['rep', 'repe', 'repz', 'repne', 'repnz']:
            parts = stripped.split(None, 1)
            if len(parts) > 1:
                first_word = parts[1].split()[0].lower()
            else:
                return False # Just 'rep'?
        
        if first_word in self.write_ops or first_word in self.read_ops or first_word in self.rmw_ops:
            return True
            
        return False

    def process_asm_block(self, lines):
        converted_lines = []
        variables = {} # var_name -> {'index': i, 'read': bool, 'write': bool}
        clobbers = set()
        
        for line in lines:
            stripped = line.strip()
            # Preserve comments
            comment = ""
            if '//' in stripped:
                parts = stripped.split('//', 1)
                stripped = parts[0].strip()
                comment = " //" + parts[1]
            
            if not stripped:
                continue

            # Handle labels
            if stripped.endswith(':'):
                converted_lines.append(f'"{stripped}\\n"')
                continue

            # Parse mnemonic and operands
            parts = stripped.split(None, 1)
            mnemonic = parts[0].lower()
            
            # Handle REP prefixes
            prefix = ""
            if mnemonic in ['rep', 'repe', 'repz', 'repne', 'repnz']:
                prefix = mnemonic + " "
                # The actual instruction is the next part
                if len(parts) > 1:
                    sub_parts = parts[1].split(None, 1)
                    mnemonic = sub_parts[0].lower()
                    if len(sub_parts) > 1:
                        operands_str = sub_parts[1]
                    else:
                        operands_str = ""
                else:
                    # Just a prefix on a line? Weird but possible in source
                    continue
            else:
                operands_str = parts[1] if len(parts) > 1 else ""
            
            operands = []
            if operands_str:
                # Split by comma, respecting potential brackets (simple split for now)
                operands = [op.strip() for op in operands_str.split(',')]
            
            # Determine suffix
            suffix = ""
            # Jumps and calls usually don't need a size suffix in AT&T unless indirect
            # SIMD instructions also usually don't need suffixes (or have them built-in)
            no_suffix_ops = {
                'jmp', 'je', 'jne', 'jg', 'jge', 'jl', 'jle', 'call',
                'cvtsi2ss', 'cvttss2si', 'cvtsi2sd', 'cvttsd2si',
                'movss', 'movsd', 'addss', 'addsd', 'subss', 'subsd',
                'mulss', 'mulsd', 'divss', 'divsd',
                'movaps', 'movups', 'movdqa', 'movdqu',
                'addps', 'addpd', 'subps', 'subpd', 'mulps', 'mulpd', 'divps', 'divpd',
                'xorps', 'xorpd', 'andps', 'andpd', 'orps', 'orpd',
                'movsb', 'movsw', 'movsd', 'movsq',
                'stosb', 'stosw', 'stosd', 'stosq',
                'scasb', 'scasw', 'scasd', 'scasq',
                'lodsb', 'lodsw', 'lodsd', 'lodsq',
                'cmpsb', 'cmpsw', 'cmpsd', 'cmpsq'
            }
            
            if mnemonic in no_suffix_ops:
                suffix = ""
            else:
                size_found = False
                
                # Check for explicit size directives in operands
                for op in operands:
                    op_lower = op.lower()
                    if 'byte' in op_lower:
                        suffix = 'b'
                        size_found = True
                        break
                    elif 'word' in op_lower and 'dword' not in op_lower and 'qword' not in op_lower:
                        suffix = 'w'
                        size_found = True
                        break
                    elif 'dword' in op_lower:
                        suffix = 'l'
                        size_found = True
                        break
                    elif 'qword' in op_lower:
                        suffix = 'q'
                        size_found = True
                        break
                
                if not size_found:
                    # Check operands for registers to determine size
                    for op in operands:
                        # Strip size directives first (though we checked them above)
                        clean_op = re.sub(r'\b(byte|word|dword|qword|xmmword|ymmword)(\s+ptr)?\s+', '', op, flags=re.IGNORECASE)
                        if clean_op.lower() in self.registers:
                            suffix = self.registers[clean_op.lower()]
                            size_found = True
                            break
                
                if not size_found:
                    # Default to 'l' (32-bit)
                    suffix = 'l' 

            # Convert mnemonic
            att_mnemonic = prefix + mnemonic + suffix
            
            # Process operands
            att_operands = []
            
            # Intel: op dest, src
            # AT&T: op src, dest
            # So we reverse the operands
            
            # Process operands
            att_operands = []
            
            # Intel: op dest, src
            # AT&T: op src, dest
            # So we reverse the operands
            
            # Determine read/write status for variables
            # Op 0 (Intel dest)
            if len(operands) > 0:
                dest = operands[0]
                is_write = mnemonic in self.write_ops
                is_read = mnemonic in self.rmw_ops or mnemonic in self.read_ops
                
                if mnemonic == 'mov':
                    is_read = False # dest is overwrite
                
                self.track_operand(dest, is_read, is_write, variables, clobbers, mnemonic)
            
            # Op 1 (Intel src)
            if len(operands) > 1:
                src = operands[1]
                self.track_operand(src, True, False, variables, clobbers, mnemonic) # src is always read
            
            # Handle implicit clobbers for string instructions
            if mnemonic.startswith('movs') or mnemonic.startswith('stos') or mnemonic.startswith('scas') or mnemonic.startswith('lods') or mnemonic.startswith('cmps'):
                clobbers.add('rcx')
                clobbers.add('rdi')
                clobbers.add('rsi')
                if mnemonic.startswith('stos') or mnemonic.startswith('scas') or mnemonic.startswith('lods'):
                    clobbers.add('rax') # Accumulator often used
                
                # Also, these modify memory implicitly, so we should add "memory" clobber
                clobbers.add('memory')

            # Convert operands to AT&T format
            for op in operands:
                att_op = self.convert_operand(op, variables, mnemonic)
                att_operands.append(att_op)
            
            # Reverse operands for AT&T
            att_operands.reverse()
            
            asm_line = f'"{att_mnemonic} {", ".join(att_operands)};"{comment}'
            converted_lines.append(asm_line)

        # Build __asm__ block
        asm_code = "    __asm__(\n        " + "\n        ".join(converted_lines)
        
        # Outputs
        outputs = []
        inputs = []
        
        sorted_vars = sorted(variables.items(), key=lambda item: item[1]['index'])
        
        # Reconstruct indices logic...
        new_indices = {}
        current_idx = 0
        final_outputs = []
        final_inputs = []
        
        # First pass: Outputs
        for name, info in sorted_vars:
            if info['write']: # Covers =r and +r
                constraint = "+r" if info['read'] else "=r"
                final_outputs.append(f'"{constraint}"({name})')
                new_indices[name] = current_idx
                current_idx += 1
        
        # Second pass: Inputs (read-only)
        for name, info in sorted_vars:
            if not info['write'] and info['read']:
                final_inputs.append(f'"r"({name})')
                new_indices[name] = current_idx
                current_idx += 1
                
        # Update placeholders in converted lines
        final_lines = []
        for line in converted_lines:
            temp_line = line
            for name, idx in new_indices.items():
                # Use regex to replace whole word to avoid partial matches
                # Also handle the % prefix we added in convert_operand
                # The operand in the string is "%name"
                temp_line = re.sub(f'%{re.escape(name)}\\b', f'%{idx}', temp_line)
            final_lines.append(temp_line)

        asm_code = "    __asm__(\n        " + "\n        ".join(final_lines)
        asm_code += "\n        : " + ", ".join(final_outputs)
        asm_code += "\n        : " + ", ".join(final_inputs)
        
        if clobbers:
            clobbers_list = [f'"{c}"' for c in sorted(clobbers)]
            asm_code += "\n        : " + ", ".join(clobbers_list)
        
        asm_code += "\n    );"
        
        return asm_code

    def normalize_register(self, reg):
        reg = reg.lower()
        # Map sub-registers to 64-bit parent
        mapping = {
            'eax': 'rax', 'ax': 'rax', 'al': 'rax', 'ah': 'rax',
            'ebx': 'rbx', 'bx': 'rbx', 'bl': 'rbx', 'bh': 'rbx',
            'ecx': 'rcx', 'cx': 'rcx', 'cl': 'rcx', 'ch': 'rcx',
            'edx': 'rdx', 'dx': 'rdx', 'dl': 'rdx', 'dh': 'rdx',
            'esi': 'rsi', 'si': 'rsi', 'sil': 'rsi',
            'edi': 'rdi', 'di': 'rdi', 'dil': 'rdi',
            'ebp': 'rbp', 'bp': 'rbp', 'bpl': 'rbp',
            'esp': 'rsp', 'sp': 'rsp', 'spl': 'rbp', # rsp/spl usually not clobbered explicitly but...
            'r8d': 'r8', 'r8w': 'r8', 'r8b': 'r8',
            'r9d': 'r9', 'r9w': 'r9', 'r9b': 'r9',
            'r10d': 'r10', 'r10w': 'r10', 'r10b': 'r10',
            'r11d': 'r11', 'r11w': 'r11', 'r11b': 'r11',
            'r12d': 'r12', 'r12w': 'r12', 'r12b': 'r12',
            'r13d': 'r13', 'r13w': 'r13', 'r13b': 'r13',
            'r14d': 'r14', 'r14w': 'r14', 'r14b': 'r14',
            'r15d': 'r15', 'r15w': 'r15', 'r15b': 'r15',
        }
        return mapping.get(reg, reg)

    def track_operand(self, op, is_read, is_write, variables, clobbers, mnemonic):
        # Strip size directives
        op = re.sub(r'\b(byte|word|dword|qword|xmmword|ymmword)(\s+ptr)?\s+', '', op, flags=re.IGNORECASE)
        
        # Handle memory operands [expr]
        if '[' in op and ']' in op:
            # Extract content inside brackets
            match = re.search(r'\[(.*?)\]', op)
            if match:
                content = match.group(1)
                tokens = re.split(r'[\+\-\*\s]+', content)
                for token in tokens:
                    if not token: continue
                    if token.isdigit(): continue
                    if token.lower() in self.registers:
                        pass
                    else:
                        # Check for SYMBOL(var)
                        if 'SYMBOL(' in token:
                            # Don't track as variable input
                            pass
                        else:
                            self.track_variable(token, True, False, variables)
            return

        # Direct operand (register, immediate, or variable)
        op_lower = op.lower()
        if op_lower in self.registers:
            if is_write:
                clobbers.add(self.normalize_register(op_lower))
            return
        
        if op.isdigit() or (op.startswith('-') and op[1:].isdigit()):
            return
            
        # Ignore labels for jump/call instructions
        if mnemonic in ['jmp', 'je', 'jne', 'jg', 'jge', 'jl', 'jle', 'call']:
             return

        # Check for SYMBOL(var)
        if 'SYMBOL(' in op:
            return

        # Assume variable
        self.track_variable(op, is_read, is_write, variables)

    def track_variable(self, name, is_read, is_write, variables):
        if not name: return
        # Don't lowercase name to preserve C variable case
        if name not in variables:
            variables[name] = {'index': len(variables), 'read': False, 'write': False}
        
        if is_read:
            variables[name]['read'] = True
        if is_write:
            variables[name]['write'] = True

    def convert_operand(self, op, variables, mnemonic):
        # Strip size directives
        op = re.sub(r'\b(byte|word|dword|qword|xmmword|ymmword)(\s+ptr)?\s+', '', op, flags=re.IGNORECASE)
        
        # Handle memory operands [expr]
        if '[' in op and ']' in op:
            match = re.search(r'\[(.*?)\]', op)
            if match:
                content = match.group(1)
                # Convert Intel [base + index*scale + disp] to AT&T disp(base, index, scale)
                
                base = None
                index = None
                scale = 1
                disp = ""
                
                # Handle SYMBOL(var) in displacement
                # We replace SYMBOL(var) with var(%rip) logic or just var
                # If user writes [SYMBOL(var)], we want var(%rip) or just var
                
                # Split by + (ignoring - for now, assuming simple addition)
                parts = [p.strip() for p in content.split('+')]
                
                for part in parts:
                    # Check for scale *
                    if '*' in part:
                        subparts = part.split('*')
                        if subparts[0].strip().lower() in self.registers:
                            index = f"%%{subparts[0].strip().lower()}"
                            scale = subparts[1].strip()
                        elif subparts[1].strip().lower() in self.registers:
                            index = f"%%{subparts[1].strip().lower()}"
                            scale = subparts[0].strip()
                    elif part.lower() in self.registers:
                        if base is None:
                            base = f"%%{part.lower()}"
                        else:
                            index = f"%%{part.lower()}"
                    else:
                        # Displacement or variable
                        if part.isdigit():
                            disp = part
                        elif part.startswith('SYMBOL(') and part.endswith(')'):
                            # Extract symbol name
                            sym_name = part[7:-1]
                            disp = f"{sym_name}(%%rip)" # PC-relative addressing for globals
                        else:
                            # Variable
                            # If it's a variable tracked in variables, use %name
                            if part in variables:
                                disp = f"%{part}"
                            else:
                                # Maybe a number?
                                disp = part
                
                # Construct AT&T string
                res = ""
                if disp:
                    res += disp
                
                if base or index:
                    res += "("
                    if base:
                        res += base
                    if index:
                        res += f", {index}"
                        if scale != 1:
                            res += f", {scale}"
                    res += ")"
                
                return res

        # Direct operand
        op_lower = op.lower()
        if op_lower in self.registers:
            return f"%%{op_lower}"
        
        if op.isdigit() or (op.startswith('-') and op[1:].isdigit()):
            return f"${op}"
            
        # If it's a jump/call target, return it as is
        if mnemonic in ['jmp', 'je', 'jne', 'jg', 'jge', 'jl', 'jle', 'call']:
            return op

        # Check for SYMBOL(var)
        if op.startswith('SYMBOL(') and op.endswith(')'):
            return f"{op[7:-1]}(%%rip)"

        # If variable, return %name
        return f"%{op}"

