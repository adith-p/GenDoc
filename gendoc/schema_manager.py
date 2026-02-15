import os
import sys
import subprocess
from .utils import Colors


def generate_schema(framework, root_dir):
    """Attempts to generate OpenAPI schema using detected framework."""
    manage_py = os.path.join(root_dir, "manage.py")
    if not os.path.exists(manage_py):
        print(f"{Colors.RED}Error: manage.py not found in {root_dir}{Colors.ENDC}")
        return None

    cmd = []
    output_file = "schema.yaml"

    if "drf-spectacular" in framework:
        cmd = [sys.executable, manage_py, "spectacular", "--file", output_file]
    elif "drf-yasg" in framework:
        output_file = "swagger.json"
        cmd = [sys.executable, manage_py, "generate_swagger", "-o", output_file]

    if not cmd:
        return None

    print(f"{Colors.BLUE}Running: {' '.join(cmd)}{Colors.ENDC}")
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"{Colors.GREEN}Schema generated: {output_file}{Colors.ENDC}")
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"{Colors.RED}Generation failed: {e.stderr.decode()}{Colors.ENDC}")
        return None
