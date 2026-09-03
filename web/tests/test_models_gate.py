from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import numpy as np


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


def test_all_default_economic_factor_groups_have_live_provider_mappings():
    models = _load_models()
    default_ids = {
        "GPRD", "FRED-USEPUINDXD", "FRED-CRUDEPROD", "FRED-CRUDESTOCKS",
        "FRED-REFINERYUTIL", "FRED-GASOLINE", "FRED-HENRYHUB", "FRED-COPPER",
        "FRED-DTWEXBGS", "FRED-DEXCHUS", "FRED-DGS10", "FRED-DFF",
        "FRED-T10YIE", "FRED-HYSPREAD", "FRED-STLFSI4", "FRED-VIXCLS",
        "FRED-OVXCLS", "FRED-SP500", "FRED-CPIAUCSL", "FRED-PPI",
        "FRED-INDPRO", "FRED-UNRATE", "FRED-RSAFS",
    }

    assert default_ids <= models.SERIES.keys()
    assert all(models.SERIES[series_id][0] for series_id in default_ids)


def test_f_survival_matches_reference_values_without_scipy_runtime():
    models = _load_models()

    assert abs(models.f_survival(1.0, 1, 10) - 0.34089313230206) < 1e-10
    assert abs(models.f_survival(3.5, 2, 100) - 0.03394775941762179) < 1e-10
    assert abs(models.f_survival(10.0, 5, 40) - 2.9195853033816384e-06) < 1e-12


def test_fft_analytic_signal_preserves_real_series_and_quadrature():
    models = _load_models()
    phase = np.linspace(0, 4 * np.pi, 256, endpoint=False)
    signal = np.cos(phase)
    analytic = models.analytic_signal(signal)

    assert np.allclose(analytic.real, signal, atol=1e-12)
    assert np.allclose(analytic.imag, np.sin(phase), atol=1e-10)


def test_multiple_break_scan_recovers_two_material_regime_changes():
    models = _load_models()
    values = np.r_[np.linspace(0, 1, 40), np.linspace(8, 9, 40), np.linspace(-4, -3, 40)]
    dates = [f"2026-{index + 1:03d}" for index in range(len(values))]

    result = models.multiple_break_test(values, dates, min_size=12, max_breaks=4)

    indices = result["breakIndices"]
    assert len(indices) >= 2
    assert any(abs(index - 40) <= 4 for index in indices)
    assert any(abs(index - 80) <= 4 for index in indices)
    assert result["method"] == "penalized binary segmentation"
