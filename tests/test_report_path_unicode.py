from pathlib import Path

def unique_report_path(path: Path) -> Path:
    path = Path(path)
    if not path.exists():
        return path
    n = 1
    while True:
        c = path.with_name(f"{path.stem}_{n}{path.suffix}")
        if not c.exists():
            return c
        n += 1

def test_unicode_collision(tmp_path: Path):
    p = tmp_path / "báo_cáo.json"
    p.write_text("{}", encoding="utf-8")
    out = unique_report_path(p)
    assert out != p
