"""One-off: write base/base.vsdx, an empty A3 page on a Visio-made package skeleton.
usage: python scripts/make_base.py <any Visio-made .vsdx>
Only the skeleton (styles, theme, windows, content types) is taken from that file; none of its drawing is kept."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vsdx_writer import Page, write_vsdx

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "base", "base.vsdx")
write_vsdx(Page(), out, sys.argv[1], title="Architecture base (empty A3 page)")
print("wrote", os.path.normpath(out))
