"""
GenDoc CLI - Fixed PDF Table Rendering
Properly formats tables in both Markdown and PDF to prevent alignment issues
"""

import sys
import os
import datetime
import subprocess
import shutil
from typing import Optional

try:
    import typer
except ImportError:
    print("\033[91mError: Typer is not installed. Please run: uv add typer\033[0m")
    sys.exit(1)

from parser import (
    scan_project,
    detect_schema_frameworks,
    find_generated_schemas,
    parse_schema_file,
)

# Check for Python-native PDF libs
try:
    import markdown
    from weasyprint import HTML, CSS

    PYTHON_PDF_SUPPORT = True
except ImportError:
    PYTHON_PDF_SUPPORT = False

# Initialize Typer App
app = typer.Typer(
    name="GenDoc", help="Beautiful API Documentation Generator", add_completion=False
)


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


# --- Progress Bar ---
class ProgressBar:
    def __init__(self, total_phases=6, verbose=False):
        self.total = total_phases
        self.current = 0
        self.verbose = verbose
        self.bar_length = 30

    def update(self, msg):
        if self.verbose:
            print(f"  {Colors.GREEN}[+]{Colors.ENDC} {msg}")
            return

        if "Phase" in msg:
            self.current += 1

        progress = min(self.current / self.total, 1.0)
        filled_len = int(self.bar_length * progress)
        bar = "█" * filled_len + "-" * (self.bar_length - filled_len)
        percent = int(progress * 100)

        sys.stdout.write(
            f"\r{Colors.BLUE}[{bar}]{Colors.ENDC} {percent}% | {msg[:40]:<40}"
        )
        sys.stdout.flush()

    def finish(self):
        if not self.verbose:
            bar = "█" * self.bar_length
            sys.stdout.write(
                f"\r{Colors.GREEN}[{bar}]{Colors.ENDC} 100% | Scan Complete!                                   \n"
            )
            sys.stdout.flush()


def get_base_type(type_str):
    """Extracts base type from List[...] string."""
    if type_str.startswith("List[") and type_str.endswith("]"):
        return type_str[5:-1]
    return type_str


def render_nested_schema(serializer_name, serializers_map, visited=None):
    """Generates an HTML list for nested serializer fields."""
    if visited is None:
        visited = set()

    base_name = get_base_type(serializer_name)

    if base_name in visited:
        return "<em style='color: #888;'>(Recursive)</em>"

    if base_name not in serializers_map:
        return ""

    fields = serializers_map[base_name]["fields"]
    if not fields:
        return ""

    new_visited = visited.copy()
    new_visited.add(base_name)

    html_parts = ["<ul style='list-style-type: none; padding-left: 10px; margin: 0;'>"]
    for fname, details in fields.items():
        ftype = details["type"]
        props = details["props"]

        prop_badges = []
        for p in props:
            color = (
                "#d9534f"
                if p == "Required"
                else "#5bc0de"
                if p == "ReadOnly"
                else "#aaa"
            )
            prop_badges.append(
                f"<span style='font-size: 0.8em; color: {color}; border: 1px solid {color}; padding: 0 4px; border-radius: 3px;'>{p}</span>"
            )

        prop_html = " ".join(prop_badges)

        child_base = get_base_type(ftype)
        nested_html = ""
        if child_base in serializers_map:
            child_content = render_nested_schema(
                child_base, serializers_map, new_visited
            )
            if child_content:
                nested_html = f"<div style='margin-left: 10px; border-left: 2px solid #eee; padding-left: 10px;'><details><summary style='cursor: pointer; color: #007bff;'>Show Nested</summary>{child_content}</details></div>"

        html_parts.append(
            f"<li style='margin-bottom: 4px;'><strong>{fname}</strong>: <code style='background: #f4f4f4; padding: 2px 4px; border-radius: 4px;'>{ftype}</code> {prop_html} {nested_html}</li>"
        )

    html_parts.append("</ul>")
    return "".join(html_parts)


