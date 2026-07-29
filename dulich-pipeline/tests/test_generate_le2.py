from pathlib import Path

import generate_le2


def test_le2_runtime_spec_is_outside_cleanup_output():
    root = Path(generate_le2.__file__).parent.resolve()
    output_root = (root / "output").resolve()
    spec_path = generate_le2.DEFAULT_SPEC_PATH.resolve()

    assert spec_path.is_file()
    assert output_root not in spec_path.parents
    assert generate_le2.DEFAULT_OUTPUT_DIR.resolve().is_relative_to(output_root)


def test_le2_missing_spec_returns_nonzero(tmp_path, capsys):
    missing = tmp_path / "missing.json"

    result = generate_le2.main(
        ["--spec", str(missing), "--out", str(tmp_path / "render")]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert "Spec không tồn tại" in captured.err
    assert not (tmp_path / "render").exists()
