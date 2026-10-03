from pathlib import Path

from paper_preflight.bib.parse import parse_bib_file, parse_bib_text, resolve_value

BIB = r"""@string{nips = "Advances in Neural Information Processing Systems"}
% preflight: ignore[REF090, ref003] reason="internal report"
@inproceedings{vaswani2017,
  title     = {Attention Is All You Need},
  author    = {Vaswani, Ashish and Shazeer, Noam and others},
  booktitle = nips # " 30",
  month     = dec,
  year      = 2017,
  title     = {Second title is ignored},
}

@article{tacl,
  title  = "{BERT}: {P}re-training of {D}eep {B}idirectional {T}ransformers",
  author = {M{\"u}ller, J{\"o}rg and {van der Berg}, Jan},
  doi    = {10.1162/tacl\_a\_00276},
  url    = {https://example.org/a\%20b},
}

@misc{tacl, title = {Duplicate key, ignored}}

@article{broken,
  title = {Unbalanced {braces},
  year = {2020}
}

@book{zhou2016,
  title     = {机器学习},
  author    = {周志华},
  publisher = {清华大学出版社},
  year      = {2016},
}
"""


def test_entries_values_and_lines() -> None:
    result = parse_bib_text(BIB, Path("refs.bib"))
    assert [e.key for e in result.entries] == ["vaswani2017", "tacl", "zhou2016"]
    vaswani, tacl, zhou = result.entries
    assert vaswani.line == 3
    assert vaswani.entry_type == "inproceedings"
    assert vaswani.text("title") == "Attention Is All You Need"
    assert vaswani.fields["title"].line == 4
    assert vaswani.text("booktitle") == "Advances in Neural Information Processing Systems 30"
    assert vaswani.text("month") == "December"
    assert vaswani.text("year") == "2017"
    assert vaswani.duplicate_fields == ("title",)
    assert tacl.text("title") == "BERT: Pre-training of Deep Bidirectional Transformers"
    assert tacl.text("author") == "Müller, Jörg and van der Berg, Jan"
    assert tacl.text("doi") == "10.1162/tacl_a_00276"
    assert tacl.fields["doi"].raw == r"{10.1162/tacl\_a\_00276}"
    assert tacl.text("url") == "https://example.org/a%20b"
    assert zhou.text("title") == "机器学习"


def test_issues_are_reported_with_lines() -> None:
    result = parse_bib_text(BIB, Path("refs.bib"))
    issues = [(i.kind, i.line, i.key) for i in result.issues]
    assert ("duplicate_field", 3, "vaswani2017") in issues
    assert ("duplicate_key", 19, "tacl") in issues
    assert any(kind == "syntax_error" and line == 21 for kind, line, _ in issues)


def test_suppression_comments_attach_to_following_entry() -> None:
    result = parse_bib_text(BIB, Path("refs.bib"))
    vaswani = result.entries[0]
    suppression = vaswani.suppressed("REF003")
    assert suppression is not None
    assert suppression.reason == "internal report"
    assert suppression.line == 2
    assert vaswani.suppressed("CIT003") is None
    assert result.entries[1].suppressions == ()


def test_resolve_value_concatenation_and_undefined_macro() -> None:
    assert resolve_value('{A} # " and " # b', {"b": "B"}) == "A and B"
    assert resolve_value("undefinedmacro", {}) == "undefinedmacro"
    assert resolve_value('"x # y"', {}) == "x # y"


def test_crlf_bom_and_gb18030_files(tmp_path: Path) -> None:
    text = "@book{zhou2016,\r\n  title = {机器学习},\r\n  year = {2016}\r\n}\r\n"
    utf8_bom = tmp_path / "bom.bib"
    utf8_bom.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    gbk = tmp_path / "gbk.bib"
    gbk.write_bytes(text.encode("gb18030"))
    for path, encoding in ((utf8_bom, "utf-8"), (gbk, "gb18030")):
        result = parse_bib_file(path)
        assert result.encoding == encoding
        (entry,) = result.entries
        assert entry.text("title") == "机器学习"
        assert entry.fields["year"].line == 3


def test_unreadable_file(tmp_path: Path) -> None:
    result = parse_bib_file(tmp_path / "missing.bib")
    assert [i.kind for i in result.issues] == ["unreadable"]
