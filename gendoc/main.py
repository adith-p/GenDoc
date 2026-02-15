import sys
import os
import json
import yaml
import re
from typing import Optional

try:
    import typer
except ImportError:
    print("\033[91mError: Typer is not installed. Please run: uv add typer\033[0m")
    sys.exit(1)

from .parser import (
    scan_project,
    detect_schema_frameworks,
    find_generated_schemas,
    parse_schema_file,
)
from .utils import Colors, ProgressBar, YAML_AVAILABLE
from .openapi import generate_openapi_spec
from .postman import generate_postman_collection
from .renderer import generate_markdown
from .converters import convert_to_pdf, convert_to_html
from .schema_manager import generate_schema

# Initialize Typer App
app = typer.Typer(
    name="drf-docmint", help="Static API Documentation Generator", add_completion=False
)


@app.command()
def generate_docs(
    target: str = typer.Argument(".", help="Project root or schema file"),
    verbose: bool = typer.Option(False, "--verbose", "-vb", help="Verbose output"),
    destination: Optional[str] = typer.Option(
        None, "--destination", "-d", help="Output file path"
    ),
    format: str = typer.Option(
        "md",
        "--format",
        "-f",
        help="Output format: 'md', 'pdf', 'html', 'json', 'yaml', 'postman'",
    ),
    api_version: Optional[str] = typer.Option(
        None,
        "--api-version",
        help="Filter by API version (e.g., 'v1', 'v2', or 'all' for any versioned endpoint)",
    ),
    auto_open: bool = typer.Option(
        False, "--open", "-o", help="Open the generated file automatically"
    ),
    version: bool = typer.Option(
        False, "--version", "-v", help="Show drf-docmint version and exit"
    ),
):
    """Generate API documentation from Django REST Framework project."""

    if version:
        from gendoc import __version__

        print(__version__)
        raise typer.Exit()

    # Determine output filename and location
    if destination:
        output_file = destination
        # Ensure the directory for the provided destination exists
        output_dir = os.path.dirname(output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
    else:
        # Default to docs/ folder in current directory
        output_dir = "docs"
        os.makedirs(output_dir, exist_ok=True)
        ext = "json" if format == "postman" else format
        output_file = os.path.join(output_dir, f"API_DOCS.{ext}")

    print(f"{Colors.HEADER}╔═══════════════════════════════════════╗{Colors.ENDC}")
    print(f"{Colors.HEADER}║     drf-docmint API Doc Generator     ║{Colors.ENDC}")
    print(f"{Colors.HEADER}╚═══════════════════════════════════════╝{Colors.ENDC}")

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

    # Filter standard paths if requested
    if api_version:
        initial_count = len(specs)
        if api_version.lower() == "all":
            specs = [s for s in specs if re.search(r"/v\d+", s["path"])]
            print(f"{Colors.BLUE}Filtering: all versioned endpoints{Colors.ENDC}")
        else:
            version_pattern = (
                api_version if api_version.startswith("v") else f"v{api_version}"
            )
            specs = [s for s in specs if f"/{version_pattern}" in s["path"].lower()]
            print(f"{Colors.BLUE}Filtering: API version {version_pattern}{Colors.ENDC}")

        filtered_count = initial_count - len(specs)
        if filtered_count > 0:
            print(
                f"{Colors.BLUE}Filtered {filtered_count} endpoints (kept {len(specs)}).{Colors.ENDC}"
            )

    # --- Export Logic ---
    if format == "json":
        print(f"\n{Colors.GREEN}[+]{Colors.ENDC} Generating JSON (OpenAPI)...")
        openapi_spec = generate_openapi_spec(specs, serializers_map)
        with open(output_file, "w") as f:
            json.dump(openapi_spec, f, indent=2)
        print(f"{Colors.BOLD}Successfully generated JSON spec.{Colors.ENDC}")
        print(f"Saved to: {Colors.UNDERLINE}{output_file}{Colors.ENDC}")
        if auto_open:
            typer.launch(output_file)
        return

    if format == "yaml":
        print(f"\n{Colors.GREEN}[+]{Colors.ENDC} Generating YAML (OpenAPI)...")
        if not YAML_AVAILABLE:
            print(
                f"{Colors.RED}Error: PyYAML is required for YAML export.{Colors.ENDC}"
            )
            print(f"{Colors.YELLOW}Run: uv add PyYAML{Colors.ENDC}")
            sys.exit(1)

        openapi_spec = generate_openapi_spec(specs, serializers_map)
        with open(output_file, "w") as f:
            yaml.dump(openapi_spec, f, sort_keys=False)
        print(f"{Colors.BOLD}Successfully generated YAML spec.{Colors.ENDC}")
        print(f"Saved to: {Colors.UNDERLINE}{output_file}{Colors.ENDC}")
        if auto_open:
            typer.launch(output_file)
        return

    if format == "postman":
        print(f"\n{Colors.GREEN}[+]{Colors.ENDC} Generating Postman Collection...")
        collection = generate_postman_collection(specs, serializers_map)
        with open(output_file, "w") as f:
            json.dump(collection, f, indent=2)
        print(f"{Colors.BOLD}Successfully generated Postman Collection.{Colors.ENDC}")
        print(f"Saved to: {Colors.UNDERLINE}{output_file}{Colors.ENDC}")
        if auto_open:
            typer.launch(output_file)
        return

    # Normal Docs Generation (MD/PDF/HTML)
    print(f"\n{Colors.GREEN}[+]{Colors.ENDC} Generating content...")

    # Output
    if format == "html":
        md = generate_markdown(specs, serializers_map, mode="html")
        success = convert_to_html(md, output_file)
        if success:
            print(
                f"\n{Colors.BOLD}Successfully generated HTML documentation for {len(specs)} endpoints{Colors.ENDC}"
            )
            print(f"Saved to: {Colors.UNDERLINE}{output_file}{Colors.ENDC}")
            if auto_open:
                typer.launch(output_file)
        return

    # Generate with format-specific rendering
    md = generate_markdown(specs, serializers_map, mode=format)

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
            if auto_open:
                typer.launch(md_fallback)
        else:
            # Also save markdown version
            md_version = output_file.replace(".pdf", ".md")
            md_content = generate_markdown(specs, serializers_map, mode="md")
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
            if auto_open:
                typer.launch(output_file)
    else:
        with open(output_file, "w") as f:
            f.write(md)
        print(
            f"\n{Colors.BOLD}Successfully generated documentation for {len(specs)} endpoints.{Colors.ENDC}"
        )
        print(f"Saved to: {Colors.UNDERLINE}{output_file}{Colors.ENDC}")
        if auto_open:
            typer.launch(output_file)


if __name__ == "__main__":
    app()
