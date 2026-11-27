from pathlib import Path

import pikepdf
import pytest

from offlinepdf.core import (
    InvalidRangeError,
    PasswordRequiredError,
    delete,
    extract,
    merge,
    reorder,
    rotate,
    split,
)
from offlinepdf.core.render import page_text


def texts(path: Path) -> list[str]:
    with pikepdf.open(path) as pdf:
        count = len(pdf.pages)
    return [page_text(path, i).strip() for i in range(count)]


def test_merge_keeps_order_and_adds_bookmarks(tmp_path, sample_pdf, second_pdf):
    out = merge([second_pdf, sample_pdf], tmp_path / "merged.pdf")
    content = texts(out)
    assert len(content) == 8
    assert content[0] == "Second 1" and content[3] == "Page 1"
    with pikepdf.open(out) as pdf, pdf.open_outline() as outline:
        titles = [item.title for item in outline.root]
        assert titles == ["second", "sample"]
        assert len(outline.root[1].children) == 5


def test_merge_without_bookmarks(tmp_path, sample_pdf, second_pdf):
    out = merge([sample_pdf, second_pdf], tmp_path / "m.pdf", bookmarks=False, keep_outlines=False)
    with pikepdf.open(out) as pdf, pdf.open_outline() as outline:
        assert len(outline.root) == 0


def test_merge_encrypted_input_with_password(tmp_path, encrypted_pdf, second_pdf):
    with pytest.raises(PasswordRequiredError):
        merge([encrypted_pdf, second_pdf], tmp_path / "x.pdf")
    out = merge([encrypted_pdf, second_pdf], tmp_path / "ok.pdf", passwords={str(encrypted_pdf): "secret"})
    assert len(texts(out)) == 8


def test_split_each(tmp_path, sample_pdf):
    outputs = split(sample_pdf, tmp_path / "parts")
    assert [p.name for p in outputs][:2] == ["sample_page001.pdf", "sample_page002.pdf"]
    assert len(outputs) == 5
    assert texts(outputs[4]) == ["Page 5"]


def test_split_every_and_ranges(tmp_path, sample_pdf):
    chunks = split(sample_pdf, tmp_path / "a", mode="every", every=2)
    assert [len(texts(p)) for p in chunks] == [2, 2, 1]
    groups = split(sample_pdf, tmp_path / "b", mode="ranges", ranges="1-2, 5, 3-")
    assert [texts(p) for p in groups] == [["Page 1", "Page 2"], ["Page 5"], ["Page 3", "Page 4", "Page 5"]]


def test_extract_in_typed_order(tmp_path, sample_pdf):
    out = extract(sample_pdf, tmp_path / "e.pdf", "4, 1-2")
    assert texts(out) == ["Page 4", "Page 1", "Page 2"]


def test_delete(tmp_path, sample_pdf):
    out = delete(sample_pdf, tmp_path / "d.pdf", "2, 4-5")
    assert texts(out) == ["Page 1", "Page 3"]


def test_delete_everything_is_rejected(tmp_path, sample_pdf):
    with pytest.raises(InvalidRangeError):
        delete(sample_pdf, tmp_path / "d.pdf", "1-5")


def test_reorder(tmp_path, sample_pdf):
    out = reorder(sample_pdf, tmp_path / "r.pdf", [4, 3, 2, 1, 0])
    assert texts(out) == ["Page 5", "Page 4", "Page 3", "Page 2", "Page 1"]
    with pytest.raises(InvalidRangeError):
        reorder(sample_pdf, tmp_path / "bad.pdf", [0, 9])


def test_rotate_selected_pages(tmp_path, sample_pdf):
    out = rotate(sample_pdf, tmp_path / "rot.pdf", 90, pages="1, 3")
    with pikepdf.open(out) as pdf:
        assert [page.rotation for page in pdf.pages] == [90, 0, 90, 0, 0]


def test_rotate_all_relative(tmp_path, rotated_pdf):
    out = rotate(rotated_pdf, tmp_path / "rot.pdf", 270)
    with pikepdf.open(out) as pdf:
        assert [page.rotation for page in pdf.pages] == [270, 0]
