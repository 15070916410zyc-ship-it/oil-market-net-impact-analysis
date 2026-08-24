from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_models():
    path = Path(__file__).parents[1] / "api" / "models.py"
    spec = spec_from_file_location("web_api_models", path)
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_selected_scale_granger_gate_excludes_non_significant_factors():
    models = _load_models()
    rows = [
        {"id": "KEEP", "imf": "IMF2", "significant": True, "pValue": 0.021},
        {"id": "DROP_P", "imf": "IMF2", "significant": False, "pValue": 0.411},
        {"id": "DROP_SCALE", "imf": "IMF1", "significant": True, "pValue": 0.008},
    ]

    retained = models.retained_scale_rows(rows, "IMF2")

    assert [row["id"] for row in retained] == ["KEEP"]


def test_main_scale_selection_can_keep_one_or_two_imfs():
    models = _load_models()

    two = models.select_main_scale_indices([100.0, 72.0, 40.0], [], ratio=0.5)
    one = models.select_main_scale_indices([100.0, 49.0, 20.0], [], ratio=0.5)

    assert two == [0, 1]
    assert one == [0]


def test_main_scale_selection_prioritises_gprd_supported_imfs():
    models = _load_models()
    rows = [
        {"id": "GPRD", "imf": "IMF2", "significant": True},
        {"id": "GPRD", "imf": "IMF3", "significant": True},
    ]

    selected = models.select_main_scale_indices([200.0, 90.0, 80.0], rows, ratio=0.5)

    assert selected == [1, 2]
