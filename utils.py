import sys
import shutil


# --- CLI Colors ---
class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def get_base_type(type_str):
    """Extracts base type from List[...] string."""
    if type_str.startswith("List[") and type_str.endswith("]"):
        return type_str[5:-1]
    return type_str


# --- Phase Loader ---
class ProgressBar:
    def __init__(self, total_phases=6, verbose=False):
        self.verbose = verbose
        self.total = total_phases
        self.current = 0

    def update(self, msg):
        if self.verbose:
            print(f"  {Colors.GREEN}[+]{Colors.ENDC} {msg}")
            return

        if msg.startswith("Phase"):
            # Clear previous active line
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()

            # Format phase header
            parts = msg.split(":", 1)
            if len(parts) > 1:
                description = parts[1].strip()
                print(f"{Colors.BOLD}{Colors.BLUE}:: {description}{Colors.ENDC}")
            else:
                print(f"{Colors.BOLD}{Colors.BLUE}:: {msg}{Colors.ENDC}")
        else:
            # Update detailed status on the same line
            sys.stdout.write(f"\r   {Colors.CYAN}└─{Colors.ENDC} {msg[:70]:<70}")
            sys.stdout.flush()

    def finish(self):
        if not self.verbose:
            sys.stdout.write("\r" + " " * 80 + "\r")  # Clear last detail line
            print(f"{Colors.BOLD}{Colors.GREEN}:: Scan Complete!{Colors.ENDC}")


# --- Dependency Checks ---
try:
    import markdown

    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

try:
    from weasyprint import HTML, CSS

    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
