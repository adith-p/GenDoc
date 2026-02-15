import re
import json
from .utils import get_base_type, generate_json_example


def generate_postman_collection(specs, serializers_map):
    """Converts GenDoc scan results to a Postman Collection v2.1."""

    collection = {
        "info": {
            "name": "Generated API Documentation",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": [],
        "variable": [
            {"key": "base_url", "value": "http://localhost:8000", "type": "string"}
        ],
    }

    # Grouping logic (similar to renderer but for JSON structure)
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

    # Build Folder Structure
    sorted_versions = sorted([v for v in grouped_specs.keys() if v != "General"])
    if "General" in grouped_specs:
        sorted_versions.append("General")

    for version in sorted_versions:
        version_folder = {"name": version, "item": []}

        resources = sorted(grouped_specs[version].keys())
        for resource in resources:
            resource_folder = {"name": resource, "item": []}

            version_specs = sorted(
                grouped_specs[version][resource], key=lambda x: x["path"]
            )
            for spec in version_specs:
                path = spec["path"]

                # Convert path vars: /users/<id>/ -> /users/:id/
                # Postman uses :param for path variables
                pm_path_str = re.sub(r"<[^:>]+:([^>]+)>", r":\1", path)
                pm_path_str = re.sub(r"<([^>]+)>", r":\1", pm_path_str)

                # Split for the URL object
                path_segments = [p for p in pm_path_str.split("/") if p]

                for method, details in spec["methods"].items():
                    request_name = f"{method} {path}"

                    # Generate Request Body
                    body = {}
                    req_ser = details.get("request", "None")
                    if req_ser and req_ser not in ["None", "Not required", "NoBody"]:
                        mock_data = {}
                        if "RawBody" in req_ser:
                            # Try to parse the keys from "RawBody {key1, key2}"
                            match = re.search(r"RawBody \{(.+)\}", req_ser)
                            if match:
                                keys = match.group(1).split(",")
                                for k in keys:
                                    mock_data[k.strip()] = "value"
                            else:
                                mock_data = {"key": "value"}
                        else:
                            mock_data = generate_json_example(req_ser, serializers_map)

                        body = {
                            "mode": "raw",
                            "raw": json.dumps(mock_data, indent=2),
                            "options": {"raw": {"language": "json"}},
                        }

                    # Extract Query Params
                    query = []
                    for qp in details.get("query_params", []):
                        query.append(
                            {"key": qp, "value": "", "description": "Query parameter"}
                        )

                    # Path Variables
                    variables = []
                    path_vars = re.findall(r":([^/]+)", pm_path_str)
                    for pv in path_vars:
                        variables.append(
                            {"key": pv, "value": "", "description": "Path variable"}
                        )

                    item = {
                        "name": request_name,
                        "request": {
                            "method": method,
                            "header": [
                                {
                                    "key": "Content-Type",
                                    "value": "application/json",
                                    "type": "text",
                                }
                            ],
                            "body": body,
                            "url": {
                                "raw": "{{base_url}}" + pm_path_str,
                                "host": ["{{base_url}}"],
                                "path": path_segments,
                                "query": query,
                                "variable": variables,
                            },
                            "description": spec.get("doc", "").strip(),
                        },
                        "response": [],
                    }
                    resource_folder["item"].append(item)

            version_folder["item"].append(resource_folder)

        collection["item"].append(version_folder)

    return collection

