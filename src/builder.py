import subprocess
import shutil
import os
import shlex


class Builder:
    def __init__(self, compiled_file, verbose=False, target='windows', linker_flags=''):
        self.compiled_file = compiled_file
        self.verbose = verbose
        self.target = target  # 'windows', 'linux', 'macos'
        # linker_flags is a single string (e.g. "-L/path -lSDL2 -lSDL2main -mwindows")
        self.linker_flags = linker_flags or ''
    
    def log(self, message):
        if self.verbose:
            print(message)
    
    def assemble_and_link(self):
        print(f"[*] Building executable from {self.compiled_file}...")
        
        obj_ext = '.obj' if self.target == 'windows' else '.o'
        exe_ext = '.exe' if self.target == 'windows' else ''

        obj_file = self.compiled_file.replace('.asm', obj_ext)
        exe_file = self.compiled_file.replace('.asm', exe_ext)
        
        self.log(f"[*] Assembling {self.compiled_file}...")
        if not self.assemble_file(self.compiled_file, obj_file):
            return False
        
        print(f"[+] Assembled: {obj_file}")
        
        self.log(f"[*] Linking {exe_file}...")
        if not self.link_files(obj_file, exe_file):
            return False
        
        print(f"[+] Executable created: {exe_file}")
        print(f"[+] Build successful!")
        return True
    
    def assemble_file(self, asm_file, obj_file):
        # Choose NASM output format based on target
        fmt = 'win64' if self.target == 'windows' else ('elf64' if self.target == 'linux' else 'macho64')
        nasm_cmd = ['nasm', '-f', fmt, asm_file, '-o', obj_file]
        
        try:
            result = subprocess.run(nasm_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"[!] NASM assembly failed:")
                print(result.stderr)
                return False
            
            return True
        
        except FileNotFoundError:
            print("[!] Error: NASM not found!")
            print("    Install from: https://www.nasm.us/")
            return False
        
        except Exception as e:
            print(f"[!] Assembly error: {e}")
            return False
    
    def link_files(self, obj_file, exe_file):
        # Linking depends on target and toolchain availability
        try:
            if self.target == 'windows':
                # Prefer mingw-w64 cross-compiler if available
                cross_gcc = shutil.which('x86_64-w64-mingw32-gcc') or shutil.which('x86_64-w64-mingw32-clang')
                if cross_gcc:
                    link_cmd = [cross_gcc, obj_file, '-o', exe_file, '-m64']
                else:
                    # Fallback to host gcc (may fail to produce a Win32 exe on non-Windows hosts)
                    host_gcc = shutil.which('gcc')
                    if host_gcc:
                        print("[!] Warning: mingw-w64 cross-compiler not found. Trying host gcc (may fail).")
                        link_cmd = [host_gcc, obj_file, '-o', exe_file, '-m64']
                    else:
                        print("[!] Error: No suitable GCC found to link Windows executable.")
                        print("    Install mingw-w64 on macOS: brew install mingw-w64 nasm")
                        return False

            elif self.target == 'linux':
                # Link for Linux ELF; host gcc is preferred
                host_gcc = shutil.which('gcc')
                if host_gcc:
                    link_cmd = [host_gcc, obj_file, '-o', exe_file]
                else:
                    print("[!] Error: GCC not found for linking Linux executable.")
                    print("    Install GCC (e.g., brew install gcc or apt install build-essential)")
                    return False

            elif self.target == 'macos':
                # macOS linking: try clang
                host_clang = shutil.which('clang') or shutil.which('gcc')
                if host_clang:
                    link_cmd = [host_clang, obj_file, '-o', exe_file]
                else:
                    print("[!] Error: clang/gcc not found for linking macOS executable.")
                    return False

            else:
                print(f"[!] Unsupported target: {self.target}")
                return False

            # If user provided extra linker flags, split them safely and append
            if self.linker_flags:
                try:
                    extra = shlex.split(self.linker_flags)
                except Exception:
                    extra = self.linker_flags.split()
                link_cmd.extend(extra)

            self.log(f"[*] Running linker: {' '.join(link_cmd)}")
            result = subprocess.run(link_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"[!] Linking failed:")
                if result.stderr:
                    print(result.stderr)
                if result.stdout:
                    print(result.stdout)
                # Helpful message for Windows cross-compile
                if self.target == 'windows':
                    print("    If you're on macOS, install mingw-w64: brew install mingw-w64 nasm")
                return False

            return True

        except Exception as e:
            print(f"[!] Linking error: {e}")
            return False
    
    def run_executable(self):
        exe_file = self.compiled_file.replace('.asm', '.exe')
        
        if not os.path.exists(exe_file):
            print(f"[!] Executable not found: {exe_file}")
            return False
        
        print(f"[*] Running {exe_file}...")
        print("=" * 50)
        
        try:
            result = subprocess.run([exe_file], capture_output=False)
            print("=" * 50)
            print(f"[*] Program exited with code: {result.returncode}")
            return True
        
        except Exception as e:
            print(f"[!] Runtime error: {e}")
            return False
