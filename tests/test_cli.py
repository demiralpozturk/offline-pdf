import json

import pikepdf

from offlinepdf.cli import main
from offlinepdf.core import is_encrypted, page_count, read_metadata
from offlinepdf.core.render import page_text


def test_merge_and_info_json(tmp_path, sample_pdf, second_pdf, capsys):
    out = tmp_path / "m.pdf"
    assert main(["merge", str(sample_pdf), str(second_pdf), "-o", str(out)]) == 0
    assert page_count(out) == 8
    capsys.readouterr()
    assert main(["info", str(out), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["pages"] == 8


def test_wildcards_are_expanded(tmp_path, jpeg_file, png_file):
    out = tmp_path / "imgs.pdf"
    assert main(["images2pdf", str(tmp_path / "*.*g"), "-o", str(out), "--page-size", "a4"]) == 0
    assert page_count(out) == 2


def test_split_ranges_default_folder(tmp_path, sample_pdf, capsys):
    assert main(["split", str(sample_pdf), "--ranges", "1-2, 3-"]) == 0
    folder = sample_pdf.parent / "sample_split"
    assert sorted(p.name for p in folder.iterdir()) == ["sample_pages1-2.pdf", "sample_pages3-5.pdf"]


def test_reorder_reverse(tmp_path, sample_pdf):
    out = tmp_path / "r.pdf"
    assert main(["reorder", str(sample_pdf), "--order", "end-1", "-o", str(out)]) == 0
    assert page_text(out, 0).strip() == "Page 5"


def test_protect_unlock_round_trip(tmp_path, sample_pdf):
    locked = tmp_path / "l.pdf"
    assert main(["protect", str(sample_pdf), "--new-password", "x1", "-o", str(locked)]) == 0
    assert is_encrypted(locked)
    assert main(["compress", str(locked), "-o", str(tmp_path / "c.pdf")]) == 1
    opened = tmp_path / "u.pdf"
    assert main(["unlock", str(locked), "--password", "x1", "-o", str(opened)]) == 0
    assert not is_encrypted(opened)


def test_metadata_and_watermark(tmp_path, sample_pdf):
    edited = tmp_path / "e.pdf"
    assert main(["metadata", str(sample_pdf), "--title", "CLI Başlık", "-o", str(edited)]) == 0
    meta = read_metadata(edited)
    assert meta["title"] == "CLI Başlık" and meta["author"] == "Test Author"
    marked = tmp_path / "w.pdf"
    assert main(["watermark", str(edited), "--text", "TASLAK", "--tiled", "-o", str(marked)]) == 0
    assert "TASLAK" in page_text(marked, 0)
    with pikepdf.open(marked) as pdf:
        assert len(pdf.pages) == 5
