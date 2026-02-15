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


# --- SCANNERS ---


class SettingsScanner(ast.NodeVisitor):
    def __init__(self):
        self.found_frameworks = set()

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "INSTALLED_APPS":
                if isinstance(node.value, ast.List):
                    for elt in node.value.elts:
                        val = (
                            elt.value
                            if isinstance(elt, ast.Constant)
                            else elt.s
                            if isinstance(elt, ast.Str)
                            else None
                        )
                        if val:
                            if "drf_spectacular" in val:
                                self.found_frameworks.add("drf-spectacular")
                            if "drf_yasg" in val:
                                self.found_frameworks.add("drf-yasg")
        self.generic_visit(node)


class ModelScanner(ast.NodeVisitor):
    def __init__(self):
        self.models = {}
        self.current_model = None

    def visit_ClassDef(self, node):
        is_model = any(
            (isinstance(b, ast.Name) and "Model" in b.id)
            or (isinstance(b, ast.Attribute) and "Model" in b.attr)
            for b in node.bases
        )
        if is_model:
            self.current_model = node.name
            self.models[self.current_model] = {}
            self.generic_visit(node)
            self.current_model = None
        else:
            self.generic_visit(node)

    def visit_Assign(self, node):
        if self.current_model and isinstance(node.value, ast.Call):
            type_name = None
            if (
                isinstance(node.value.func, ast.Attribute)
                and "Field" in node.value.func.attr
            ):
                type_name = node.value.func.attr
            elif (
                isinstance(node.value.func, ast.Name) and "Field" in node.value.func.id
            ):
                type_name = node.value.func.id
            if type_name:
                props = []
                for kw in node.value.keywords:
                    if (
                        kw.arg in ["null", "blank"]
                        and isinstance(kw.value, ast.Constant)
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


class SerializerScanner(ast.NodeVisitor):
    def __init__(self, models_map=None):
        self.serializers = {}
        self.current_class = None
        self.models_map = models_map or {}
        self.meta_model = None
        self.meta_fields = None

    def visit_ClassDef(self, node):
        if "Serializer" in node.name:
            self.current_class = node.name
            self.serializers[self.current_class] = {"fields": {}}
            self.meta_model = None
            self.meta_fields = None
            self.generic_visit(node)
            if self.meta_model and self.meta_model in self.models_map:
                model_fields = self.models_map[self.meta_model]
                current_fields = self.serializers[self.current_class]["fields"]
                if self.meta_fields == "__all__":
                    for fname, fdef in model_fields.items():
                        if fname not in current_fields:
                            current_fields[fname] = fdef
                elif isinstance(self.meta_fields, list):
                    for fname in self.meta_fields:
                        if fname in model_fields and fname not in current_fields:
                            current_fields[fname] = model_fields[fname]
            self.current_class = None
        elif self.current_class and node.name == "Meta":
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            if target.id == "model":
                                if isinstance(item.value, ast.Name):
                                    self.meta_model = item.value.id
                                elif isinstance(item.value, ast.Attribute):
                                    self.meta_model = item.value.attr
                            elif target.id == "fields":
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
                                        elif isinstance(elt, ast.Str):
                                            self.meta_fields.append(elt.s)
        else:
            self.generic_visit(node)

    def visit_Assign(self, node):
        if (
            self.current_class
            and self.current_class != "Meta"
            and isinstance(node.value, ast.Call)
        ):
            type_name = None
            if isinstance(node.value.func, ast.Attribute) and (
                "Field" in node.value.func.attr or "Serializer" in node.value.func.attr
            ):
                type_name = node.value.func.attr
            elif isinstance(node.value.func, ast.Name) and (
                "Field" in node.value.func.id or "Serializer" in node.value.func.id
            ):
                type_name = node.value.func.id
            if type_name:
                props = []
                for kw in node.value.keywords:
                    if (
                        kw.arg == "required"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is False
                    ):
                        props.append("Optional")
                    if (
                        kw.arg == "read_only"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        props.append("ReadOnly")
                    if (
                        kw.arg == "write_only"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        props.append("WriteOnly")
                    if (
                        kw.arg == "many"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        type_name = f"List[{type_name}]"
                    if (
                        kw.arg == "allow_null"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        props.append("Nullable")
                    if kw.arg == "child" and isinstance(kw.value, ast.Call):
                        if isinstance(kw.value.func, ast.Name):
                            type_name = f"List[{kw.value.func.id}]"
                        elif isinstance(kw.value.func, ast.Attribute):
                            type_name = f"List[{kw.value.func.attr}]"
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.serializers[self.current_class]["fields"][target.id] = {
                            "type": type_name,
                            "props": props,
                        }


class ServiceScanner(ast.NodeVisitor):
    """Scans service layer files to detect serializer usage and query parameter access."""

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
        input_ser, output_ser = None, None
        detected_qps = set()

        # Track argument names to detect if query params are accessed on arguments (likely request)
        args = [a.arg for a in node.args.args]

        # Track aliases: qp = request.query_params
        qp_aliases = set()

        for item in ast.walk(node):
            # Track alias assignments
            if isinstance(item, ast.Assign):
                if isinstance(item.value, ast.Attribute):
                    if (
                        isinstance(item.value.value, ast.Name)
                        and item.value.value.id in args
                    ):
                        if item.value.attr in ["query_params", "GET"]:
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    qp_aliases.add(target.id)

            # Serializer usage
            if (
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Name)
                and "Serializer" in item.func.id
            ):
                if any(kw.arg in ["data", "partial"] for kw in item.keywords):
                    input_ser = item.func.id
                else:
                    output_ser = item.func.id

            # Query Param usage: subscript access
            if isinstance(item, ast.Subscript):
                # Direct: request.query_params['key']
                if isinstance(item.value, ast.Attribute) and item.value.attr in [
                    "query_params",
                    "GET",
                ]:
                    if (
                        isinstance(item.value.value, ast.Name)
                        and item.value.value.id in args
                    ):
                        val = (
                            item.slice.value
                            if isinstance(item.slice, ast.Constant)
                            else item.slice.s
                            if isinstance(item.slice, ast.Str)
                            else None
                        )
                        if val:
                            detected_qps.add(str(val))
                # Alias: qp['key']
                elif isinstance(item.value, ast.Name) and item.value.id in qp_aliases:
                    val = (
                        item.slice.value
                        if isinstance(item.slice, ast.Constant)
                        else item.slice.s
                        if isinstance(item.slice, ast.Str)
                        else None
                    )
                    if val:
                        detected_qps.add(str(val))

            # Query Param usage: .get() method
            if (
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Attribute)
                and item.func.attr == "get"
            ):
                # Direct: request.query_params.get('key')
                if isinstance(
                    item.func.value, ast.Attribute
                ) and item.func.value.attr in [
                    "query_params",
                    "GET",
                ]:
                    if (
                        isinstance(item.func.value.value, ast.Name)
                        and item.func.value.value.id in args
                    ):
                        if item.args:
                            val = (
                                item.args[0].value
                                if isinstance(item.args[0], ast.Constant)
                                else item.args[0].s
                                if isinstance(item.args[0], ast.Str)
                                else None
                            )
                            if val:
                                detected_qps.add(str(val))
                # Alias: qp.get('key')
                elif (
                    isinstance(item.func.value, ast.Name)
                    and item.func.value.id in qp_aliases
                ):
                    if item.args:
                        val = (
                            item.args[0].value
                            if isinstance(item.args[0], ast.Constant)
                            else item.args[0].s
                            if isinstance(item.args[0], ast.Str)
                            else None
                        )
                        if val:
                            detected_qps.add(str(val))

        self.service_methods[f"{self.current_class}.{node.name}"] = {
            "input": input_ser,
            "output": output_ser,
            "query_params": list(detected_qps),
        }


class MethodBodyVisitor(ast.NodeVisitor):
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
        self.query_params = set()  # Store detected query parameters
        self.query_param_aliases = set()  # Track variables holding request.query_params

    def _register_var(self, name, class_name, var_type):
        self.vars[name] = {"class": class_name, "type": var_type}

    def _get_var(self, name):
        return self.vars.get(name)

    def visit_Assign(self, node):
        # Detect aliases: qp = request.query_params or qp = request.GET
        if (
            isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "request"
        ):
            if node.value.attr in ["query_params", "GET"]:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.query_param_aliases.add(target.id)

        # Existing logic for serializers/request.data
        if isinstance(node.value, ast.Call):
            func_name = None
            if isinstance(node.value.func, ast.Name):
                func_name = node.value.func.id
            elif (
                isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr == "get_serializer"
            ):
                func_name = self.class_serializer
            if func_name and "Serializer" in func_name:
                self.serializer_used = True
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._register_var(target.id, func_name, "instance")
                is_input = any(
                    kw.arg == "data"
                    or (
                        isinstance(kw.value, ast.Attribute)
                        and kw.value.value.id == "request"
                        and kw.value.attr == "data"
                    )
                    for kw in node.value.keywords
                )
                is_input = is_input or any(
                    isinstance(arg, ast.Attribute)
                    and arg.value.id == "request"
                    and arg.attr == "data"
                    for arg in node.value.args
                )
                if is_input and not self.input_serializer:
                    self.input_serializer = func_name
                    self.input_source = "direct"
        elif (
            isinstance(node.value, ast.Attribute)
            and node.value.attr == "data"
            and isinstance(node.value.value, ast.Name)
        ):
            info = self._get_var(node.value.value.id)
            if info and info["type"] == "instance":
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._register_var(target.id, info["class"], "data")
        self.generic_visit(node)

    def visit_Subscript(self, node):
        # request.data['key']
        if (
            isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "request"
        ):
            # Data keys
            if node.value.attr == "data":
                val = (
                    node.slice.value
                    if isinstance(node.slice, ast.Constant)
                    else node.slice.s
                    if isinstance(node.slice, ast.Str)
                    else None
                )
                if val:
                    self.raw_input_fields.add(str(val))
            # Query Params keys: request.query_params['key'] or request.GET['key']
            elif node.value.attr in ["query_params", "GET"]:
                val = (
                    node.slice.value
                    if isinstance(node.slice, ast.Constant)
                    else node.slice.s
                    if isinstance(node.slice, ast.Str)
                    else None
                )
                if val:
                    self.query_params.add(str(val))

        # Alias usage: qp['key']
        elif (
            isinstance(node.value, ast.Name)
            and node.value.id in self.query_param_aliases
        ):
            val = (
                node.slice.value
                if isinstance(node.slice, ast.Constant)
                else node.slice.s
                if isinstance(node.slice, ast.Str)
                else None
            )
            if val:
                self.query_params.add(str(val))

        self.generic_visit(node)

    def visit_Call(self, node):
        # Detect request.data.get() or request.query_params.get()
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "get":
                # Check direct access: request.data.get / request.query_params.get
                if (
                    isinstance(node.func.value, ast.Attribute)
                    and isinstance(node.func.value.value, ast.Name)
                    and node.func.value.value.id == "request"
                ):
                    # request.data.get('key')
                    if node.func.value.attr == "data":
                        if node.args:
                            val = (
                                node.args[0].value
                                if isinstance(node.args[0], ast.Constant)
                                else node.args[0].s
                                if isinstance(node.args[0], ast.Str)
                                else None
                            )
                            if val:
                                self.raw_input_fields.add(str(val))
                    # request.query_params.get('key')
                    elif node.func.value.attr in ["query_params", "GET"]:
                        if node.args:
                            val = (
                                node.args[0].value
                                if isinstance(node.args[0], ast.Constant)
                                else node.args[0].s
                                if isinstance(node.args[0], ast.Str)
                                else None
                            )
                            if val:
                                self.query_params.add(str(val))

                # Check alias access: qp.get('key')
                elif (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id in self.query_param_aliases
                ):
                    if node.args:
                        val = (
                            node.args[0].value
                            if isinstance(node.args[0], ast.Constant)
                            else node.args[0].s
                            if isinstance(node.args[0], ast.Str)
                            else None
                        )
                        if val:
                            self.query_params.add(str(val))

            # Service calls
            elif isinstance(node.func.value, ast.Name):
                key = f"{node.func.value.id}.{node.func.attr}"
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

                    # Check if 'request' is passed to service
                    request_passed = any(
                        isinstance(arg, ast.Name) and arg.id == "request"
                        for arg in node.args
                    )
                    if request_passed and info.get("query_params"):
                        for qp in info["query_params"]:
                            self.query_params.add(qp)

        self.generic_visit(node)

    def visit_Return(self, node):
        if (
            node.value
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "Response"
        ):
            status = "200"
            for kw in node.value.keywords:
                if kw.arg == "status":
                    val = ast.dump(kw.value)
                    m = re.search(r"HTTP_(\d+)", val)
                    status = m.group(1) if m else "200"

            data_node = (
                node.value.args[0]
                if node.value.args
                else next(
                    (kw.value for kw in node.value.keywords if kw.arg == "data"), None
                )
            )

            found = None
            if data_node:
                if isinstance(data_node, ast.Name):
                    info = self._get_var(data_node.id)
                    if info:
                        found = info["class"]
                elif isinstance(data_node, ast.Attribute) and data_node.attr == "data":
                    # serializer.data or MySerializer().data
                    if isinstance(data_node.value, ast.Name):
                        info = self._get_var(data_node.value.id)
                        if info:
                            found = info["class"]
                    elif (
                        isinstance(data_node.value, ast.Call)
                        and isinstance(data_node.value.func, ast.Name)
                        and "Serializer" in data_node.value.func.id
                    ):
                        found = data_node.value.func.id

            if found:
                self.responses[status] = {"serializer": found, "source": "inferred"}
            elif not found:
                if status == "204":
                    self.responses[status] = {
                        "serializer": "NoContent",
                        "source": "status",
                    }
                elif data_node and isinstance(data_node, ast.Dict):
                    keys = [
                        k.value if isinstance(k, ast.Constant) else k.s
                        for k in data_node.keys
                        if k
                    ]
                    label = f"Object {{{', '.join(keys)}}}" if keys else "DynamicObject"
                    self.responses[status] = {"serializer": label, "source": "raw_dict"}

        self.generic_visit(node)


def analyze_method_logic(
    method_node, class_serializer="None", method_name="", service_map=None
):
    visitor = MethodBodyVisitor(class_serializer, method_name, service_map)
    visitor.visit(method_node)

    if not visitor.input_serializer and not visitor.serializer_used:
        if visitor.raw_input_fields:
            keys_str = ", ".join(sorted(visitor.raw_input_fields))
            visitor.input_serializer = f"RawBody {{{keys_str}}}"
            visitor.input_source = "direct_raw_keys"
        else:
            # Fallback check for any request.data use
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
        list(visitor.query_params),  # Return detected query params
    )


class ViewVisitor(ast.NodeVisitor):
    def __init__(self, service_map=None):
        self.views = {}
        self.service_map = service_map or {}

    def visit_ClassDef(self, node):
        if not any(
            (isinstance(b, ast.Name) and b.id in GENERIC_DEFAULTS)
            or (isinstance(b, ast.Name) and "APIView" in b.id)
            for b in node.bases
        ):
            self.generic_visit(node)
            return

        doc = ast.get_docstring(node) or "No description."
        class_serializer = None
        permissions = []

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        if target.id == "serializer_class" and isinstance(
                            item.value, ast.Name
                        ):
                            class_serializer = item.value.id
                        elif target.id == "permission_classes":
                            if isinstance(item.value, (ast.List, ast.Tuple)):
                                for elt in item.value.elts:
                                    if isinstance(elt, ast.Name):
                                        permissions.append(elt.id)
                                    elif isinstance(elt, ast.Attribute):
                                        permissions.append(elt.attr)

        if not class_serializer:  # Fallback to get_serializer_class
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
            if isinstance(item, ast.FunctionDef) and item.name in [
                "get",
                "post",
                "put",
                "delete",
                "patch",
            ]:
                (req_ser, req_src), response_map, query_params = analyze_method_logic(
                    item, class_serializer, item.name, self.service_map
                )
                verb = item.name.upper()

                if not req_ser:
                    if verb in ["POST", "PUT", "PATCH"] and class_serializer:
                        req_ser, req_src = class_serializer, "class_default"
                    else:
                        req_ser, req_src = "NoBody", "no_body"

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
                            "204": {"serializer": "NoContent", "source": "no_content"}
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

                res_ser_str = ", ".join(
                    [f"{c}: {m['serializer']}" for c, m in sorted(response_map.items())]
                )

                methods[verb] = {
                    "request": req_ser,
                    "response": res_ser_str,
                    "response_details": response_map,
                    "req_source": req_src,
                    "res_source": "composite",
                    "permissions": permissions,
                    "query_params": query_params,  # Store found query params
                }

        # Backfill
        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        for base in bases:
            if base in GENERIC_DEFAULTS:
                for method in GENERIC_DEFAULTS[base]["methods"]:
                    if method not in methods:
                        req_ser = "NoBody"
                        res_str = f"200: {class_serializer or 'Unknown'}"
                        if method == "DELETE":
                            res_str = "204: NoContent"
                        elif method == "POST":
                            res_str = f"201: {class_serializer or 'Unknown'}"
                        if method in ["POST", "PUT", "PATCH"]:
                            req_ser = class_serializer or "Unknown"

                        methods[method] = {
                            "request": req_ser,
                            "response": res_str,
                            "req_source": "generic_default",
                            "res_source": "generic_default",
                            "permissions": permissions,
                            "query_params": [],
                        }

        self.views[node.name] = {"doc": doc, "methods": methods}
        self.generic_visit(node)


class URLVisitor(ast.NodeVisitor):
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


def parse_schema_file(file_path):
    # (Simplified stub - in reality you import json/yaml)
    return [], {}


def scan_project(root_path: str, callback=None):
    root = Path(root_path)
    all_views = {}
    all_urls = []
    service_map = {}
    serializers_map = {}
    models_map = {}

    if callback:
        callback("Phase 0a: Scanning models...")
    for path in root.rglob("*.py"):
        if ".venv" in path.parts or "migrations" in path.parts:
            continue
        if "models" in path.name or "models" in str(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                    scanner = ModelScanner()
                    scanner.visit(tree)
                    models_map.update(scanner.models)
            except:
                continue

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

    if callback:
        callback("Phase 3: Mapping URLs...")
    for path in root.rglob("urls.py"):
        if ".venv" in path.parts or "migrations" in path.parts:
            continue
        try:
            if callback:
                callback(f"Mapping {path.parent.name}/urls.py...")
            with open(path, "r", encoding="utf-8") as f:
                """
                prefix = (
                    ""
                    if path.parent.name in ["config", "root"]
                    else f"{path.parent.name}/"
                )
                """
                prefix = ""
                tree = ast.parse(f.read())
                visitor = URLVisitor(current_prefix=prefix)
                visitor.visit(tree)
                all_urls.extend(visitor.patterns)
        except:
            continue

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
