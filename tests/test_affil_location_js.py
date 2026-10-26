"""The browser parser (docs/js/affil-location.js) agrees with affil_location.py."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.pipeline.affil_location import parse_locations

ROOT = Path(__file__).resolve().parent.parent
CASES = [
    "Department of Surgery, Massachusetts General Hospital, Boston, MA 02114, USA.",
    "Brigham and Women's Hospital, Boston, Massachusetts; Harvard Medical School, Boston, MA, USA.",
    "Duke University, Durham NC 27710.",
    "University of Oregon, Eugene, OR, USA.",
    "Tbilisi State Medical University, Tbilisi, Georgia.",
    "Emory University, Atlanta, Georgia, USA.",
    "Department of Medicine, University of Hong Kong, Hong Kong, China.",
    "Peking University, Beijing 100871, China. Electronic address: someone@pku.edu.cn.",
    "Dartmouth-Hitchcock Medical Center, Lebanon, New Hampshire.",
    "Korea University (the Republic of Korea), Seoul.",
    "University of Toronto, Toronto, Ontario, Canada.",
    "Institut Pasteur, Paris, France; Universität Zürich, Zürich, Switzerland.",
    "1 Department of Physics, Stanford University, Stanford, Calif.",
    "Nowhere Institute, Some Street 5.",
    "constructor, toString, hasOwnProperty",
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_parser_matches_python():
    inp = "".join(json.dumps(c) + "\n" for c in CASES)
    out = subprocess.run(["node", str(ROOT / "tests" / "js" / "parse_affils.js")],
                         input=inp, capture_output=True, text=True, check=True)
    js = [json.loads(line) for line in out.stdout.splitlines()]
    py = [[[loc.country, loc.state] for loc in parse_locations(c)] for c in CASES]
    assert js == py
