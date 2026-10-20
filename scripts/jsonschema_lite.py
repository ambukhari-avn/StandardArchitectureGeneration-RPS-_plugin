"""A small JSON-Schema checker (standard library only) for the subset data/spec_schema.json uses:
type (one or a list), enum, required, properties, additionalProperties (false), items, minItems, minLength, minimum, pattern.

    errors = check(instance, schema)      -> list of "path: message" strings; empty means valid
"""
import re


def _type_ok(v, t):
    if t == "object":
        return isinstance(v, dict)
    if t == "array":
        return isinstance(v, list)
    if t == "string":
        return isinstance(v, str)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "null":
        return v is None
    raise ValueError("unsupported schema type %r" % t)


def check(value, schema, path="$"):
    errs = []
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(value, x) for x in types):
            return ["%s: expected %s, got %s" % (path, "/".join(types), type(value).__name__)]
    if "enum" in schema and value not in schema["enum"]:
        errs.append("%s: %r is not one of %s" % (path, value, schema["enum"]))
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errs.append("%s: must not be empty" % path)
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errs.append("%s: %r does not match %s" % (path, value, schema["pattern"]))
    if isinstance(value, (int, float)) and not isinstance(value, bool) and "minimum" in schema and value < schema["minimum"]:
        errs.append("%s: %r is below the minimum %s" % (path, value, schema["minimum"]))
    if isinstance(value, dict):
        for k in schema.get("required", []):
            if k not in value:
                errs.append("%s: missing required field %r" % (path, k))
        props = schema.get("properties", {})
        for k, v in value.items():
            if k in props:
                errs += check(v, props[k], "%s.%s" % (path, k))
            elif schema.get("additionalProperties", True) is False:
                errs.append("%s: unknown field %r (allowed: %s)" % (path, k, ", ".join(sorted(props))))
            elif isinstance(schema.get("additionalProperties"), dict):
                errs += check(v, schema["additionalProperties"], "%s.%s" % (path, k))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errs.append("%s: needs at least %d item(s)" % (path, schema["minItems"]))
        if "items" in schema:
            for i, v in enumerate(value):
                errs += check(v, schema["items"], "%s[%d]" % (path, i))
    return errs
