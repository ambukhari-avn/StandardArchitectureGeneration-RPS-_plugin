"""Zip what ChatGPT's code tool needs to validate a spec and draw the .vsdx: scripts, data, base, the example diagram and the format reference.

    python chatgpt-plugin/make_package.py [out.zip]      (default: Downloads\\out\\arch_plugin.zip)

Upload the zip to the chat; the instructions tell the model to unzip it and run scripts/build_diagram.py.
Standard library only.
"""
import os
import sys
import zipfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
KEEP = ("scripts", "data", "base", "samples", os.path.join("docs", "diagram-format.md"))
SKIP = ("__pycache__", ".pyc", "dev_preview.py", "import_dataset.py", "xlsx_reader.py")                  # development aids, not needed to draw


def files():
    for top in KEEP:
        path = os.path.join(ROOT, top)
        walk = [(path, [], [os.path.basename(path)])] if os.path.isfile(path) else os.walk(path)
        for d, _, names in walk:
            for n in names:
                full = os.path.join(d if not os.path.isfile(path) else os.path.dirname(path), n)
                if not any(s in full for s in SKIP):
                    yield full, os.path.relpath(full, ROOT)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "Downloads", "out", "arch_plugin.zip")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for full, rel in files():
            z.write(full, "arch_plugin/" + rel.replace(os.sep, "/"))
    print("wrote %s (%d files, %.1f MB)" % (out, len(z.namelist()), os.path.getsize(out) / 1e6))
