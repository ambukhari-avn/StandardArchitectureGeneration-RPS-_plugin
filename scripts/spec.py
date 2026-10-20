"""Diagram spec: load, validate, and the two decisions the drawing step needs. Standard library only.

The language model writes a spec (see data/spec_schema.json and docs/spec-format.md). Nothing is drawn from a spec that fails
validate(). The point of the checks is that the model cannot invent anything: every label traces to the dataset, the cited BOQ
rows or the user's prompt; every quantity equals the BOQ; every BOQ device line is drawn or explicitly omitted; every connection
is within the Purdue rules and says whether it was stated or assumed.

    report = validate(spec, boq_paths)   # boq_paths: {BOQ file name or path: path} or a list of paths
    report.errors / report.warnings      # [{'code', 'where', 'message'}]
    report.notes                         # notes the diagram must carry (assumptions, boxes, omissions, provisional levels)
    render_mode(device, group, ...)      # 'picture' or 'box' for the drawing step
"""
import json
import os
import re

import boq_parser
import boq_rules
import footer
import jsonschema_lite
import quantity
from cables import CableError, Cables
from components import Components
from matching import Matcher
from purdue import PurdueError, PurdueMap

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA_PATH = os.path.join(ROOT, "data", "spec_schema.json")
RULES_PATH = os.path.join(ROOT, "data", "spec_rules.json")


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()


def load_json(path):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


class Report:
    def __init__(self):
        self.errors, self.warnings, self.notes, self.stats = [], [], [], {}

    def error(self, code, where, message):
        self.errors.append({"code": code, "where": where, "message": message})

    def warn(self, code, where, message):
        self.warnings.append({"code": code, "where": where, "message": message})

    @property
    def ok(self):
        return not self.errors

    def text(self):
        out = ["%s: %d error(s), %d warning(s)" % ("VALID" if self.ok else "INVALID", len(self.errors), len(self.warnings))]
        out += ["  ERROR   %s [%s] %s" % (e["code"], e["where"], e["message"]) for e in self.errors]
        out += ["  warning %s [%s] %s" % (w["code"], w["where"], w["message"]) for w in self.warnings]
        if self.ok:
            out += ["  note for the diagram: " + n for n in self.notes]
        return "\n".join(out)


def _path_map(boq_paths):
    if not boq_paths:
        return {}
    items = boq_paths.items() if isinstance(boq_paths, dict) else [(p, p) for p in boq_paths]
    m = {}
    for k, v in items:
        m[os.path.basename(k)] = v
    return m


def render_mode(device, group, comps, purdue, srules):
    """'picture' or 'box'. A picture only for a dataset component that has one, outside the box levels (field devices, DMZ)
    and not third-party; everything else is a rectangle with text."""
    if not device.get("component") or device.get("third_party"):
        return "box"
    layer = comps.get(device["component"])["layer"]
    level = purdue.level_of(layer, group["level"])
    if level in srules["box_levels"] or group["level"] in srules["box_levels"]:
        return "box"
    return "picture" if comps.picture_path(device["component"]) else "box"


