"""Image policy (decision D30): the only pictures in the repo are the ones listed for components in the dataset workbook
(data/icons, referenced by data/components.json) plus the Avanceon logo the user supplied for the footer.
The sample architectures are for learning structure and connections only; none of their images may be reused.
Run:  python -m unittest discover -s tests"""
import json
import os
import unittest

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".emf", ".gif", ".svg", ".wmf", ".tif", ".tiff", ".webp")
ALLOWED_OTHER = {os.path.join("base", "avanceon_logo.png")}        # supplied by the user for the footer


def repo_images():
    out = []
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in (".git", "__pycache__")]
        out += [os.path.relpath(os.path.join(d, f), ROOT) for f in files if f.lower().endswith(EXTS)]
    return sorted(out)


class ImagePolicyTests(unittest.TestCase):
    def test_only_dataset_pictures_and_the_footer_logo_exist(self):
        with open(os.path.join(ROOT, "data", "components.json"), encoding="utf-8") as fh:
            listed = {os.path.normpath(os.path.join("data", c["picture"])) for c in json.load(fh)["components"] if c["picture"]}
        stray = [p for p in repo_images() if p not in listed and p not in ALLOWED_OTHER]
        self.assertEqual(stray, [], "image(s) that are not from the dataset workbook and not the footer logo")

    def test_every_listed_picture_is_present(self):
        with open(os.path.join(ROOT, "data", "components.json"), encoding="utf-8") as fh:
            pics = {c["picture"] for c in json.load(fh)["components"] if c["picture"]}
        for p in pics:
            self.assertTrue(os.path.exists(os.path.join(ROOT, "data", p)), p)

    def test_the_base_visio_file_carries_no_pictures(self):
        import zipfile
        names = zipfile.ZipFile(os.path.join(ROOT, "base", "base.vsdx")).namelist()
        self.assertEqual([n for n in names if "/media/" in n or "/embeddings/" in n or n.endswith(".emf")], [])


if __name__ == "__main__":
    unittest.main()
