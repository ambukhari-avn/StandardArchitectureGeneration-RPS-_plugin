"""Diagram spec: load, validate, and the decision the drawing step needs. Standard library only.

The language model writes a spec (see data/spec_schema.json and docs/spec-format.md) from the user's prompt and the user's answers
to its clarifying questions. Nothing is drawn from a spec that fails validate(). The point of the checks is that the model cannot
invent anything: every device quotes the user's words; every label is in that quote; a dataset component is named only when the
quote names it (title or order number, and brand when titles clash); every connection is within the Purdue rules and says whether
the user stated it or it is assumed.

    report = validate(spec)          # the spec carries the prompt; answers to questions are in spec["answers"]
    report.errors / report.warnings  # [{'code', 'where', 'message'}]
    report.notes                     # notes the diagram must carry (assumptions, boxes, provisional levels)
    render_mode(device, group, ...)  # 'picture' or 'box' for the drawing step
"""
import json
import os
import re

import footer
import jsonschema_lite
import quantity
from cables import CableError, Cables
from components import Components
from matching import Matcher, norm
from purdue import PurdueError, PurdueMap

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SCHEMA_PATH = os.path.join(ROOT, "data", "spec_schema.json")
RULES_PATH = os.path.join(ROOT, "data", "spec_rules.json")


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


def validate(spec, comps=None, purdue=None, cables=None, srules=None, matcher=None):
    rep = Report()
    comps, purdue, cables = comps or Components(), purdue or PurdueMap(), cables or Cables()
    matcher, srules = matcher or Matcher(comps), srules or load_json(RULES_PATH)

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

    said = norm(" ".join([spec["prompt"]] + list(spec.get("answers", {}).values())))     # everything the user has said
    levels = list(purdue.levels)
    idx = {l: i for i, l in enumerate(levels)}
    dmz = srules["dmz_level"]
    devices, boxes_no_component, layers_used, qty_notes = {}, [], set(), []

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
            rep.error("G003", gw, "a Level 3.5 (DMZ) group is only allowed when the user asked for a DMZ (options.dmz)")
        for d in g["devices"]:
            dw = "device %s" % d["id"]
            if d["id"] in devices:
                rep.error("D001", dw, "duplicate device id")
                continue
            quote = d["quote"]
            if norm(quote) not in said:
                rep.error("D017", dw, "quote %r does not appear in the prompt or the user's answers" % quote)
            try:
                plan = quantity.plan(d["qty"], d.get("quantity_mode") or opts["quantity_mode"], opts.get("max_instances", quantity.DEFAULT_MAX_INSTANCES))
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
                    status, cands = matcher.check(quote, comp["id"])
                    if status == "no":
                        rep.error("D018", dw, "component %r is not named by the quote (its title or an order number must appear in it); "
                                  "draw it as a box with the user's wording, or ask the user" % comp["id"])
                    elif status == "ambiguous":
                        rep.error("D019", dw, "the quote fits several dataset components (%s); ask the user which brand or part number is meant" % ", ".join(cands))
                    try:
                        lv = purdue.level_of(comp["layer"], g["level"] if g["level"] in purdue.levels else None)
                        if lv != g["level"] and g["level"] in purdue.levels:
                            rep.error("D010", dw, "%s is a %r component (level %s) but sits in group %s at level %s" % (comp["label"], comp["layer"], lv, g["id"], g["level"]))
                    except PurdueError as e:
                        rep.error("D010", dw, str(e))
            elif not d.get("label"):
                rep.error("D004", dw, "no dataset component and no label: give a component id, or a label that appears in the quote")
            else:
                boxes_no_component.append(d["label"])
                if norm(d["label"]) not in norm(quote):
                    rep.error("D005", dw, "label %r does not appear in the quote" % d["label"])
            # boxes required
            if (g["level"] == dmz or d.get("third_party")) and d.get("component"):
                rep.error("D014", dw, "DMZ and third-party items are drawn as boxes; remove component and use a label")
            # VM
            says_vm = bool(re.search(srules["vm_pattern"], quote, re.I))
            if d.get("vm"):
                if not says_vm:
                    rep.error("D011", dw, "marked as a VM, but the quote does not say it is one")
                for c in d["vm"]["contents"]:
                    if norm(c) not in said:
                        rep.error("D012", dw, "VM content %r is not in the prompt or the user's answers" % c)
            elif says_vm:
                rep.warn("D013", dw, "the quote says VM or virtual, but the device has no vm block")
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
            if not c.get("quote") or norm(c["quote"]) not in said:
                rep.error("C006", cw, "basis 'prompt' needs a quote that appears in the prompt or the user's answers")
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

    # ---- notes the diagram must carry ------------------------------------------------------------------------------------
    unconf = purdue.unconfirmed(layers_used)
    if boxes_no_component:
        rep.notes.append("Drawn as boxes with the user's wording (not in the component dataset): %s." % "; ".join(dict.fromkeys(boxes_no_component)))
    assumed = [c for c in spec.get("connections", []) if c["basis"] == "assumed"]
    if assumed:
        rep.notes.append("%d connection(s) are assumed: not stated by the user." % len(assumed))
    if unconf:
        rep.notes.append("Purdue level assigned provisionally for: %s." % ", ".join(l for l, _ in unconf))
    rep.notes += ["Quantity: " + n for n in qty_notes]
    rep.stats = {"groups": len(spec["groups"]), "devices": len(devices), "connections": len(spec.get("connections", []))}
    return rep