def validate(spec, boq_paths=None, comps=None, purdue=None, cables=None, rules=None, srules=None, matcher=None):
    rep = Report()
    comps, purdue, cables = comps or Components(), purdue or PurdueMap(), cables or Cables()
    matcher = matcher or Matcher(comps)
    rules, srules = rules or boq_rules.Rules(), srules or load_json(RULES_PATH)

    errs = jsonschema_lite.check(spec, load_json(SCHEMA_PATH))
    for e in errs:
        rep.error("S001", "structure", e)
    if errs:
        return rep                                      # later checks need the structure

    opts = spec["options"]
    try:
        footer._check_fields(spec["project"], opts.get("allow_tbc", False))
    except footer.FooterError as e:
        rep.error("P001", "project", str(e))

    # ---- BOQ sheets ------------------------------------------------------------------------------------------------
    sheets, paths = {}, _path_map(boq_paths)
    for src in spec["sources"]:
        p = paths.get(os.path.basename(src["file"]))
        if not p:
            rep.error("B000", "sources", "BOQ file %r was not supplied to the validator" % src["file"])
            continue
        for sh in src["sheets"]:
            if sh in sheets:
                rep.error("B000", "sources", "sheet name %r appears twice; rows could not be told apart" % sh)
                continue
            try:
                parsed = boq_parser.parse_sheet(p, sh)
            except (boq_parser.BoqError, KeyError) as e:
                rep.error("B001", "sources", "cannot read sheet %r of %s: %s" % (sh, src["file"], e))
                continue
            sheets[sh] = {"file": src["file"], "lines": {l["row"]: l for l in rules.classify_all(parsed["lines"])},
                          "zero": {l["row"] for l in parsed["zero_qty"]}}

    prompt_n = norm(spec.get("prompt", ""))
    levels = list(purdue.levels)
    idx = {l: i for i, l in enumerate(levels)}
    dmz = srules["dmz_level"]
    devices, cited, boxes_no_component, overrides, layers_used, qty_notes, by_default = {}, set(), [], [], set(), [], []

    # ---- groups and devices ------------------------------------------------------------------------------------------
    seen_groups = set()
    for g in spec["groups"]:
        gw = "group %s" % g["id"]
        if g["id"] in seen_groups:
            rep.error("G001", gw, "duplicate group id")
        seen_groups.add(g["id"])
        if g["level"] not in purdue.levels:
            rep.error("G002", gw, "level %r is not a Purdue level (use one of %s)" % (g["level"], ", ".join(levels)))
        if g["level"] == dmz and not opts["dmz"]:
            rep.error("G003", gw, "a Level 3.5 (DMZ) group is only allowed when the prompt asked for a DMZ (options.dmz)")
        for d in g["devices"]:
            dw = "device %s" % d["id"]
            if d["id"] in devices:
                rep.error("D001", dw, "duplicate device id")
                continue
            rows, comp = [], None
            # basis
            if d["basis"] == "boq":
                if not d.get("boq"):
                    rep.error("D015", dw, "basis 'boq' needs the BOQ rows it comes from (boq: [{sheet, row}])")
                if d.get("quote"):
                    rep.error("D016", dw, "basis 'boq' must not carry a prompt quote")
            else:
                if d.get("boq"):
                    rep.error("D016", dw, "basis 'prompt' must not cite BOQ rows")
                if not d.get("quote"):
                    rep.error("D017", dw, "basis 'prompt' needs quote: the words of the prompt that ask for it")
                elif norm(d["quote"]) not in prompt_n:
                    rep.error("D017", dw, "quote %r does not appear in the prompt" % d["quote"])
            # cited rows
            for ref in d.get("boq", []):
                info = sheets.get(ref["sheet"])
                if info is None:
                    rep.error("D007", dw, "sheet %r is not in sources" % ref["sheet"])
                elif ref["row"] in info["zero"]:
                    rep.error("D007", dw, "%s row %d has quantity 0" % (ref["sheet"], ref["row"]))
                elif ref["row"] not in info["lines"]:
                    rep.error("D007", dw, "%s row %d is not an item line of the BOQ" % (ref["sheet"], ref["row"]))
                else:
                    line = info["lines"][ref["row"]]
                    rows.append(line)
                    cited.add((ref["sheet"], ref["row"]))
                    if line["bucket"] != "device":
                        if d.get("boq_override"):
                            overrides.append("%s (row %d is classed as %s: %s)" % (d.get("label") or d.get("component"), ref["row"], line["bucket"], d["boq_override"]))
                        else:
                            rep.error("D008", dw, "%s row %d (%r) is classed as %s, not a device; add boq_override with a reason to draw it anyway" % (
                                ref["sheet"], ref["row"], line["description"][:40], line["bucket"]))
            part_rows = []
            for ref in d.get("parts", []):
                info = sheets.get(ref["sheet"])
                if info is None or ref["row"] not in info["lines"]:
                    rep.error("B002", dw, "part %s row %s is not an item line of the BOQ" % (ref["sheet"], ref["row"]))
                else:
                    part_rows.append(info["lines"][ref["row"]])
                    cited.add((ref["sheet"], ref["row"]))
            # quantity
            if rows and len(rows) == len(d.get("boq", [])) and abs(sum(l["qty"] for l in rows) - d["qty"]) > 1e-6:
                rep.error("D006", dw, "qty %g does not equal the cited BOQ rows (sum %g)" % (d["qty"], sum(l["qty"] for l in rows)))
            unit = d.get("unit") or (rows[0]["unit"] if rows else "")
            try:
                plan = quantity.plan(d["qty"], unit, d.get("quantity_mode") or opts["quantity_mode"], opts.get("max_instances", quantity.DEFAULT_MAX_INSTANCES))
                qty_notes += ["%s: %s" % (d["id"], n) for n in plan["notes"]]
            except quantity.QuantityError as e:
                rep.error("D009", dw, str(e))
            # component and label
            if d.get("component"):
                if d["component"] not in comps.by_id:
                    rep.error("D002", dw, "component %r is not in the dataset" % d["component"])
                else:
                    comp = comps.get(d["component"])
                    if d.get("label"):
                        rep.error("D003", dw, "a dataset component takes its label from the dataset; remove label")
                    layers_used.add(comp["layer"])
                    supported = set()                      # components the cited text matches by the exact rules (alias, part number, title, heading)
                    for l in rows + part_rows:
                        supported |= set(matcher.match(l["description"], l["model"], l["make"]).ids) | set(matcher.match_heading(l["section"]).ids)
                    if d.get("quote"):
                        supported |= set(matcher.match(d["quote"]).ids) | set(matcher.match_heading(d["quote"]).ids)
                    if comp["id"] not in supported:
                        rep.error("D018", dw, "component %r is not supported by an exact match of the cited text (alias, part number, title or heading); "
                                  "draw it as a box with the BOQ wording, or ask for the alias to be confirmed in data/aliases.json" % comp["id"])
                    try:
                        lv = purdue.level_of(comp["layer"], g["level"] if g["level"] in purdue.levels else None)
                        if lv != g["level"] and g["level"] in purdue.levels:
                            rep.error("D010", dw, "%s is a %r component (level %s) but sits in group %s at level %s" % (comp["label"], comp["layer"], lv, g["id"], g["level"]))
                    except PurdueError as e:
                        rep.error("D010", dw, str(e))
            elif not d.get("label"):
                rep.error("D004", dw, "no dataset component and no label: give a component id, or a label taken from the BOQ or the prompt")
            else:
                boxes_no_component.append(d["label"])
                if d["basis"] == "boq":
                    allowed = set()
                    for l in rows:
                        allowed |= {norm(l["section"]), norm(l["description"])}
                    if rows and norm(d["label"]) not in allowed:
                        rep.error("D005", dw, "label %r is not the section heading or description of the cited BOQ rows" % d["label"])
                elif norm(d["label"]) not in prompt_n:
                    rep.error("D005", dw, "label %r does not appear in the prompt" % d["label"])
            # boxes required
            if (g["level"] == dmz or d.get("third_party")) and d.get("component"):
                rep.error("D014", dw, "DMZ and third-party items are drawn as boxes; remove component and use a label")
            # VM
            texts = [l["description"] + " " + l["model"] for l in rows + part_rows] + ([d["quote"]] if d.get("quote") else [])
            vm_re = re.compile(srules["vm_pattern"], re.I)
            says_vm = any(vm_re.search(t) for t in texts)
            if d.get("vm"):
                if not says_vm:
                    rep.error("D011", dw, "marked as a VM, but neither the cited BOQ text nor the quote says it is one")
                for c in d["vm"]["contents"]:
                    if norm(c) not in prompt_n and not any(norm(c) in norm(t) for t in texts):
                        rep.error("D012", dw, "VM content %r is not in the prompt or the cited BOQ text" % c)
            elif says_vm:
                rep.warn("D013", dw, "the BOQ text says VM or virtual, but the device has no vm block")
            by_default += ["%s row %d" % (l["sheet"], l["row"]) for l in rows if l["by_default"]]
            role = d.get("role") or ("firewall" if d.get("component") in srules["firewall_components"] else None)
            devices[d["id"]] = {"d": d, "g": g, "level": g["level"], "role": role}

    # ---- connections -------------------------------------------------------------------------------------------------
    pairs = set()
    for i, c in enumerate(spec.get("connections", [])):
        cw = "connection %d (%s - %s)" % (i + 1, c["from"], c["to"])
        a, b = devices.get(c["from"]), devices.get(c["to"])
        for end, dev in (("from", a), ("to", b)):
            if dev is None:
                rep.error("C001", cw, "%s is not a device id in the spec" % c[end])
        if c["from"] == c["to"]:
            rep.error("C007", cw, "a device cannot connect to itself")
        try:
            cables.get(c["cable"])
        except CableError as e:
            rep.error("C002", cw, str(e))
        if c["basis"] == "prompt":
            if not c.get("quote") or norm(c["quote"]) not in prompt_n:
                rep.error("C006", cw, "basis 'prompt' needs a quote that appears in the prompt")
        elif c.get("quote"):
            rep.error("C006", cw, "an assumed connection must not carry a quote")
        if a is None or b is None or a["level"] not in idx or b["level"] not in idx:
            continue
        la, lb = a["level"], b["level"]
        if srules["adjacent_levels_only"] and abs(idx[la] - idx[lb]) > 1:
            rep.error("C003", cw, "levels %s and %s are not adjacent; traffic must pass the levels between them" % (la, lb))
        for r in srules["connection_rules"]:
            if "between_levels" in r and {la, lb} == set(r["between_levels"]) and c["cable"] != r["cable"]:
                (rep.error if r["severity"] == "error" else rep.warn)("C004", cw, "%s: levels %s-%s must use %r (%s)" % (r["id"], la, lb, r["cable"], r["source"]))
            if "min_level_forbidden" in r and c["cable"] == r["cable"] and min(idx[la], idx[lb]) >= idx[r["min_level_forbidden"]]:
                (rep.error if r["severity"] == "error" else rep.warn)("C009", cw, "%s: %s" % (r["id"], r["source"]))
        if srules["dmz_requires_firewall"] and la != lb and dmz in (la, lb) and "firewall" not in (a["role"], b["role"]):
            rep.error("C005", cw, "traffic into or out of the DMZ must pass a firewall; one end must be a firewall device")
        key = (frozenset((c["from"], c["to"])), c["cable"])
        if key in pairs:
            rep.warn("C008", cw, "duplicate connection")
        pairs.add(key)
    for r in spec.get("rings", []):
        rw = "ring %s" % r["id"]
        for m in r["members"]:
            if m not in devices:
                rep.error("R001", rw, "member %r is not a device id in the spec" % m)
        try:
            cables.get(r["cable"])
        except CableError as e:
            rep.error("R001", rw, str(e))

    # ---- nothing silently dropped --------------------------------------------------------------------------------------
    omitted = set()
    for o in spec.get("omitted", []):
        key = (o["sheet"], o["row"])
        info = sheets.get(o["sheet"])
        if info is None or o["row"] not in info["lines"]:
            rep.error("B002", "omitted", "%s row %s is not an item line of the BOQ" % key)
        elif key in cited:
            rep.error("B003", "omitted", "%s row %d is both drawn and omitted" % key)
        omitted.add(key)
    unaccounted = []
    for sh, info in sheets.items():
        for row, l in info["lines"].items():
            if l["bucket"] == "device" and (sh, row) not in cited and (sh, row) not in omitted:
                unaccounted.append("%s row %d: %s (qty %g)" % (sh, row, l["description"][:45], l["qty"]))
    if unaccounted:
        rep.error("B001", "boq", "%d BOQ device line(s) are neither drawn nor omitted: %s%s" % (
            len(unaccounted), "; ".join(unaccounted[:12]), " ..." if len(unaccounted) > 12 else ""))

    if by_default:
        rep.warn("B004", "boq", "%d cited BOQ row(s) were classed as devices by default (no classification rule matched), so check they are devices: %s%s" % (
            len(by_default), ", ".join(by_default[:10]), " ..." if len(by_default) > 10 else ""))

    # ---- notes the diagram must carry ------------------------------------------------------------------------------------
    unconf = purdue.unconfirmed(layers_used)
    if boxes_no_component:
        rep.notes.append("Drawn as boxes with the BOQ or prompt wording (not in the component dataset): %s." % "; ".join(dict.fromkeys(boxes_no_component)))
    assumed = [c for c in spec.get("connections", []) if c["basis"] == "assumed"]
    if assumed:
        rep.notes.append("%d connection(s) are assumed: not stated in the BOQ or the prompt." % len(assumed))
    if unconf:
        rep.notes.append("Purdue level assigned provisionally for: %s." % ", ".join(l for l, _ in unconf))
    if omitted:
        by_reason = {}
        for o in spec["omitted"]:
            by_reason.setdefault(o["reason"], 0)
            by_reason[o["reason"]] += 1
        rep.notes.append("BOQ device lines not drawn: " + "; ".join("%s (%d)" % kv for kv in by_reason.items()) + ".")
    rep.notes += ["Quantity: " + n for n in qty_notes]
    rep.notes += ["Drawn although classed otherwise: " + o for o in overrides]
    rep.stats = {"groups": len(spec["groups"]), "devices": len(devices), "connections": len(spec.get("connections", [])),
                 "boq_device_lines": sum(1 for i in sheets.values() for l in i["lines"].values() if l["bucket"] == "device"),
                 "drawn_rows": len(cited), "omitted_rows": len(omitted)}
    return rep