def render_serializer_table_html(serializer_name, serializers_map):
    """Generates an HTML table (for PDF) - prevents alignment issues."""
    base_name = get_base_type(serializer_name)

    if base_name not in serializers_map:
        return ""

    fields = serializers_map[base_name]["fields"]
    if not fields:
        return ""

    lines = []
    lines.append("<table>")
    lines.append("  <thead>")
    lines.append("    <tr>")
    lines.append("      <th>Field</th>")
    lines.append("      <th>Type</th>")
    lines.append("      <th>Properties</th>")
    lines.append("      <th>Nested Schema</th>")
    lines.append("    </tr>")
    lines.append("  </thead>")
    lines.append("  <tbody>")

    visited = {base_name}

    for field_name, details in fields.items():
        ftype = details["type"]
        props_list = details["props"]

        # Format properties with badges
        if props_list:
            prop_badges = []
            for p in props_list:
                css_class = (
                    "prop-required"
                    if p == "Required"
                    else "prop-readonly"
                    if p == "ReadOnly"
                    else "prop-optional"
                )
                prop_badges.append(f'<span class="{css_class}">{p}</span>')
            props_html = " ".join(prop_badges)
        else:
            props_html = "-"

        # Check for nested serializer
        child_base = get_base_type(ftype)
        nested_display = "-"

        if child_base in serializers_map:
            nested_html = render_nested_schema(child_base, serializers_map, visited)
            if nested_html:
                nested_display = (
                    f"<details><summary>View</summary>{nested_html}</details>"
                )

        lines.append("    <tr>")
        lines.append(f"      <td><strong>{field_name}</strong></td>")
        lines.append(f"      <td><code>{ftype}</code></td>")
        lines.append(f"      <td>{props_html}</td>")
        lines.append(f"      <td>{nested_display}</td>")
        lines.append("    </tr>")

    lines.append("  </tbody>")
    lines.append("</table>")

    return "\n" + "\n".join(lines) + "\n"


def render_serializer_table_markdown(serializer_name, serializers_map):
    """Generates a Markdown table (for .md files)."""
    base_name = get_base_type(serializer_name)

    if base_name not in serializers_map:
        return ""

    fields = serializers_map[base_name]["fields"]
    if not fields:
        return ""

    lines = []
    lines.append("")
    lines.append("| Field | Type | Properties | Schema |")
    lines.append("| :--- | :--- | :--- | :--- |")

    visited = {base_name}

    for field_name, details in fields.items():
        ftype = details["type"]
        props = (
            ", ".join([f"`{p}`" for p in details["props"]]) if details["props"] else "-"
        )

        child_base = get_base_type(ftype)
        nested_display = "-"

        if child_base in serializers_map:
            nested_html = render_nested_schema(child_base, serializers_map, visited)
            if nested_html:
                nested_display = (
                    f"<details><summary>View Nested</summary>{nested_html}</details>"
                )

        lines.append(f"| **{field_name}** | `{ftype}` | {props} | {nested_display} |")

    return "\n" + "\n".join(lines) + "\n"


