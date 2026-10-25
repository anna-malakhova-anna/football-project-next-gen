"""The site build is split into layers (scripts/build_site.py docstring); a lower layer never imports a higher one, so there are no import cycles."""
import ast
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
LAYERS = ["site_p5_data", "site_data", "site_render", "site_rules", "site_charts", "site_phase5", "build_site"]
LOWER_ONLY = {   # module -> the site modules it may import
    "site_p5_data": set(),
    "site_data": {"site_p5_data"},
    "site_render": {"site_phase5", "site_p5_data", "site_cards"},
    "site_rules": {"site_p5_data", "site_data", "site_render"},
    "site_charts": {"site_phase5", "site_product", "site_render"},
    "site_phase5": {"site_p5_data"},
}


def _site_imports(module: str) -> set[str]:
    tree = ast.parse((SCRIPTS / f"{module}.py").read_text(encoding="utf-8"))
    found = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            if n.module == "scripts":
                found |= {a.name for a in n.names}
            elif n.module.startswith("scripts."):
                found.add(n.module.split(".", 1)[1])
    return {m for m in found if m.startswith("site_") or m == "build_site"}


def test_each_site_module_imports_only_from_the_layers_below_it():
    for module, allowed in LOWER_ONLY.items():
        extra = _site_imports(module) - allowed
        assert not extra, f"{module} imports {sorted(extra)}"


def test_the_page_assembly_module_is_on_top():
    assert LAYERS[-1] == "build_site"
    for module in LAYERS[:-1]:
        assert "build_site" not in _site_imports(module)
