import sys
import time
import threading
import itertools

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    GREY = '\033[90m'
    MAGENTA = '\033[35m'

class Spinner:
    def __init__(self, message="Processing...", delay=0.1):
        self.spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
        self.delay = delay
        self.busy = False
        self.spinner_visible = False
        self.message = message
        sys.stdout.write(f"{Colors.CYAN}  {message} {Colors.ENDC}")
        sys.stdout.flush()

    def write_next(self):
        with self._screen_lock:
            if not self.spinner_visible:
                sys.stdout.write(next(self.spinner))
                self.spinner_visible = True
                sys.stdout.flush()

    def remove_spinner(self, cleanup=False):
        with self._screen_lock:
            if self.spinner_visible:
                sys.stdout.write('\b')
                self.spinner_visible = False
                if cleanup:
                    sys.stdout.write(' ')       # overwrite spinner with blank
                    sys.stdout.write('\r')      # return to start of line, NOT \n
                sys.stdout.flush()

    def spinner_task(self):
        while self.busy:
            self.write_next()
            time.sleep(self.delay)
            self.remove_spinner()

    def __enter__(self):
        self._screen_lock = threading.Lock()
        self.busy = True
        self.thread = threading.Thread(target=self.spinner_task)
        self.thread.start()
        return self

    def __exit__(self, exception, value, tb):
        self.busy = False
        self.remove_spinner(cleanup=True)
        self.thread.join()
        # Clear the line
        sys.stdout.write('\r' + ' ' * (len(self.message) + 10) + '\r')
        sys.stdout.flush()
        if exception:
            return False

class CLI:
    @staticmethod
    def print_banner():
        print()
        print(f"  {Colors.BOLD}{Colors.MAGENTA}CASM{Colors.ENDC} {Colors.GREY}v2.0{Colors.ENDC}")
        print(f"  {Colors.GREY}Advanced Assembly Compiler{Colors.ENDC}")
        print()
    
    @staticmethod
    def print_usage():
        print(f"{Colors.BOLD}Usage:{Colors.ENDC} {Colors.GREEN}casm{Colors.ENDC} {Colors.YELLOW}<input.asm>{Colors.ENDC} [options]")
        print()
        print(f"{Colors.BOLD}Options:{Colors.ENDC}")
        print(f"  {Colors.GREEN}-o <file>{Colors.ENDC}      Specify output file")
        print(f"  {Colors.GREEN}-e, --exe{Colors.ENDC}      Compile directly to .exe")
        print(f"  {Colors.GREEN}--build{Colors.ENDC}        Assemble and link to executable")
        print(f"  {Colors.GREEN}--target <t>{Colors.ENDC}   Target OS: windows (only 'windows' is supported)")
        print(f"  {Colors.GREEN}--run{Colors.ENDC}          Run after building")
        print(f"  {Colors.GREEN}-v, --verbose{Colors.ENDC}  Verbose output")
        print(f"  {Colors.GREEN}-h, --help{Colors.ENDC}     Show help")
        print()
        print(f"{Colors.BOLD}Examples:{Colors.ENDC}")
        print(f"  {Colors.CYAN}casm program.asm{Colors.ENDC}")
        print(f"  {Colors.CYAN}casm program.asm --build{Colors.ENDC}")
        print(f"  {Colors.CYAN}casm program.asm --exe --run{Colors.ENDC}")
        print(f"  {Colors.CYAN}casm program.asm -o output.asm -v{Colors.ENDC}")
    
    @staticmethod
    def error(msg):
        print(f"\r  {Colors.RED}✖{Colors.ENDC} {msg}")

    @staticmethod
    def warning(msg):
        print(f"\r  {Colors.YELLOW}⚠{Colors.ENDC} {msg}")

    @staticmethod
    def success(msg):
        print(f"\r  {Colors.GREEN}✔{Colors.ENDC} {msg}")

    @staticmethod
    def info(msg):
        print(f"\r  {Colors.BLUE}ℹ{Colors.ENDC} {msg}")
    
    @staticmethod
    def step(msg):
        print(f"\r  {Colors.CYAN}→{Colors.ENDC} {msg}")

    @staticmethod
    def spinner(message):
        return Spinner(message)

    @staticmethod
    def parse_args(args):
        if len(args) < 2:
            return None
        
        config = {
            'input_file': None,
            'output_file': None,
            'build': False,
            'exe': False,
            'run': False,
            'verbose': False,
            'debug': False,
            'target': 'windows',
            'arch': 'x86_64',
            'ldflags': '',
            'help': False
        }
        
        i = 1
        while i < len(args):
            arg = args[i]
            
            if arg in ['-h', '--help']:
                config['help'] = True
                return config
            
            elif arg == '-o':
                if i + 1 < len(args):
                    config['output_file'] = args[i + 1]
                    i += 2
                else:
                    CLI.error("-o requires filename")
                    return None
            
            elif arg in ['-e', '--exe', '--e']:
                config['exe'] = True
                config['build'] = True
                i += 1

            elif arg == '--target':
                if i + 1 < len(args):
                    requested = args[i + 1].lower()
                    if requested in ['windows', 'linux', 'macos']:
                        config['target'] = requested
                    else:
                        CLI.warning(f"Unknown target '{requested}'. Defaulting to 'windows'.")
                        config['target'] = 'windows'
                    i += 2
                else:
                    CLI.error("--target requires a value (windows, linux, macos)")
                    return None
            elif arg == '--arch':
                if i + 1 < len(args):
                    requested = args[i + 1].lower()
                    if requested in ['x86_64', 'arm64']:
                        config['arch'] = requested
                    else:
                        CLI.warning(f"Unknown architecture '{requested}'. Defaulting to 'x86_64'.")
                        config['arch'] = 'x86_64'
                    i += 2
                else:
                    CLI.error("--arch requires a value (x86_64, arm64)")
                    return None
            elif arg == '--ldflags':
                # Accept a single string containing linker flags (quote as needed)
                if i + 1 < len(args):
                    config['ldflags'] = args[i + 1]
                    i += 2
                else:
                    CLI.error("--ldflags requires a quoted string of flags (e.g. '-L/path -lSDL2')")
                    return None
            
            elif arg == '--build':
                config['build'] = True
                i += 1
            
            elif arg == '--run':
                config['run'] = True
                config['build'] = True
                i += 1

            elif arg == '--debug':
                # Enable debug-friendly NASM output (emit DWARF/codeview info)
                config['debug'] = True
                i += 1
            
            elif arg in ['-v', '--verbose']:
                config['verbose'] = True
                i += 1
            
            elif not arg.startswith('-'):
                if config['input_file'] is None:
                    config['input_file'] = arg
                i += 1
            
            else:
                CLI.warning(f"Unknown option: {arg}")
                return None
        
        if not config['input_file']:
            CLI.error("No input file specified")
            return None
        
        return config