def generate_markdown(specs, serializers_map, for_pdf=False):
    """Generate markdown - with option to use HTML tables for PDF."""
    lines = []

    # Header
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"# API Documentation")
    lines.append(f"> **Generated by GenDoc** on {generated_at}")
    lines.append("")

    # Executive Summary Table
    lines.append("## Executive Summary")
    lines.append("")

    if for_pdf:
        # Use HTML table for PDF with proper styling
        lines.append('<table class="summary-table">')
        lines.append("  <thead>")
        lines.append("    <tr>")
        lines.append("      <th>Endpoint</th>")
        lines.append('      <th style="text-align: center;">Method</th>')
        lines.append("      <th>Request</th>")
        lines.append("      <th>Response</th>")
        lines.append("    </tr>")
        lines.append("  </thead>")
        lines.append("  <tbody>")

        for spec in sorted(specs, key=lambda x: x["path"]):
            path = spec["path"]
            for method, details in spec["methods"].items():
                req = details.get("request", "None")
                res = details.get("response", "None")

                # Truncate long responses to prevent overflow
                if len(res) > 60:
                    res = res[:57] + "..."

                method_class = f"method-{method.lower()}"
                lines.append(f"    <tr>")
                lines.append(f"      <td><code>{path}</code></td>")
                lines.append(
                    f'      <td style="text-align: center;"><span class="{method_class}">{method}</span></td>'
                )
                lines.append(f"      <td><code>{req}</code></td>")
                lines.append(f"      <td><code>{res}</code></td>")
                lines.append(f"    </tr>")

        lines.append("  </tbody>")
        lines.append("</table>")
        lines.append(
            '<div class="page-break-after"></div>'
        )  # Force page break after summary
    else:
        # Use Markdown table
        lines.append("| Endpoint | Method | Request | Response |")
        lines.append("| :--- | :---: | :--- | :--- |")

        method_styles = {
            "GET": "color: #28a745;",
            "POST": "color: #007bff;",
            "PUT": "color: #fd7e14;",
            "PATCH": "color: #ffc107;",
            "DELETE": "color: #dc3545;",
        }

        for spec in sorted(specs, key=lambda x: x["path"]):
            path = spec["path"]
            for method, details in spec["methods"].items():
                req = details.get("request", "None")
                res = details.get("response", "None").replace("|", "\\|")

                style = method_styles.get(method, "")
                method_badge = (
                    f"<span style='{style} font-weight: bold;'>{method}</span>"
                )

                lines.append(f"| `{path}` | {method_badge} | `{req}` | `{res}` |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Endpoint Details
    lines.append("## Endpoint Details")
    lines.append("")

    for spec in sorted(specs, key=lambda x: x["path"]):
        path = spec["path"]
        view = spec["view"]
        doc = spec["doc"]

        lines.append(f"### `{path}`")
        lines.append(f"**View Class:** `{view}`")
        lines.append("")

        if doc:
            clean_doc = "\n".join(
                [line.strip() for line in doc.split("\n") if line.strip()]
            )
            if clean_doc:
                if for_pdf:
                    lines.append(f"<blockquote>{clean_doc}</blockquote>")
                else:
                    lines.append(f"```text\n{clean_doc}\n```")
        lines.append("")

        lines.append("#### Methods")
        lines.append("")

        for method, details in spec["methods"].items():
            if for_pdf:
                method_class = f"method-{method.lower()}"
                lines.append(f"<h4><span class='{method_class}'>{method}</span></h4>")
            else:
                lines.append(f"<details>")
                lines.append(f"<summary><strong>{method}</strong></summary>")

            lines.append("")

            # Input Section
            req_ser = details.get("request", "None")
            lines.append(f"**Input Parameters:**")

            if req_ser not in ["None", "Not required", "NoBody"]:
                lines.append(f"Schema: `{req_ser}`")
                lines.append("")

                base_req = get_base_type(req_ser)
                if base_req in serializers_map:
                    if for_pdf:
                        lines.append(
                            render_serializer_table_html(req_ser, serializers_map)
                        )
                    else:
                        lines.append(
                            render_serializer_table_markdown(req_ser, serializers_map)
                        )
            else:
                lines.append("_No input required._")

            lines.append("")

            # Response Section
            lines.append(f"**Responses:**")
            lines.append("")

            res_details = details.get("response_details")
            if res_details:
                for status, info in sorted(res_details.items()):
                    ser = info.get("serializer", "Unknown")
                    lines.append(f"**{status}** (`{ser}`)")

                    base_res = get_base_type(ser)
                    if base_res in serializers_map:
                        if for_pdf:
                            lines.append(
                                render_serializer_table_html(ser, serializers_map)
                            )
                        else:
                            lines.append(
                                render_serializer_table_markdown(ser, serializers_map)
                            )
                    lines.append("")
            else:
                res_ser = details.get("response", "None")
                lines.append(f"**Output:** `{res_ser}`")
                lines.append("")

                base_res = get_base_type(res_ser)
                if base_res in serializers_map:
                    if for_pdf:
                        lines.append(
                            render_serializer_table_html(res_ser, serializers_map)
                        )
                    else:
                        lines.append(
                            render_serializer_table_markdown(res_ser, serializers_map)
                        )

            lines.append("")

            if not for_pdf:
                lines.append("</details>")
                lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


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


def convert_to_pdf(md_content, output_path):
    """Converts Markdown to PDF using WeasyPrint."""

    if not PYTHON_PDF_SUPPORT:
        print(f"{Colors.RED}Error: WeasyPrint not installed.{Colors.ENDC}")
        print(f"{Colors.YELLOW}Install: pip install markdown weasyprint{Colors.ENDC}")
        return False

    print(f"  {Colors.BLUE}[*]{Colors.ENDC} Converting to PDF with WeasyPrint...")

    try:
        # Convert MD -> HTML
        html_content = markdown.markdown(
            md_content, extensions=["tables", "fenced_code", "attr_list"]
        )

        # Enhanced CSS for PDF
        css = """
            @page {
                size: A4;
                margin: 2.5cm;
                @bottom-center {
                    content: "Page " counter(page);
                    font-size: 9pt;
                    color: #777;
                }
            }
            
            body {
                font-family: 'Helvetica', 'Arial', sans-serif;
                font-size: 10pt;
                line-height: 1.6;
                color: #333;
            }
            
            h1 { color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; font-size: 24pt; page-break-after: avoid; }
            h2 { color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-top: 30px; font-size: 18pt; page-break-after: avoid; }
            h3 { color: #34495e; margin-top: 25px; font-size: 14pt; font-weight: bold; page-break-after: avoid; }
            h4 { color: #34495e; font-size: 12pt; font-weight: bold; margin: 15px 0 10px 0; page-break-after: avoid; }
            
            /* Tables - General */
            table {
                border-collapse: collapse;
                width: 100%;
                margin: 15px 0;
                font-size: 9pt;
                page-break-inside: auto;
            }
            tr {
                page-break-inside: avoid;
                page-break-after: auto;
            }
            th, td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
                vertical-align: top;
                word-wrap: break-word;
                overflow-wrap: break-word;
            }
            th {
                background-color: #f8f9fa;
                font-weight: bold;
                color: #333;
            }
            
            /* Summary Table - Specific styling */
            .summary-table {
                table-layout: fixed;
                width: 100%;
            }
            .summary-table th:nth-child(1) { width: 30%; }  /* Endpoint */
            .summary-table th:nth-child(2) { width: 12%; text-align: center; }  /* Method */
            .summary-table th:nth-child(3) { width: 28%; }  /* Request */
            .summary-table th:nth-child(4) { width: 30%; }  /* Response */
            
            .summary-table td {
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .summary-table td:nth-child(2) {
                text-align: center;
            }
            
            /* Page break utilities */
            .page-break-after {
                page-break-after: always;
            }
            .page-break-before {
                page-break-before: always;
            }
            .avoid-break {
                page-break-inside: avoid;
            }
            
            /* Code */
            code {
                background-color: #f4f4f4;
                font-family: 'Courier New', monospace;
                padding: 2px 4px;
                font-size: 9pt;
                border-radius: 3px;
                color: #e74c3c;
                word-break: break-all;
            }
            pre {
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                border: 1px solid #eee;
                font-family: 'Courier New', monospace;
                font-size: 9pt;
                white-space: pre-wrap;
                margin: 15px 0;
                overflow-wrap: break-word;
            }
            pre code {
                background-color: transparent;
                padding: 0;
                color: #333;
            }
            
            blockquote {
                border-left: 4px solid #ddd;
                padding-left: 15px;
                margin: 15px 0;
                color: #666;
                font-style: italic;
            }
            
            /* Method badges */
            .method-get { background: #28a745; color: white; padding: 3px 10px; border-radius: 4px; font-weight: bold; font-size: 8pt; display: inline-block; }
            .method-post { background: #007bff; color: white; padding: 3px 10px; border-radius: 4px; font-weight: bold; font-size: 8pt; display: inline-block; }
            .method-put { background: #fd7e14; color: white; padding: 3px 10px; border-radius: 4px; font-weight: bold; font-size: 8pt; display: inline-block; }
            .method-patch { background: #ffc107; color: #333; padding: 3px 10px; border-radius: 4px; font-weight: bold; font-size: 8pt; display: inline-block; }
            .method-delete { background: #dc3545; color: white; padding: 3px 10px; border-radius: 4px; font-weight: bold; font-size: 8pt; display: inline-block; }
            
            /* Property badges */
            .prop-required { color: #d73a49; border: 1px solid #d73a49; padding: 1px 4px; border-radius: 3px; font-size: 8pt; font-weight: bold; }
            .prop-readonly { color: #0366d6; border: 1px solid #0366d6; padding: 1px 4px; border-radius: 3px; font-size: 8pt; font-weight: bold; }
            .prop-optional { color: #6a737d; border: 1px solid #6a737d; padding: 1px 4px; border-radius: 3px; font-size: 8pt; }
            
            /* Details */
            details {
                margin: 10px 0;
                padding: 10px;
                background: #f9f9f9;
                border: 1px solid #eee;
                border-radius: 4px;
            }
            summary {
                font-weight: bold;
                cursor: pointer;
                color: #0366d6;
            }
        """

        html_doc = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>API Documentation</title>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        HTML(string=html_doc).write_pdf(output_path, stylesheets=[CSS(string=css)])
        return True

    except Exception as e:
        print(f"{Colors.RED}PDF generation failed: {e}{Colors.ENDC}")
        return False


@app.command()
def generate_docs(
    target: str = typer.Argument(".", help="Project root or schema file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    destination: Optional[str] = typer.Option(
        None, "--destination", "-d", help="Output file path"
    ),
    format: str = typer.Option(
        "md", "--format", "-f", help="Output format: 'md' or 'pdf'"
    ),
):
    """Generate API documentation from Django REST Framework project."""

    output_file = destination or f"API_DOCS.{format}"

    print(f"{Colors.HEADER}╔════════════════════════════════════╗{Colors.ENDC}")
    print(f"{Colors.HEADER}║      GenDoc API Doc Generator      ║{Colors.ENDC}")
    print(f"{Colors.HEADER}╚════════════════════════════════════╝{Colors.ENDC}")

    specs = []
    serializers_map = {}
    used_schema = False

    # Schema file provided directly
    if os.path.isfile(target) and target.endswith((".json", ".yaml", ".yml")):
        print(f"\n{Colors.BLUE}Parsing schema file...{Colors.ENDC}")
        try:
            specs, serializers_map = parse_schema_file(target)
            used_schema = True
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.ENDC}")
            raise typer.Exit(code=1)

    # Directory scan
    else:
        root_dir = target
        frameworks = detect_schema_frameworks(root_dir)
        schema_files = find_generated_schemas(root_dir)

        if frameworks or schema_files:
            print(f"\n{Colors.CYAN}--- Schema Detection ---{Colors.ENDC}")

            if frameworks:
                print(
                    f"Detected frameworks: {Colors.BOLD}{', '.join(frameworks)}{Colors.ENDC}"
                )

            if schema_files:
                print(f"Detected existing schema files:")
                for schema_file in schema_files:
                    print(f"  {Colors.YELLOW}- {schema_file}{Colors.ENDC}")

            print("-" * 24)

            if schema_files:
                print(f"{Colors.BOLD}Found existing schema file(s).{Colors.ENDC}")

                if frameworks:
                    choice = input(
                        f"Use existing ({Colors.GREEN}s{Colors.ENDC}), regenerate using {frameworks[0]} ({Colors.YELLOW}r{Colors.ENDC}), or use static analysis ({Colors.BLUE}g{Colors.ENDC})? [s/r/g]: "
                    ).lower()
                else:
                    choice = input(
                        f"Use existing schema ({Colors.GREEN}s{Colors.ENDC}) or static analysis ({Colors.BLUE}g{Colors.ENDC})? [s/g]: "
                    ).lower()

                if choice == "s":
                    print(f"{Colors.GREEN}Using:{Colors.ENDC} {schema_files[0]}")
                    try:
                        specs, serializers_map = parse_schema_file(schema_files[0])
                        used_schema = True
                    except Exception as e:
                        print(f"{Colors.RED}Error parsing schema: {e}{Colors.ENDC}")
                        print(
                            f"{Colors.YELLOW}Falling back to static analysis...{Colors.ENDC}"
                        )
                elif choice == "r" and frameworks:
                    generated_file = generate_schema(frameworks[0], root_dir)
                    if generated_file:
                        try:
                            specs, serializers_map = parse_schema_file(generated_file)
                            used_schema = True
                        except Exception as e:
                            print(
                                f"{Colors.RED}Error parsing generated schema: {e}{Colors.ENDC}"
                            )

            elif frameworks:
                print(
                    f"{Colors.YELLOW}Framework detected but no schema file found.{Colors.ENDC}"
                )
                choice = input(
                    f"Generate schema using {frameworks[0]} ({Colors.GREEN}y{Colors.ENDC}) or static analysis ({Colors.BLUE}g{Colors.ENDC})? [y/g]: "
                ).lower()
                if choice == "y":
                    generated_file = generate_schema(frameworks[0], root_dir)
                    if generated_file:
                        try:
                            specs, serializers_map = parse_schema_file(generated_file)
                            used_schema = True
                        except Exception as e:
                            print(
                                f"{Colors.RED}Error parsing generated schema: {e}{Colors.ENDC}"
                            )

    # Static analysis fallback
    if not used_schema:
        print(f"\n{Colors.BLUE}Scanning {target}...{Colors.ENDC}")
        pbar = ProgressBar(total_phases=6, verbose=verbose)
        specs, serializers_map = scan_project(target, callback=pbar.update)
        pbar.finish()

    print(f"\n{Colors.GREEN}[+]{Colors.ENDC} Generating content...")

    # Generate with format-specific rendering
    md = generate_markdown(specs, serializers_map, for_pdf=(format == "pdf"))

    # Output
    if format == "pdf":
        success = convert_to_pdf(md, output_file)
        if not success:
            # Fallback to md if PDF conversion fails
            md_fallback = output_file.replace(".pdf", ".md")
            with open(md_fallback, "w") as f:
                f.write(md)
            print(
                f"\n{Colors.YELLOW}PDF generation failed. Saved as Markdown instead:{Colors.ENDC}"
            )
            print(f"Saved to: {Colors.UNDERLINE}{md_fallback}{Colors.ENDC}")
        else:
            # Also save markdown version
            md_version = output_file.replace(".pdf", ".md")
            md_content = generate_markdown(specs, serializers_map, for_pdf=False)
            with open(md_version, "w") as f:
                f.write(md_content)

            print(
                f"\n{Colors.BOLD}Successfully generated documentation for {len(specs)} endpoints.{Colors.ENDC}"
            )
            print(
                f"{Colors.GREEN}PDF:{Colors.ENDC} {Colors.UNDERLINE}{output_file}{Colors.ENDC}"
            )
            print(
                f"{Colors.GREEN}Markdown:{Colors.ENDC} {Colors.UNDERLINE}{md_version}{Colors.ENDC}"
            )
    else:
        with open(output_file, "w") as f:
            f.write(md)
        print(
            f"\n{Colors.BOLD}Successfully generated documentation for {len(specs)} endpoints.{Colors.ENDC}"
        )
        print(f"Saved to: {Colors.UNDERLINE}{output_file}{Colors.ENDC}")


if __name__ == "__main__":
    app()
