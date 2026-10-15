"""Native handler query planning over an explicitly supplied mirror snapshot.
No tenant state, storage, HTTP request facade or private service access.
"""
from .native_active_filters import active_filters_to_query_kwargs
from urllib.parse import parse_qsl

class QueryPairs:
    """Ordered URL query projection (first value + all repetitions), not a Request."""
    def __init__(self, query_string):
        self.pairs = parse_qsl(query_string, keep_blank_values=True)
    def get(self, key, default=None):
        return next((value for name, value in self.pairs if name == key), default)
    def getall(self, key, default=None):
        found = [value for name, value in self.pairs if name == key]
        return found if found else default
    def __contains__(self, key):
        return any(name == key for name, _ in self.pairs)

def plan_relative_paths(query, active_payload):
    search = query.get("search", "").strip()
    limit = min(int(query.get("limit", "15")), 100)
    offset = max(0, int(query.get("offset", "0")))

    folder = query.get("folder")
    recursive = query.get("recursive", "true").lower() == "true"
    base_models = list(query.getall("base_model", []))
    model_types = list(query.getall("model_type", []))

    tag_filters: Dict[str, str] = {}
    for tag in query.getall("tag_include", []):
        if tag:
            tag_filters[tag] = "include"
    for tag in query.getall("tag_exclude", []):
        if tag:
            tag_filters[tag] = "exclude"

    auto_tag_filters: Dict[str, str] = {}
    for tag in query.getall("auto_tag_include", []):
        if tag:
            auto_tag_filters[tag] = "include"
    for tag in query.getall("auto_tag_exclude", []):
        if tag:
            auto_tag_filters[tag] = "exclude"

    tag_logic = query.get("tag_logic", "any").lower()
    if tag_logic not in ("any", "all"):
        tag_logic = "any"

    credit_required = query.get("credit_required")
    if credit_required is not None:
        credit_required = credit_required.lower() not in ("false", "0", "")

    allow_selling_generated_content = query.get(
        "allow_selling_generated_content"
    )
    if allow_selling_generated_content is not None:
        allow_selling_generated_content = (
            allow_selling_generated_content.lower() not in ("false", "0", "")
        )

    # When requested, merge the manager page's active filters stored
    # server-side. Explicit query parameters take precedence over the
    # stored values.
    use_active_filters = (
        query.get("use_active_filters", "").lower() in ("1", "true")
    )
    if use_active_filters:
        stored = active_payload
        injected = active_filters_to_query_kwargs(stored)
        if folder is None and "folder" in injected:
            folder = injected["folder"]
        if "recursive" not in query and "recursive" in injected:
            recursive = injected["recursive"]
        if not base_models and injected.get("base_models"):
            base_models = injected["base_models"]
        if not model_types and injected.get("model_types"):
            model_types = injected["model_types"]
        if not tag_filters and injected.get("tags"):
            tag_filters = injected["tags"]
        if not auto_tag_filters and injected.get("auto_tags"):
            auto_tag_filters = injected["auto_tags"]
        if "tag_logic" not in query and injected.get("tag_logic"):
            injected_logic = str(injected["tag_logic"]).lower()
            if injected_logic in ("any", "all"):
                tag_logic = injected_logic
        if credit_required is None and "credit_required" in injected:
            credit_required = injected["credit_required"]
        if (
            allow_selling_generated_content is None
            and "allow_selling_generated_content" in injected
        ):
            allow_selling_generated_content = injected[
                "allow_selling_generated_content"
            ]

    # The presence of the recursive param (always sent by the loras
    # widget when filter mode is on) signals that the filter pipeline
    # must run even when no concrete filter is set, so global settings
    # like show_only_sfw stay consistent with the list endpoint.
    apply_filters = (
        use_active_filters
        or "recursive" in query
        or folder is not None
        or bool(base_models)
        or bool(model_types)
        or bool(tag_filters)
        or bool(auto_tag_filters)
        or credit_required is not None
        or allow_selling_generated_content is not None
    )
    return {'search': search, 'limit': limit, 'offset': offset, 'folder': folder,
        'recursive': recursive, 'base_models': base_models, 'model_types': model_types,
        'tags': tag_filters, 'auto_tags': auto_tag_filters, 'tag_logic': tag_logic,
        'credit_required': credit_required, 'allow_selling_generated_content': allow_selling_generated_content,
        'apply_filters': apply_filters}
