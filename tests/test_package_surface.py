import indexpilot


def test_public_package_surface_is_importable():
    assert indexpilot.__version__ == "0.2.0"
    assert callable(indexpilot.build_workload_dna_report)
