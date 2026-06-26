from repomind.ingest import parse_repo, repo_slug


def test_parse_repo_parses_python_and_js_files(tmp_path):
    (tmp_path / "mod.py").write_text("def f(): pass")
    (tmp_path / "mod.js").write_text("function g() {}")
    (tmp_path / "notes.txt").write_text("not code")

    parsed = parse_repo(tmp_path)

    paths = {p.path for p in parsed}
    assert paths == {"mod.py", "mod.js"}


def test_parse_repo_skips_ignored_directories(tmp_path):
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("function f() {}")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.py").write_text("def f(): pass")
    (tmp_path / "real.py").write_text("def f(): pass")

    parsed = parse_repo(tmp_path)

    assert [p.path for p in parsed] == ["real.py"]


def test_parse_repo_skips_unparseable_file_without_failing_others(tmp_path):
    (tmp_path / "broken.py").write_text("def f(:::::")
    (tmp_path / "good.py").write_text("def f(): pass")

    parsed = parse_repo(tmp_path)

    assert [p.path for p in parsed] == ["good.py"]


def test_repo_slug_strips_git_suffix_and_trailing_slash():
    assert repo_slug("https://github.com/foo/bar.git") == "bar"
    assert repo_slug("https://github.com/foo/bar") == "bar"
    assert repo_slug("https://github.com/foo/bar/") == "bar"
