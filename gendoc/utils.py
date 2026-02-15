import sys


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


# --- JSON Mock Data Generator ---
def get_mock_value(ftype):
    """Returns a mock value for a given Django/DRF field type."""
    ftype = ftype.lower()
    if "int" in ftype:
        return 0
    if "float" in ftype or "decimal" in ftype:
        return 0.0
    if "bool" in ftype:
        return True
    if "uuid" in ftype:
        return "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    if "datetime" in ftype:
        return "2024-02-15T12:00:00Z"
    if "date" in ftype:
        return "2024-02-15"
    if "email" in ftype:
        return "user@example.com"
    if "url" in ftype:
        return "https://example.com"
    if "json" in ftype or "dict" in ftype:
        return {"key": "value"}
    if "list" in ftype:
        return ["string"]
    return "string"


def generate_json_example(serializer_name, serializers_map, visited=None):
    """Generates a mock JSON dictionary/list for a serializer recursively."""
    if visited is None:
        visited = set()

    base_name = get_base_type(serializer_name)
    is_list = serializer_name.startswith("List[")

    if base_name in visited:
        return [{"...recursive..."}] if is_list else {"...recursive...": True}

    if base_name not in serializers_map:
        val = get_mock_value(base_name)
        return [val] if is_list else val

    fields = serializers_map[base_name]["fields"]
    if not fields:
        return [{}] if is_list else {}

    new_visited = visited.copy()
    new_visited.add(base_name)

    example_obj = {}
    for fname, details in fields.items():
        ftype = details["type"]

        child_is_list = ftype.startswith("List[")
        child_base = get_base_type(ftype)

        if child_base in serializers_map:
            val = generate_json_example(ftype, serializers_map, new_visited)
            example_obj[fname] = val
        else:
            val = get_mock_value(child_base)
            if child_is_list:
                val = [val]
            example_obj[fname] = val

    return [example_obj] if is_list else example_obj
