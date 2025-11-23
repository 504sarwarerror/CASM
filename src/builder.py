import subprocess
import shutil
import os
import shlex
from utils.cli import CLI


class Builder:
    def __init__(self, compiled_file, verbose=False, target='windows', linker_flags='', debug=False, arch='x86_64'):
        self.compiled_file = compiled_file
        self.verbose = verbose
        self.target = target  # 'windows', 'linux', 'macos'
        self.arch = arch  # 'x86_64', 'arm64'
        # linker_flags is a single string (e.g. "-L/path -lSDL2 -lSDL2main -mwindows")
        self.linker_flags = linker_flags or ''
        # When debug=True, pass NASM debug flags (e.g. -gcv8 -F cv8) for richer
        # debug info in the object file. Only meaningful for certain targets.
        self.debug = bool(debug)
    
    def log(self, message):
        if self.verbose:
            CLI.info(message)
    
    def assemble_and_link(self):
        # Check if the input is a C file (from the new C-to-ASM feature)
        if self.compiled_file.lower().endswith('.c'):
            return self.compile_c_file()

        obj_ext = '.obj' if self.target == 'windows' else '.o'
        exe_ext = '.exe' if self.target == 'windows' else ''

        # If the compiled_file is the generated asm named like <build>/<name>-gen.asm
        # we want the object and executable to be <build>/<name>.obj and <build>/<name>.exe
        if self.compiled_file.endswith('-gen.asm'):
            base_no_gen = self.compiled_file[:-len('-gen.asm')]
        else:
            base_no_gen = os.path.splitext(self.compiled_file)[0]

        obj_file = base_no_gen + obj_ext
        exe_file = base_no_gen + exe_ext
        
        with CLI.spinner(f"Building {os.path.basename(exe_file)}..."):
            self.log(f"Assembling {self.compiled_file}...")
            if not self.assemble_file(self.compiled_file, obj_file):
                return False
            
            self.log(f"Linking {exe_file}...")
            if not self.link_files(obj_file, exe_file):
                return False
        
        CLI.success(f"Built {os.path.basename(exe_file)}")
        return True

    def compile_c_file(self):
        exe_ext = '.exe' if self.target == 'windows' else ''
        
        # Determine output executable name
        if self.compiled_file.endswith('-gen.c'):
            base_no_gen = self.compiled_file[:-len('-gen.c')]
        else:
            base_no_gen = os.path.splitext(self.compiled_file)[0]
            
        exe_file = base_no_gen + exe_ext
        
        with CLI.spinner(f"Compiling {os.path.basename(exe_file)}..."):
            self.log(f"Compiling {self.compiled_file} with GCC/Clang...")
            
            # Determine compiler command
            cmd = []
            if self.target == 'windows':
                 # Prefer mingw-w64 cross-compiler if available
                cross_gcc = shutil.which('x86_64-w64-mingw32-gcc') or shutil.which('x86_64-w64-mingw32-clang')
                if cross_gcc:
                    cmd = [cross_gcc, self.compiled_file, '-o', exe_file, '-m64']
                else:
                    host_gcc = shutil.which('gcc')
                    if host_gcc:
                        CLI.warning("mingw-w64 cross-compiler not found. Trying host gcc (may fail).")
                        cmd = [host_gcc, self.compiled_file, '-o', exe_file, '-m64']
                    else:
                        CLI.error("No suitable GCC found to compile Windows executable.")
                        return False
            else:
                # Linux/macOS
                compiler = shutil.which('gcc') or shutil.which('clang')
                if not compiler:
                    CLI.error("GCC or Clang not found.")
                    return False
                cmd = [compiler, self.compiled_file, '-o', exe_file]
                if self.target == 'linux':
                    cmd.append('-m64')

            # Add debug flags
            if self.debug:
                cmd.append('-g')
                
            # Add user linker flags (which might include include paths or libs)
            if self.linker_flags:
                try:
                    extra = shlex.split(self.linker_flags)
                except Exception:
                    extra = self.linker_flags.split()
                cmd.extend(extra)
            
            self.log(f"Running: {' '.join(cmd)}")
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    CLI.error("Compilation failed:")
                    print(result.stderr)
                    return False
            except Exception as e:
                CLI.error(f"Compilation error: {e}")
                return False
                
        CLI.success(f"Built {os.path.basename(exe_file)}")
        return True
    
    def assemble_file(self, asm_file, obj_file):
        # ARM64 uses clang as assembler (.s files), x86_64 uses NASM (.asm files)
        if self.arch == 'arm64':
            # Use clang to assemble ARM64 .s files
            clang_cmd = ['clang', '-c', asm_file, '-o', obj_file, '-arch', 'arm64']
            if self.debug:
                clang_cmd.append('-g')
            
            try:
                result = subprocess.run(clang_cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    CLI.error("Clang assembly failed:")
                    print(result.stderr)
                    return False
                
                return True
            
            except FileNotFoundError:
                CLI.error("Clang not found!")
                print("    Install Xcode Command Line Tools: xcode-select --install")
                return False
            
            except Exception as e:
                CLI.error(f"Assembly error: {e}")
                return False
        else:
            # x86_64: Use NASM
            # Choose NASM output format based on target
            fmt = 'win64' if self.target == 'windows' else ('elf64' if self.target == 'linux' else 'macho64')
            # Build base command
            nasm_cmd = ['nasm', '-f', fmt]
            # If requested, add NASM debug flags for Windows (cv8) which produces
            # CodeView debug information compatible with many Windows debuggers.
            if self.debug and self.target == 'windows':
                nasm_cmd.extend(['-gcv8', '-F', 'cv8'])
            
            # For macOS, add underscore prefix to all globals/externs automatically
            if self.target == 'macos':
                nasm_cmd.extend(['--prefix', '_'])

            # Enable multi-pass optimization to resolve label offsets
            # Use -Ox for maximum optimization passes (needed when --prefix changes label sizes)
            nasm_cmd.append('-Ox')

            nasm_cmd.extend([asm_file, '-o', obj_file])
            
            try:
                result = subprocess.run(nasm_cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    CLI.error("NASM assembly failed:")
                    print(result.stderr)
                    return False
                
                return True
            
            except FileNotFoundError:
                CLI.error("NASM not found!")
                print("    Install from: https://www.nasm.us/")
                return False
            
            except Exception as e:
                CLI.error(f"Assembly error: {e}")
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
                        CLI.warning("mingw-w64 cross-compiler not found. Trying host gcc (may fail).")
                        link_cmd = [host_gcc, obj_file, '-o', exe_file, '-m64']
                    else:
                        CLI.error("No suitable GCC found to link Windows executable.")
                        print("    Install mingw-w64 on macOS: brew install mingw-w64 nasm")
                        return False

            elif self.target == 'linux':
                # Link for Linux ELF; host gcc is preferred
                host_gcc = shutil.which('gcc')
                if host_gcc:
                    link_cmd = [host_gcc, obj_file, '-o', exe_file]
                else:
                    CLI.error("GCC not found for linking Linux executable.")
                    print("    Install GCC (e.g., brew install gcc or apt install build-essential)")
                    return False

            elif self.target == 'macos':
                # macOS linking: try clang
                host_clang = shutil.which('clang') or shutil.which('gcc')
                if host_clang:
                    link_cmd = [host_clang, obj_file, '-o', exe_file, '-arch', self.arch]
                else:
                    CLI.error("clang/gcc not found for linking macOS executable.")
                    return False

            else:
                CLI.error(f"Unsupported target: {self.target}")
                return False

            # If user provided extra linker flags, split them safely and append
            if self.linker_flags:
                try:
                    extra = shlex.split(self.linker_flags)
                except Exception:
                    extra = self.linker_flags.split()
                # If debug requested, add -g so the final binary contains
                # debug symbols and debuggers can locate source files.
                if self.debug:
                    # Place -g before user-supplied flags
                    link_cmd.append('-g')
                link_cmd.extend(extra)

            else:
                # No extra flags provided; still add -g if debug requested
                if self.debug:
                    link_cmd.append('-g')

            self.log(f"Running linker: {' '.join(link_cmd)}")
            result = subprocess.run(link_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                CLI.error("Linking failed:")
                if result.stderr:
                    print(result.stderr)
                if result.stdout:
                    print(result.stdout)
                return False

            return True

        except Exception as e:
            CLI.error(f"Linking error: {e}")
            return False
    
    def run_executable(self):
        # Use the same base-name logic as assemble_and_link to find the exe
        if self.compiled_file.endswith('-gen.asm'):
            base_no_gen = self.compiled_file[:-len('-gen.asm')]
        elif self.compiled_file.endswith('-gen.c'):
            base_no_gen = self.compiled_file[:-len('-gen.c')]
        else:
            base_no_gen = os.path.splitext(self.compiled_file)[0]

        exe_file = base_no_gen + ('.exe' if self.target == 'windows' else '')

        if exe_file and not os.path.exists(exe_file):
            CLI.error(f"Executable not found: {exe_file}")
            return False
        
        CLI.info(f"Running {exe_file}...")
        print("=" * 50)
        
        try:
            result = subprocess.run([exe_file], capture_output=False)
            print("=" * 50)
            CLI.info(f"Program exited with code: {result.returncode}")
            return True
        
        except Exception as e:
            CLI.error(f"Runtime error: {e}")
            return False
