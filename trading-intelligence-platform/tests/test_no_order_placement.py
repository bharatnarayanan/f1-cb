"""Codifies buildspec.json's structural acceptance criterion:

  "Given the entire codebase, when it is audited for order-placement code
  paths, then none exist — this is a structural acceptance criterion, not
  just a runtime configuration."

This scans actual source (not docs/comments that legitimately mention the
forbidden terms while explaining why they must never appear in code) for
calls/definitions that would constitute an order-placement path.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"

# Matches a call or a def, e.g. `kite.place_order(` or `def place_order(` —
# not a bare mention of the word in a comment/docstring sentence.
FORBIDDEN_PATTERNS = [
    re.compile(r"\bdef\s+place_order\b"),
    re.compile(r"\bdef\s+modify_order\b"),
    re.compile(r"\bdef\s+cancel_order\b"),
    re.compile(r"\bdef\s+exit_order\b"),
    re.compile(r"\bdef\s+place_gtt\b"),
    re.compile(r"\bdef\s+place_mf_order\b"),
    re.compile(r"\.place_order\s*\("),
    re.compile(r"\.modify_order\s*\("),
    re.compile(r"\.cancel_order\s*\("),
    re.compile(r"\.exit_order\s*\("),
    re.compile(r"\.place_gtt\s*\("),
    re.compile(r"\.place_mf_order\s*\("),
    # String-literal form only (an actual mode value) — bare mentions of the
    # word in prose/comments explaining that no such mode exists are fine
    # and expected (see docs/CLAUDE.md section 2).
    re.compile(r"""["']live_algo["']"""),
    re.compile(r"""["']auto_execute["']"""),
]


def _python_files() -> list[Path]:
    return [p for p in SRC_DIR.rglob("*.py") if "__pycache__" not in p.parts]


def test_no_order_placement_code_path_exists_in_src():
    violations = []
    for path in _python_files():
        text = path.read_text()
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                violations.append(f"{path.relative_to(REPO_ROOT)}: matched {pattern.pattern!r}")

    assert not violations, "Order-placement code path found:\n" + "\n".join(violations)


def test_src_tree_is_not_empty_so_this_audit_isnt_vacuous():
    # Guards against the test silently passing because SRC_DIR didn't exist
    # or globbing found nothing (e.g. a bad path after a future re-layout).
    assert len(_python_files()) >= 5
