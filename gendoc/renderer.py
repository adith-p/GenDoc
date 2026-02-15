import json
import datetime
import html
import re
from .utils import get_base_type


def get_endpoint_slug(path):
    """Creates a URL-safe slug for an endpoint path for jump links."""
    # Remove special chars and convert to hyphenated string
    clean_path = (
        path.lower()
        .replace("/", "-")
        .replace("{", "")
        .replace("}", "")
        .replace("<", "")
        .replace(">", "")
        .replace(":", "")
    )
    return "endpoint-" + clean_path.strip("-")


def render_json_block(serializer_name, serializers_map):
    """Renders a collapsible JSON example block."""
    try:
        example = generate_json_example(serializer_name, serializers_map)
        json_str = json.dumps(example, indent=2)
        return f"""
\n<details markdown="1">
<summary style="font-size: 0.9em; color: #6a737d;">View JSON Payload</summary>

```json
{json_str}
```

</details>\n
"""
    except Exception:
        return ""


# --- Table Renderers ---
def render_nested_schema(serializer_name, serializers_map, visited=None):
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

    html_parts = [
        "\n<ul style='list-style-type: none; padding-left: 10px; margin: 0;'>\n"
    ]
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
                nested_html = f"\n<div style='margin-left: 10px; border-left: 2px solid #eee; padding-left: 10px;'><details><summary style='cursor: pointer; color: #333;'>Show Nested</summary>{child_content}</details></div>\n"

        html_parts.append(
            f"<li style='margin-bottom: 4px;'><strong>{fname}</strong>: <code style='background: #f4f4f4; padding: 2px 4px; border-radius: 4px;'>{ftype}</code> {prop_html} {nested_html}</li>"
        )

    html_parts.append("</ul>\n")
    return "".join(html_parts)


def render_serializer_table_html(serializer_name, serializers_map):
    """HTML table for PDF/HTML - avoids markdown table parsing issues inside details."""
    base_name = get_base_type(serializer_name)
    if base_name not in serializers_map:
        return ""

    fields = serializers_map[base_name]["fields"]
    if not fields:
        return ""

    lines = []
    lines.append("\n<table>")
    lines.append("  <thead>")
    lines.append("    <tr>")
    lines.append(
        "      <th>Field</th><th>Type</th><th>Properties</th><th>Nested Schema</th>"
    )
    lines.append("    </tr>")
    lines.append("  </thead>")
    lines.append("  <tbody>")

    visited = {base_name}
    for field_name, details in fields.items():
        ftype = details["type"]
        props_list = details["props"]

        prop_badges = []
        if props_list:
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

        child_base = get_base_type(ftype)
        nested_display = "-"
        if child_base in serializers_map:
            nested_html = render_nested_schema(child_base, serializers_map, visited)
            if nested_html:
                nested_display = (
                    f"\n<details><summary>View</summary>{nested_html}</details>\n"
                )

        lines.append("    <tr>")
        lines.append(f"      <td><strong>{field_name}</strong></td>")
        lines.append(f"      <td><code>{ftype}</code></td>")
        lines.append(f"      <td>{props_html}</td>")
        lines.append(f"      <td>{nested_display}</td>")
        lines.append("    </tr>")

    lines.append("  </tbody>")
    lines.append("</table>\n")
    return "\n" + "\n".join(lines) + "\n"


def render_serializer_table_markdown(serializer_name, serializers_map):
    """Standard Markdown table."""
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


