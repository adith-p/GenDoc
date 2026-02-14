import ast
import re
from pathlib import Path

# --- CONSTANTS: DRF Generic View Defaults ---
GENERIC_DEFAULTS = {
    "ListAPIView": {"methods": ["GET"]},
    "RetrieveAPIView": {"methods": ["GET"]},
    "CreateAPIView": {"methods": ["POST"]},
    "UpdateAPIView": {"methods": ["PUT", "PATCH"]},
    "DestroyAPIView": {"methods": ["DELETE"]},
    "ListCreateAPIView": {"methods": ["GET", "POST"]},
    "RetrieveUpdateAPIView": {"methods": ["GET", "PUT", "PATCH"]},
    "RetrieveDestroyAPIView": {"methods": ["GET", "DELETE"]},
    "RetrieveUpdateDestroyAPIView": {"methods": ["GET", "PUT", "PATCH", "DELETE"]},
    "ModelViewSet": {"methods": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
    "ReadOnlyModelViewSet": {"methods": ["GET"]},
    "ViewSet": {"methods": []},
    "GenericViewSet": {"methods": []},
}


# --- HELPER: Extract View Name ---
def get_view_name_from_node(node):
    """Extract view name from URL pattern node."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == "as_view":
            if isinstance(node.func.value, ast.Attribute):
                return node.func.value.attr
            elif isinstance(node.func.value, ast.Name):
                return node.func.value.id
    elif isinstance(node, ast.Attribute):
        return node.attr
    elif isinstance(node, ast.Name):
        return node.id
    return "Unknown"


# --- SETTINGS SCANNER ---
class SettingsScanner(ast.NodeVisitor):
    """Scans settings.py to detect installed schema frameworks."""

    def __init__(self):
        self.found_frameworks = set()

    def visit_Assign(self, node):
        # Check for INSTALLED_APPS = [...]
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "INSTALLED_APPS":
                if isinstance(node.value, ast.List):
                    for elt in node.value.elts:
                        val = None
                        if isinstance(elt, ast.Constant):
                            val = elt.value
                        elif isinstance(elt, ast.Str):
                            val = elt.s

                        if val:
                            if "drf_spectacular" in val:
                                self.found_frameworks.add("drf-spectacular")
                            if "drf_yasg" in val:
                                self.found_frameworks.add("drf-yasg")
        self.generic_visit(node)


# --- MODEL SCANNER ---
class ModelScanner(ast.NodeVisitor):
    """Scans models.py files to extract field definitions."""

    def __init__(self):
        self.models = {}  # { 'ModelName': { 'field_name': { 'type': ..., 'props': ... } } }
        self.current_model = None

    def visit_ClassDef(self, node):
        # Heuristic: Check if class inherits from 'Model'
        is_model = False
        for base in node.bases:
            if isinstance(base, ast.Name) and "Model" in base.id:
                is_model = True
            elif isinstance(base, ast.Attribute) and "Model" in base.attr:
                is_model = True

        if is_model:
            self.current_model = node.name
            self.models[self.current_model] = {}
            self.generic_visit(node)
            self.current_model = None
        else:
            self.generic_visit(node)

    def visit_Assign(self, node):
        if self.current_model:
            if isinstance(node.value, ast.Call):
                type_name = None
                # Check for models.CharField or CharField
                if isinstance(node.value.func, ast.Attribute):
                    if "Field" in node.value.func.attr:
                        type_name = node.value.func.attr
                elif isinstance(node.value.func, ast.Name):
                    if "Field" in node.value.func.id:
                        type_name = node.value.func.id

                if type_name:
                    props = []
                    for kw in node.value.keywords:
                        if kw.arg in ["null", "blank"]:
                            if (
                                isinstance(kw.value, ast.Constant)
                                and kw.value.value is True
                            ):
                                if "Nullable" not in props:
                                    props.append("Nullable")

                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.models[self.current_model][target.id] = {
                                "type": type_name,
                                "props": props,
                            }


# --- SERIALIZER SCANNER ---
class SerializerScanner(ast.NodeVisitor):
    """Scans serializer files to extract field definitions."""

    def __init__(self, models_map=None):
        self.serializers = {}  # { 'SerializerName': { 'fields': { 'name': {type, props} } } }
        self.current_class = None
        self.models_map = models_map or {}

        # State for Meta class parsing
        self.meta_model = None
        self.meta_fields = None

    def visit_ClassDef(self, node):
        # Heuristic: Check if class name ends with 'Serializer'
        if "Serializer" in node.name:
            self.current_class = node.name
            self.serializers[self.current_class] = {"fields": {}}
            self.meta_model = None
            self.meta_fields = None

            self.generic_visit(node)

            # Post-processing: Merge model fields if ModelSerializer
            if self.meta_model and self.meta_model in self.models_map:
                model_fields = self.models_map[self.meta_model]
                current_fields = self.serializers[self.current_class]["fields"]

                # If fields='__all__', include everything not already defined
                if self.meta_fields == "__all__":
                    for fname, fdef in model_fields.items():
                        if fname not in current_fields:
                            current_fields[fname] = fdef

                # If fields=['a', 'b'], include specific fields
                elif isinstance(self.meta_fields, list):
                    for fname in self.meta_fields:
                        if fname in model_fields and fname not in current_fields:
                            current_fields[fname] = model_fields[fname]

            self.current_class = None

        elif self.current_class and node.name == "Meta":
            # Handle inner Meta class for ModelSerializers
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            if target.id == "model":
                                # Extract model name (e.g., model = User or model = models.User)
                                if isinstance(item.value, ast.Name):
                                    self.meta_model = item.value.id
                                elif isinstance(item.value, ast.Attribute):
                                    self.meta_model = item.value.attr
                            elif target.id == "fields":
                                # Extract fields list
                                if (
                                    isinstance(item.value, ast.Constant)
                                    and item.value.value == "__all__"
                                ):
                                    self.meta_fields = "__all__"
                                elif isinstance(item.value, ast.List):
                                    self.meta_fields = []
                                    for elt in item.value.elts:
                                        if isinstance(elt, ast.Constant):
                                            self.meta_fields.append(elt.value)
                                        elif isinstance(elt, ast.Str):  # Python < 3.8
                                            self.meta_fields.append(elt.s)

        else:
            self.generic_visit(node)

    def visit_Assign(self, node):
        if (
            self.current_class and self.current_class != "Meta"
        ):  # Don't parse assignments inside Meta as explicit fields
            # Look for: field = serializers.XField() or field = XField()
            if isinstance(node.value, ast.Call):
                type_name = None
                is_field = False

                # Extract Field Type
                if isinstance(node.value.func, ast.Attribute):
                    # Case: serializers.CharField
                    if (
                        "Field" in node.value.func.attr
                        or "Serializer" in node.value.func.attr
                    ):
                        type_name = node.value.func.attr
                        is_field = True
                elif isinstance(node.value.func, ast.Name):
                    # Case: CharField
                    if (
                        "Field" in node.value.func.id
                        or "Serializer" in node.value.func.id
                    ):
                        type_name = node.value.func.id
                        is_field = True

                if is_field:
                    # Extract Properties (required, read_only, etc.)
                    props = []

                    # Heuristics for props based on keywords
                    for kw in node.value.keywords:
                        # Handle required=False (Optional)
                        if kw.arg == "required":
                            if (
                                isinstance(kw.value, ast.Constant)
                                and kw.value.value is False
                            ):
                                props.append("Optional")

                        # Handle read_only=True
                        if kw.arg == "read_only":
                            if (
                                isinstance(kw.value, ast.Constant)
                                and kw.value.value is True
                            ):
                                props.append("ReadOnly")

                        # Handle write_only=True
                        if kw.arg == "write_only":
                            if (
                                isinstance(kw.value, ast.Constant)
                                and kw.value.value is True
                            ):
                                props.append("WriteOnly")

                        # Handle many=True (List)
                        if kw.arg == "many":
                            if (
                                isinstance(kw.value, ast.Constant)
                                and kw.value.value is True
                            ):
                                type_name = f"List[{type_name}]"

                        # Handle allow_null=True
                        if kw.arg == "allow_null":
                            if (
                                isinstance(kw.value, ast.Constant)
                                and kw.value.value is True
                            ):
                                props.append("Nullable")

                        # Handle child=... (ListField)
                        if kw.arg == "child":
                            child_type = None
                            # child=Serializer() or child=serializers.Serializer()
                            if isinstance(kw.value, ast.Call):
                                if isinstance(kw.value.func, ast.Name):
                                    child_type = kw.value.func.id
                                elif isinstance(kw.value.func, ast.Attribute):
                                    child_type = kw.value.func.attr

                            if child_type:
                                type_name = f"List[{child_type}]"

                    # Register field for all targets
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.serializers[self.current_class]["fields"][
                                target.id
                            ] = {
                                "type": type_name,
                                "props": props,
                            }


# --- SERVICE SCANNER ---
class ServiceScanner(ast.NodeVisitor):
    """Scans service layer files to detect serializer usage."""

    def __init__(self):
        self.service_methods = {}
        self.current_class = None

    def visit_ClassDef(self, node):
        if any(x in node.name for x in ["Service", "Manager", "Handler"]):
            self.current_class = node.name
            self.generic_visit(node)
            self.current_class = None
        else:
            self.generic_visit(node)

    def visit_FunctionDef(self, node):
        if not self.current_class:
            return

        input_ser = None
        output_ser = None

        for item in ast.walk(node):
            if isinstance(item, ast.Call):
                if isinstance(item.func, ast.Name) and "Serializer" in item.func.id:
                    ser_name = item.func.id
                    has_data = any(
                        kw.arg in ["data", "partial"] for kw in item.keywords
                    )
                    if has_data:
                        input_ser = ser_name
                    else:
                        output_ser = ser_name

        key = f"{self.current_class}.{node.name}"
        self.service_methods[key] = {
            "input": input_ser,
            "output": output_ser,
        }


# --- METHOD BODY VISITOR ---
class MethodBodyVisitor(ast.NodeVisitor):
    """Recursively analyzes a view method to detect serializer usage with data flow tracking."""

    def __init__(self, class_serializer, method_name, service_map=None):
        self.class_serializer = class_serializer
        self.method_name = method_name.upper()
        self.service_map = service_map or {}

        self.vars = {}
        self.input_serializer = None
        self.input_source = None
        self.responses = {}
        self.serializer_used = False
        self.raw_input_fields = set()

    def _register_var(self, name, class_name, var_type):
        self.vars[name] = {"class": class_name, "type": var_type}

    def _get_var(self, name):
        return self.vars.get(name)

    # ---- VARIABLE TRACKING & REQUEST DETECTION ----
    def visit_Assign(self, node):
        if isinstance(node.value, ast.Call):
            func_name = None
            if isinstance(node.value.func, ast.Name):
                func_name = node.value.func.id
            elif isinstance(node.value.func, ast.Attribute):
                if node.value.func.attr == "get_serializer":
                    func_name = self.class_serializer

            if func_name and "Serializer" in func_name:
                self.serializer_used = True
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._register_var(target.id, func_name, "instance")

                is_input = False
                for kw in node.value.keywords:
                    if kw.arg == "data":
                        is_input = True
                    if (
                        isinstance(kw.value, ast.Attribute)
                        and isinstance(kw.value.value, ast.Name)
                        and kw.value.value.id == "request"
                        and kw.value.attr == "data"
                    ):
                        is_input = True

                for arg in node.value.args:
                    if (
                        isinstance(arg, ast.Attribute)
                        and isinstance(arg.value, ast.Name)
                        and arg.value.id == "request"
                        and arg.attr == "data"
                    ):
                        is_input = True

                if is_input and not self.input_serializer:
                    self.input_serializer = func_name
                    self.input_source = "direct"

        elif isinstance(node.value, ast.Attribute) and node.value.attr == "data":
            if isinstance(node.value.value, ast.Name):
                source_var = node.value.value.id
                info = self._get_var(source_var)
                if info and info["type"] == "instance":
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self._register_var(target.id, info["class"], "data")

        elif isinstance(node.value, ast.Dict):
            found_class = None
            for val in node.value.values:
                if (
                    isinstance(val, ast.Attribute)
                    and val.attr == "data"
                    and isinstance(val.value, ast.Name)
                ):
                    info = self._get_var(val.value.id)
                    if info and info["type"] == "instance":
                        found_class = info["class"]
                        break
                elif isinstance(val, ast.Name):
                    info = self._get_var(val.id)
                    if info and info["type"] == "data":
                        found_class = info["class"]
                        break

            if found_class:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._register_var(target.id, found_class, "data")

        self.generic_visit(node)

    # ---- RAW DATA ACCESS DETECTION ----
    def visit_Subscript(self, node):
        # request.data['key']
        if (
            isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "request"
            and node.value.attr == "data"
        ):
            if isinstance(node.slice, ast.Constant):  # Python 3.9+
                self.raw_input_fields.add(str(node.slice.value))
            elif isinstance(node.slice, ast.Str):  # Python < 3.9
                self.raw_input_fields.add(node.slice.s)
        self.generic_visit(node)

    # ---- SERVICE CALL DETECTION ----
    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute):
            # Check for request.data.get('key')
            if (
                node.func.attr == "get"
                and isinstance(node.func.value, ast.Attribute)
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "request"
                and node.func.value.attr == "data"
            ):
                if node.args and isinstance(node.args[0], ast.Constant):
                    self.raw_input_fields.add(str(node.args[0].value))
                elif node.args and isinstance(node.args[0], ast.Str):
                    self.raw_input_fields.add(node.args[0].s)

            # Check for Service calls
            elif isinstance(node.func.value, ast.Name):
                service_class = node.func.value.id
                method_name = node.func.attr
                key = f"{service_class}.{method_name}"

                if key in self.service_map:
                    info = self.service_map[key]
                    if not self.input_serializer and info["input"]:
                        self.input_serializer = info["input"]
                        self.input_source = f"service:{key}"

                    if info["output"] and "200" not in self.responses:
                        self.responses["200"] = {
                            "serializer": info["output"],
                            "source": f"service:{key}",
                        }

        self.generic_visit(node)

    # ---- RESPONSE DETECTION ----
    def visit_Return(self, node):
        if node.value and isinstance(node.value, ast.Call):
            if (
                isinstance(node.value.func, ast.Name)
                and node.value.func.id == "Response"
            ):
                status_code = "200"
                data_node = None

                if node.value.args:
                    data_node = node.value.args[0]

                for kw in node.value.keywords:
                    if kw.arg == "data":
                        data_node = kw.value
                    if kw.arg == "status":
                        val_str = ast.dump(kw.value)
                        m = re.search(r"HTTP_(\d+)", val_str)
                        if m:
                            status_code = m.group(1)
                        elif isinstance(kw.value, ast.Constant):
                            status_code = str(kw.value.value)
                        elif "204" in val_str:
                            status_code = "204"

                found_ser = None
                found_src = None

                if data_node:
                    if isinstance(data_node, ast.Name):
                        info = self._get_var(data_node.id)
                        if info and info["type"] in ["data", "instance"]:
                            found_ser = info["class"]
                            found_src = "direct_var"

                    elif isinstance(data_node, ast.Attribute):
                        if isinstance(data_node.value, ast.Name):
                            info = self._get_var(data_node.value.id)
                            if info and info["type"] == "instance":
                                found_ser = info["class"]
                                found_src = "direct_attr"

                    elif isinstance(data_node, ast.Dict):
                        for val in data_node.values:
                            if (
                                isinstance(val, ast.Attribute)
                                and val.attr == "data"
                                and isinstance(val.value, ast.Name)
                            ):
                                info = self._get_var(val.value.id)
                                if info and info["type"] == "instance":
                                    found_ser = info["class"]
                                    found_src = "dict_attr"
                                    break
                            elif isinstance(val, ast.Name):
                                info = self._get_var(val.id)
                                if info and info["type"] == "data":
                                    found_ser = info["class"]
                                    found_src = "dict_var"
                                    break

                    elif (
                        isinstance(data_node, ast.Attribute)
                        and data_node.attr == "data"
                    ):
                        if isinstance(data_node.value, ast.Call):
                            if isinstance(data_node.value.func, ast.Name):
                                name = data_node.value.func.id
                                if "Serializer" in name:
                                    found_ser = name
                                    found_src = "inline_instantiation"

                if found_ser:
                    self.responses[status_code] = {
                        "serializer": found_ser,
                        "source": found_src,
                    }
                elif not found_ser:
                    if status_code == "204":
                        self.responses[status_code] = {
                            "serializer": "NoContent",
                            "source": "status_code",
                        }
                    elif data_node:
                        if isinstance(data_node, ast.Dict):
                            keys = []
                            for k in data_node.keys:
                                if k is None:
                                    continue
                                if isinstance(k, ast.Constant):
                                    keys.append(str(k.value))
                                elif isinstance(k, ast.Str):
                                    keys.append(k.s)

                            label = "DynamicObject"
                            if keys:
                                key_str = ", ".join(keys)
                                if len(key_str) > 50:
                                    key_str = key_str[:47] + "..."
                                label = f"Object {{{key_str}}}"

                            self.responses[status_code] = {
                                "serializer": label,
                                "source": "raw_dict",
                            }
                        elif isinstance(data_node, ast.List):
                            self.responses[status_code] = {
                                "serializer": "DynamicList",
                                "source": "raw_list",
                            }

        self.generic_visit(node)


def analyze_method_logic(
    method_node, class_serializer="None", method_name="", service_map=None
):
    """Analyze a view method to extract request/response serializers."""
    visitor = MethodBodyVisitor(class_serializer, method_name, service_map)
    visitor.visit(method_node)

    if not visitor.input_serializer and not visitor.serializer_used:
        if visitor.raw_input_fields:
            # Construct RawBody label with detected keys
            keys_str = ", ".join(sorted(visitor.raw_input_fields))
            visitor.input_serializer = f"RawBody {{{keys_str}}}"
            visitor.input_source = "direct_raw_keys"
        else:
            # Fallback scan for generic request.data usage without specific keys
            for node in ast.walk(method_node):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "request"
                    and node.attr == "data"
                ):
                    visitor.input_serializer = "RawBody"
                    visitor.input_source = "direct_raw"
                    break

    return (
        (visitor.input_serializer, visitor.input_source),
        visitor.responses,
    )


# --- VIEW VISITOR ---
class ViewVisitor(ast.NodeVisitor):
    """Scans view classes to extract API endpoint information."""

    def __init__(self, service_map=None):
        self.views = {}
        self.service_map = service_map or {}

    def visit_ClassDef(self, node):
        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        is_drf = any(b in GENERIC_DEFAULTS or "APIView" in b for b in bases)

        if not is_drf:
            self.generic_visit(node)
            return

        doc = ast.get_docstring(node) or "No description."
        class_serializer = None

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "serializer_class":
                        if isinstance(item.value, ast.Name):
                            class_serializer = item.value.id

        if not class_serializer:
            for item in node.body:
                if (
                    isinstance(item, ast.FunctionDef)
                    and item.name == "get_serializer_class"
                ):
                    for stmt in item.body:
                        if isinstance(stmt, ast.Return) and isinstance(
                            stmt.value, ast.Name
                        ):
                            class_serializer = stmt.value.id
                            break

        methods = {}

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name in ["get", "post", "put", "delete", "patch"]:
                    (req_ser, req_src), response_map = analyze_method_logic(
                        item, class_serializer, item.name, self.service_map
                    )

                    verb = item.name.upper()

                    if not req_ser:
                        if verb in ["POST", "PUT", "PATCH"] and class_serializer:
                            req_ser = class_serializer
                            req_src = "class_default"
                        elif verb == "GET":
                            req_ser = "NoBody"
                            req_src = "no_body"
                        else:
                            req_ser = "NoBody"
                            req_src = "no_body"

                    if not response_map:
                        default_status = (
                            "201"
                            if verb == "POST"
                            else "204"
                            if verb == "DELETE"
                            else "200"
                        )
                        if verb == "DELETE":
                            response_map = {
                                "204": {
                                    "serializer": "NoContent",
                                    "source": "no_content",
                                }
                            }
                        elif class_serializer:
                            response_map = {
                                default_status: {
                                    "serializer": class_serializer,
                                    "source": "class_default",
                                }
                            }
                        else:
                            response_map = {
                                default_status: {
                                    "serializer": "Unknown",
                                    "source": "unknown",
                                }
                            }

                    res_parts = []
                    for code in sorted(response_map.keys()):
                        res_parts.append(f"{code}: {response_map[code]['serializer']}")
                    res_ser_str = ", ".join(res_parts)

                    methods[verb] = {
                        "request": req_ser,
                        "response": res_ser_str,
                        "response_details": response_map,
                        "req_source": req_src,
                        "res_source": "composite",
                    }

        for base in bases:
            if base in GENERIC_DEFAULTS:
                for method in GENERIC_DEFAULTS[base]["methods"]:
                    if method not in methods:
                        req_ser = "NoBody"
                        req_src = "generic_default"

                        if method == "DELETE":
                            res_map = {"204": {"serializer": "NoContent"}}
                            res_ser_str = "204: NoContent"
                        elif method == "POST":
                            s = class_serializer or "Unknown"
                            res_map = {"201": {"serializer": s}}
                            res_ser_str = f"201: {s}"
                        else:
                            s = class_serializer or "Unknown"
                            res_map = {"200": {"serializer": s}}
                            res_ser_str = f"200: {s}"

                        if method == "GET":
                            req_ser = "NoBody"
                        elif method in ["POST", "PUT", "PATCH"]:
                            req_ser = class_serializer or "Unknown"

                        methods[method] = {
                            "request": req_ser,
                            "response": res_ser_str,
                            "response_details": res_map,
                            "req_source": req_src,
                            "res_source": "generic_default",
                        }

        self.views[node.name] = {
            "doc": doc,
            "methods": methods,
            "bases": bases,
        }

        self.generic_visit(node)


# --- URL VISITOR ---
class URLVisitor(ast.NodeVisitor):
    """Scans urls.py files to map URL patterns to views."""

    def __init__(self, current_prefix=""):
        self.patterns = []
        self.prefix = current_prefix

    def visit_Assign(self, node):
        is_urlpatterns = False
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "urlpatterns":
                is_urlpatterns = True

        if is_urlpatterns and isinstance(node.value, ast.List):
            for item in node.value.elts:
                if isinstance(item, ast.Call) and isinstance(item.func, ast.Name):
                    if item.func.id in ["path", "re_path"]:
                        self.process_path(item)

    def process_path(self, node):
        route = ""
        if isinstance(node.args[0], ast.Constant):
            route = node.args[0].value
        elif isinstance(node.args[0], ast.Str):
            route = node.args[0].s

        full_route = self.prefix + route
        view_node = node.args[1]

        if (
            isinstance(view_node, ast.Call)
            and isinstance(view_node.func, ast.Name)
            and view_node.func.id == "include"
        ):
            self.patterns.append({"path": full_route + "*", "view": "INCLUDE"})
        else:
            self.patterns.append(
                {"path": full_route, "view": get_view_name_from_node(view_node)}
            )


# --- PROJECT SCANNER ---
def detect_schema_frameworks(root_path):
    root = Path(root_path)
    frameworks = set()
    for path in root.rglob("settings.py"):
        if ".venv" in path.parts:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
                scanner = SettingsScanner()
                scanner.visit(tree)
                frameworks.update(scanner.found_frameworks)
        except:
            continue
    return list(frameworks)


def find_generated_schemas(root_path):
    """Searches for common OpenAPI/Swagger schema files."""
    root = Path(root_path)
    common_names = [
        "schema.yml",
        "schema.yaml",
        "openapi.yml",
        "openapi.yaml",
        "openapi.json",
        "swagger.yml",
        "swagger.yaml",
        "swagger.json",
    ]
    found_files = []

    for path in root.rglob("*"):
        if (
            ".venv" in path.parts
            or "node_modules" in path.parts
            or "migrations" in path.parts
        ):
            continue
        if path.name in common_names and path.is_file():
            found_files.append(str(path))

    return found_files


def scan_project(root_path: str, callback=None):
    """
    Scans a Django REST Framework project to generate API documentation.

    Returns:
        Tuple (endpoints_list, serializers_map)
    """
    root = Path(root_path)
    all_views = {}
    all_urls = []
    service_map = {}
    serializers_map = {}
    models_map = {}

    # Phase 0a: Scan Models
    if callback:
        callback("Phase 0a: Scanning models...")
    for path in root.rglob("*.py"):
        if ".venv" in path.parts or "migrations" in path.parts:
            continue
        # Optimization: Only scan if "models" in path or content likely contains models
        if "models" in path.name or "models" in str(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                    scanner = ModelScanner()
                    scanner.visit(tree)
                    models_map.update(scanner.models)
            except:
                continue

    # Phase 0b: Scan Serializers
    if callback:
        callback("Phase 0b: Scanning serializers...")
    for path in root.rglob("*.py"):
        if ".venv" in path.parts or "migrations" in path.parts:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
                scanner = SerializerScanner(models_map=models_map)
                scanner.visit(tree)
                serializers_map.update(scanner.serializers)
        except:
            continue

    # Phase 1: Scan service layer
    if callback:
        callback("Phase 1: Scanning service layer...")

    for path in root.rglob("*.py"):
        if ".venv" in path.parts or "migrations" in path.parts:
            continue

        if any(keyword in path.name for keyword in ["service", "manager", "handler"]):
            try:
                if callback:
                    callback(f"Analyzing {path.name}...")
                with open(path, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                    scanner = ServiceScanner()
                    scanner.visit(tree)
                    service_map.update(scanner.service_methods)
            except:
                continue

    # Phase 2: Scan views
    if callback:
        callback("Phase 2: Scanning views...")

    for path in root.rglob("*.py"):
        if ".venv" in path.parts or "migrations" in path.parts:
            continue

        try:
            if callback:
                callback(f"Parsing {path.name}...")
            with open(path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
                visitor = ViewVisitor(service_map)
                visitor.visit(tree)
                all_views.update(visitor.views)
        except:
            continue

    # Phase 3: Scan URLs
    if callback:
        callback("Phase 3: Mapping URLs...")

    for path in root.rglob("urls.py"):
        if ".venv" in path.parts or "migrations" in path.parts:
            continue

        try:
            if callback:
                callback(f"Mapping {path.parent.name}/urls.py...")
            with open(path, "r", encoding="utf-8") as f:
                prefix = (
                    ""
                    if path.parent.name in ["config", "root"]
                    else f"{path.parent.name}/"
                )
                tree = ast.parse(f.read())
                visitor = URLVisitor(current_prefix=prefix)
                visitor.visit(tree)
                all_urls.extend(visitor.patterns)
        except:
            continue

    # Phase 4: Link views to URLs
    if callback:
        callback("Phase 4: Linking views to URLs...")

    final_docs = []
    for url in all_urls:
        v_name = url["view"]
        if v_name in all_views:
            v_data = all_views[v_name]
            final_docs.append(
                {
                    "path": "/" + url["path"].lstrip("/"),
                    "view": v_name,
                    "doc": v_data["doc"],
                    "methods": v_data["methods"],
                }
            )

    return final_docs, serializers_map
