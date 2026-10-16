"""CLI smoke tests."""

from pathlib import Path

import main as cli


def test_cli_generates_svg(tmp_path: Path):
    src = tmp_path / "prog.cpp"
    src.write_text("int main() { return 0; }", encoding="utf-8")
    rc = cli.main([str(src)])
    assert rc == 0
    out = tmp_path / "prog.svg"
    assert out.exists()
    assert "<svg" in out.read_text(encoding="utf-8")


def test_cli_custom_output(tmp_path: Path):
    src = tmp_path / "prog.cpp"
    src.write_text("void f() { g(); }", encoding="utf-8")
    dst = tmp_path / "custom.svg"
    rc = cli.main([str(src), "-o", str(dst)])
    assert rc == 0 and dst.exists()


def test_cli_parse_error(tmp_path: Path):
    src = tmp_path / "bad.cpp"
    src.write_text("int main() { return ; ; ;; }", encoding="utf-8")
    # `return ;` is fine; use a real syntax error
    src.write_text("int main() { int x = ; }", encoding="utf-8")
    rc = cli.main([str(src)])
    assert rc == 2


def test_cli_missing_file(tmp_path: Path):
    rc = cli.main([str(tmp_path / "nope.cpp")])
    assert rc == 1


def test_cli_invalid_utf8(tmp_path: Path, capsys):
    src = tmp_path / "invalid.cpp"
    src.write_bytes(b"// \xff\nint main() { return 0; }")
    assert cli.main([str(src)]) == 1
    captured = capsys.readouterr()
    assert "не удалось прочитать файл" in captured.err
    assert not captured.out
    assert not src.with_suffix(".svg").exists()


def test_cli_output_error(tmp_path: Path, capsys):
    src = tmp_path / "prog.cpp"
    src.write_text("int main() { return 0; }", encoding="utf-8")
    dst = tmp_path / "missing" / "out.svg"
    assert cli.main([str(src), "-o", str(dst)]) == 1
    captured = capsys.readouterr()
    assert "не удалось сохранить файл" in captured.err
    assert not captured.out
    assert not dst.exists()