def generate_markdown(specs, serializers_map, mode="md"):
    """
    Generate documentation content.
    mode: 'md', 'html', 'pdf'
    """
    lines = []
    use_html_tables = mode in ["html", "pdf"]
    use_static_headers = mode == "pdf"
    supports_json_view = mode in ["md", "html"]

    # Top anchor for back to top button
    lines.append('<div id="top"></div>')
    lines.append("")

    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"# API Documentation")
    lines.append(f"> **Generated by drf-docmint** on {generated_at}")
    lines.append("")

    # Grouping
    grouped_specs = {}
    for spec in specs:
        path = spec["path"]
        match = re.search(r"/(v\d+(?:\.\d+)?)/", path)
        version = match.group(1) if match else "General"

        resource = "Other"
        if match:
            remainder = path[match.end() :]
            parts = [p for p in remainder.split("/") if p]
            if parts:
                resource = parts[0].capitalize()
        else:
            parts = [p for p in path.split("/") if p]
            if parts:
                resource = parts[0].capitalize()

        if version not in grouped_specs:
            grouped_specs[version] = {}
        if resource not in grouped_specs[version]:
            grouped_specs[version][resource] = []
        grouped_specs[version][resource].append(spec)

    sorted_versions = sorted([v for v in grouped_specs.keys() if v != "General"])
    if "General" in grouped_specs:
        sorted_versions.append("General")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")

    for version in sorted_versions:
        resources = sorted(grouped_specs[version].keys())
        if len(sorted_versions) > 1:
            lines.append(f"### {version}")

        for resource in resources:
            version_specs = sorted(
                grouped_specs[version][resource], key=lambda x: x["path"]
            )
            lines.append(f"#### {resource}")
            lines.append("")

            if use_html_tables:
                lines.append('\n<table class="summary-table">')
                lines.append(
                    "  <thead><tr><th>Endpoint</th><th style='text-align: center;'>Method</th><th>Request</th><th>Response</th></tr></thead>"
                )
                lines.append("  <tbody>")
                for spec in version_specs:
                    path = spec["path"]
                    slug = get_endpoint_slug(path)
                    for method, details in spec["methods"].items():
                        req = details.get("request", "None")
                        res = details.get("response", "None")
                        if len(res) > 60:
                            res = res[:57] + "..."

                        safe_path = html.escape(path)
                        safe_req = html.escape(req)
                        safe_res = html.escape(res)
                        method_class = f"method-{method.lower()}"

                        lines.append(
                            f"    <tr><td><code><a href='#{slug}' style='color: inherit; text-decoration: underline;'>{safe_path}</a></code></td><td style='text-align: center;'><span class='{method_class}'>{method}</span></td><td><code>{safe_req}</code></td><td><code>{safe_res}</code></td></tr>"
                        )
                lines.append("  </tbody></table>\n")
            else:
                lines.append("| Endpoint | Method | Request | Response |")
                lines.append("| :--- | :---: | :--- | :--- |")
                for spec in version_specs:
                    path = spec["path"]
                    slug = get_endpoint_slug(path)
                    for method, details in spec["methods"].items():
                        req = details.get("request", "None")
                        res = details.get("response", "None").replace("|", "\\|")
                        method_badge = (
                            f"<span style='font-weight: bold;'>{method}</span>"
                        )
                        # We use HTML for the link in MD summary to force monochrome if possible, or keep simple MD
                        lines.append(
                            f"| <a href='#{slug}' style='color: inherit; font-family: monospace;'>{path}</a> | {method_badge} | `{req}` | `{res}` |"
                        )
            lines.append("")

    lines.append("---")
    lines.append("")

    # Endpoint Details
    use_version_headers = len(sorted_versions) > 1
    if not use_version_headers:
        lines.append("## Endpoint Details")
        lines.append("")

    for version in sorted_versions:
        resources = sorted(grouped_specs[version].keys())
        if use_version_headers:
            lines.append(f"## {version} Endpoints")
            lines.append("")

        for resource in resources:
            version_specs = sorted(
                grouped_specs[version][resource], key=lambda x: x["path"]
            )
            lines.append(f"### {resource}")
            lines.append("")

            for spec in version_specs:
                path = spec["path"]
                view = spec["view"]
                doc = spec["doc"]
                slug = get_endpoint_slug(path)

                # Add ID to header for jump links
                lines.append(f"#### <a id='{slug}'></a>`{path}`")
                lines.append(f"**View Class:** `{view}`")
                lines.append("")

                if doc:
                    clean_doc = "\n".join(
                        [line.strip() for line in doc.split("\n") if line.strip()]
                    )
                    if clean_doc:
                        if use_html_tables:
                            lines.append(f"<blockquote>{clean_doc}</blockquote>")
                        else:
                            lines.append(f"```text\n{clean_doc}\n```")
                lines.append("")

                for method, details in spec["methods"].items():
                    # Generate Permission Badges
                    perms = details.get("permissions", [])
                    perm_html = ""
                    if perms:
                        badges = []
                        for p in perms:
                            if "AllowAny" in p:
                                badges.append(
                                    f"<span style='background:#28a745;color:white;padding:2px 6px;border-radius:4px;font-size:0.8em;'>{p}</span>"
                                )
                            elif "IsAuthenticated" in p:
                                badges.append(
                                    f"<span style='background:#dc3545;color:white;padding:2px 6px;border-radius:4px;font-size:0.8em;'>{p}</span>"
                                )
                            else:
                                badges.append(
                                    f"<span style='background:#6c757d;color:white;padding:2px 6px;border-radius:4px;font-size:0.8em;'>{p}</span>"
                                )
                        perm_html = " " + " ".join(badges)

                    if use_static_headers:
                        method_class = f"method-{method.lower()}"
                        lines.append(
                            f"<h5><span class='{method_class}'>{method}</span>{perm_html}</h5>"
                        )
                    else:
                        lines.append(f'\n<details markdown="1">')
                        # Note: putting HTML inside summary might break markdown parsers in summary, but usually ok in HTML mode
                        lines.append(
                            f"<summary><strong>{method}</strong>{perm_html}</summary>\n"
                        )

                    lines.append("")

                    # Input Section
                    req_ser = details.get("request", "None")
                    lines.append(f"**Input Parameters:**")

                    if req_ser not in ["None", "Not required", "NoBody"]:
                        lines.append(f"Schema: `{req_ser}`")
                        lines.append("")
                        base_req = get_base_type(req_ser)
                        if base_req in serializers_map:
                            if use_html_tables:
                                lines.append(
                                    render_serializer_table_html(
                                        req_ser, serializers_map
                                    )
                                )
                            else:
                                lines.append(
                                    render_serializer_table_markdown(
                                        req_ser, serializers_map
                                    )
                                )
                            if supports_json_view:
                                lines.append(
                                    render_json_block(req_ser, serializers_map)
                                )
                        elif "RawBody" in req_ser:
                            lines.append("")
                            lines.append(
                                "> **Raw Body:** This endpoint accepts raw JSON data."
                            )
                            lines.append("")
                    else:
                        lines.append("_No input required._")

                    # Query Parameters Section (NEW)
                    query_params = details.get("query_params", [])
                    if query_params:
                        lines.append("")
                        lines.append(f"**Query Parameters:**")
                        lines.append("")
                        if use_html_tables:
                            lines.append(
                                "\n<table><thead><tr><th>Parameter</th><th>Type</th></tr></thead><tbody>"
                            )
                            for qp in sorted(query_params):
                                lines.append(
                                    f"<tr><td><code>{qp}</code></td><td>String (Query)</td></tr>"
                                )
                            lines.append("</tbody></table>\n")
                        else:
                            lines.append("| Parameter | Type |")
                            lines.append("| :--- | :--- |")
                            for qp in sorted(query_params):
                                lines.append(f"| `{qp}` | String (Query) |")
                        lines.append("")

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
                                if use_html_tables:
                                    lines.append(
                                        render_serializer_table_html(
                                            ser, serializers_map
                                        )
                                    )
                                else:
                                    lines.append(
                                        render_serializer_table_markdown(
                                            ser, serializers_map
                                        )
                                    )
                                if supports_json_view:
                                    lines.append(
                                        render_json_block(ser, serializers_map)
                                    )
                            lines.append("")
                    else:
                        res_ser = details.get("response", "None")
                        lines.append(f"**Output:** `{res_ser}`")
                        lines.append("")
                        base_res = get_base_type(res_ser)
                        if base_res in serializers_map:
                            if use_html_tables:
                                lines.append(
                                    render_serializer_table_html(
                                        res_ser, serializers_map
                                    )
                                )
                            else:
                                lines.append(
                                    render_serializer_table_markdown(
                                        res_ser, serializers_map
                                    )
                                )
                            if supports_json_view:
                                lines.append(
                                    render_json_block(res_ser, serializers_map)
                                )

                    lines.append("")
                    if not use_static_headers:
                        lines.append("</details>\n")
                        lines.append("")

                lines.append("---")
                lines.append("")

    # Add floating Back to Top button at the end
    if mode in ["html", "md"]:
        lines.append("""
<a href="#top" class="back-to-top" title="Back to Top">
    <span>↑</span>
</a>
<style>
    .back-to-top {
        position: fixed;
        bottom: 30px;
        right: 30px;
        width: 45px;
        height: 45px;
        background-color: #333;
        color: white !important;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        text-decoration: none !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        transition: all 0.2s ease;
        font-weight: bold;
        font-size: 20px;
    }
    .back-to-top:hover {
        background-color: #000;
        transform: translateY(-3px);
        box-shadow: 0 6px 16px rgba(0,0,0,0.2);
    }
    /* Universal Link Monochrome Styling */
    a[href^="#endpoint-"] {
        color: inherit !important;
        text-decoration: underline;
    }
</style>
""")

    return "\n".join(lines)

