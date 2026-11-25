"""База знаний: файлы превращаются в страницы, ненадёжное названо, глава собирается из загруженной книги."""

import json
import zipfile

import pytest
from glava.modules.drawing.scenes import (
    load_style,
    load_templates,
    render,
    scene_issues,
)
from glava.modules.layer.builder import mark_unsure_claims
from glava.modules.library.extract import (
    docx_pages,
    extract_pages,
    image_pages,
    pdf_pages,
    text_pages,
    to_md,
)
from glava.modules.library.pdf import joined
from glava.modules.library.preview import make_previews, preview_file
from glava.modules.library.registry import (
    LibraryError,
    library_chapter,
    load_source,
    unsure_pages,
)
from glava.modules.library.vision import page_issues, read_page
from glava.modules.llm.client import Reply
from glava.modules.source_text.units import parse_units, read_pages
from glava.pipeline.chapter import Chapter, context_of, load_chapter
from glava.pipeline.steps.extract import build_extract
from glava.pipeline.steps.routing import routing_context
from glava.shared import paths

PARAGRAPH = "Пористость породы показывает долю пустот в её объёме, а проницаемость показывает способность пропускать жидкость."
W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'


def pdf(path, *pages):
    import pymupdf

    document = pymupdf.open()
    for lines in pages:
        page = document.new_page()
        for i, (text, size) in enumerate(lines):
            page.insert_htmlbox((50, 50 + i * 90, 550, 130 + i * 90), f'<p style="font-size:{size}px">{text}</p>')
    document.save(path)
    return path


def scanned(path):
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    pixels = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50))
    pixels.clear_with(200)
    page.insert_image(page.rect, pixmap=pixels)
    document.save(path)
    return path


def docx(path, body, head=""):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", f"{head}<w:document {W_NS}><w:body>{body}</w:body></w:document>")
    return path


def p(text, style="", extra=""):
    look = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{look}{extra}<w:r><w:t>{text}</w:t></w:r></w:p>"


# ---------- текст и md
def test_md_with_page_marks_keeps_its_numbers(tmp_path):
    file = tmp_path / "a.md"
    file.write_text(f"<!-- page 90 -->\n\n{PARAGRAPH}\n\n<!-- page 91 -->\n\nВторая страница.", encoding="utf-8")
    assert [(x.page, x.state) for x in text_pages(file)] == [(90, "text"), (91, "text")]


@pytest.mark.parametrize("text", ["Потеряюсь.\n<!-- page 1 -->\nа", "<!-- page 1 -->\nа\n<!-- page 1 -->\nб", "<!-- page 2 -->\nа\n<!-- page 1 -->\nб", "<!-- page 0 -->\nа"])
def test_md_that_would_lose_text_is_refused(tmp_path, text):
    file = tmp_path / "a.md"
    file.write_text(text, encoding="utf-8")
    with pytest.raises(LibraryError):
        text_pages(file)


def test_long_text_is_split_by_paragraphs_without_losses(tmp_path):
    file = tmp_path / "a.txt"
    blocks = [f"Абзац {i}. {PARAGRAPH}" for i in range(120)]
    file.write_text("\n\n".join(blocks), encoding="utf-8")
    pages = text_pages(file)
    assert len(pages) > 3
    assert [b for x in pages for b in x.text.split("\n\n")] == blocks


def test_foreign_page_mark_does_not_move_pages(tmp_path):
    file = tmp_path / "a.txt"
    file.write_text(f"{PARAGRAPH} <!-- page 77 --> хвост", encoding="utf-8")
    pages = read_pages(to_md(text_pages(file)), [(1, 100)])
    assert list(pages) == [1] and "хвост" in pages[1]


def test_mixed_alphabets_are_doubtful(tmp_path):
    file = tmp_path / "a.txt"
    file.write_text("Пopистoсть пopoды пoкaзывaeт дoлю " * 10, encoding="utf-8")
    assert text_pages(file)[0].state == "doubtful"


def test_nested_page_mark_is_removed_completely(tmp_path):
    file = tmp_path / "a.txt"
    file.write_text(f"{PARAGRAPH} <!-- page <!-- page 1 -->7 --> конец", encoding="utf-8")
    pages = read_pages(to_md(text_pages(file)), [(1, 100)])
    assert list(pages) == [1] and "конец" in pages[1]


def test_paragraph_glued_to_a_heading_stays_a_paragraph(tmp_path):
    file = tmp_path / "a.md"
    file.write_text(f"# Заголовок\n{PARAGRAPH}", encoding="utf-8")
    units = parse_units(read_pages(to_md(text_pages(file)), [(1, 9)]))
    assert [u.kind for u in units] == ["heading", "paragraph"]


@pytest.mark.parametrize("encoding", ["cp1251", "cp866", "koi8-r", "mac_cyrillic"])
def test_old_encodings_are_guessed_and_doubted(tmp_path, encoding):
    file = tmp_path / "a.txt"
    file.write_bytes(PARAGRAPH.encode(encoding))
    page = text_pages(file)[0]
    assert page.text == PARAGRAPH and page.state == "doubtful"


def test_one_bad_byte_does_not_spoil_the_file(tmp_path):
    file = tmp_path / "a.txt"
    file.write_bytes((PARAGRAPH * 5).encode() + b"\xff" + PARAGRAPH.encode())
    page = text_pages(file)[0]
    assert PARAGRAPH in page.text and page.state == "doubtful"


# ---------- PDF
def test_pdf_text_and_headings(tmp_path):
    page = pdf_pages(pdf(tmp_path / "a.pdf", [("Глава первая", 22), (PARAGRAPH, 11)]))[0]
    assert page.state == "text"
    assert page.text.startswith("## Глава первая") and PARAGRAPH in page.text.replace("\n", " ")


@pytest.mark.parametrize(("html", "expected"), [("10<sup>6</sup> Па", "10⁶ Па"), ("10<sup>-15</sup> м", "10⁻¹⁵ м"), ("5<sup>3</sup>", "5³"), ("x<sub>2</sub> y", "x₂ y")])
def test_powers_and_indices_are_not_flattened(tmp_path, html, expected):
    page = pdf_pages(pdf(tmp_path / "a.pdf", [(f"Величина равна {html} при обычных условиях. " + PARAGRAPH, 12)]))[0]
    assert expected in page.text


def test_hyphens_follow_the_book():
    known = {"газо-водяной", "пористость", "state-of-the-art"}
    assert joined(["пори-", "стость"], known) == "пористость"
    assert joined(["газо-", "водяной"], known) == "газо-водяной"
    assert joined(["по\u00ad", "ристый"], known) == "пористый"
    assert joined(["state-of-the-", "art"], known) == "state-of-the-art"


def test_minus_given_as_a_soft_hyphen_is_kept():
    assert joined(["от \u00ad15 до \u00ad3, слой 3\u00ad4 м, газо\u00adводяной"], set()) == "от -15 до -3, слой 3-4 м, газо-водяной"
    assert joined(["при\u2010", "чём"], set()) == "причём"


def test_ordinary_book_page_is_not_doubted(tmp_path):
    """Колонтитул нарисован первым, номер страницы последним, есть номер формулы справа, подпись и сноска."""
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_htmlbox((50, 800, 550, 830), "<p>12</p>")
    page.insert_htmlbox((50, 20, 300, 45), "<p>Глава 3. Коллекторы</p>")
    page.insert_htmlbox((400, 20, 550, 45), "<p>Иванов, 2024</p>")
    for i in range(5):
        page.insert_htmlbox((50, 80 + i * 70, 550, 145 + i * 70), f"<p><b>Слово</b> {PARAGRAPH}</p>")
    page.insert_htmlbox((50, 440, 300, 460), "<p>m = V / W</p>")
    page.insert_htmlbox((500, 440, 550, 460), "<p>(12)</p>")
    page.insert_htmlbox((50, 480, 550, 560), "<ul><li>первый признак</li><li>второй признак</li></ul>")
    page.insert_htmlbox((50, 740, 550, 780), '<p style="font-size:8px">Примечание автора к абзацу выше, набранное мелко.</p>')
    document.save(tmp_path / "a.pdf")
    found = pdf_pages(tmp_path / "a.pdf")[0]
    assert (found.state, found.reasons) == ("text", ())


def drawn(path, *items):
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    for box, text in items:
        page.insert_htmlbox(box, f"<p>{text}</p>")
    document.save(path)
    return pdf_pages(path)[0]


def test_borderless_table_is_doubtful(tmp_path):
    rows = [((x, 300 + i * 30, x + 100, 325 + i * 30), t) for i in range(4) for x, t in ((50, f"Порода {i}"), (300, f"{70 + i}"))]
    assert drawn(tmp_path / "a.pdf", ((50, 50, 550, 200), PARAGRAPH), *rows).state == "doubtful"


def test_footnote_drawn_before_the_body_is_doubtful(tmp_path):
    note = "Примечание: порог действителен только для чистых песчаников, а для глинистых пород он ниже указанного в тексте."
    assert drawn(tmp_path / "a.pdf", ((50, 770, 550, 820), note), ((50, 50, 550, 200), PARAGRAPH)).state == "doubtful"


def test_rotated_text_among_plain_is_doubtful(tmp_path):
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_htmlbox((50, 50, 550, 200), f"<p>{PARAGRAPH}</p>")
    page.insert_text((300, 500), "Depth from the surface", rotate=90)
    document.save(tmp_path / "a.pdf")
    assert pdf_pages(tmp_path / "a.pdf")[0].state == "doubtful"


def test_guessed_joins_are_named_without_doubting_the_page():
    guesses = []
    assert joined(["gas-", "water and пори-", "стость"], {"пористость"}, guesses) == "gaswater and пористость"
    assert guesses == ["gaswater"]
    assert joined(["газо\u00ad", "водяной"], {"газо-водяной"}) == "газо-водяной"


def test_invisible_layer_over_strips_of_a_scan_is_doubtful(tmp_path):
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    pixels = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50))
    pixels.clear_with(200)
    for i in range(6):
        page.insert_image(pymupdf.Rect(60, 60 + i * 110, 540, 170 + i * 110), pixmap=pixels)
    page.insert_text((70, 100), "Recognised text layer that nobody can see on the page at all", render_mode=3)
    document.save(tmp_path / "a.pdf")
    assert pdf_pages(tmp_path / "a.pdf")[0].state == "doubtful"


def test_two_columns_are_doubtful(tmp_path):
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    for box in ((40, 50, 280, 300), (320, 50, 560, 300)):
        page.insert_htmlbox(box, f"<p>{PARAGRAPH}</p>" * 2)
    document.save(tmp_path / "a.pdf")
    found = pdf_pages(tmp_path / "a.pdf")[0]
    assert found.state == "doubtful" and any("колон" in r or "вниз" in r for r in found.reasons)


def test_short_text_is_not_lost(tmp_path):
    page = pdf_pages(pdf(tmp_path / "a.pdf", [("Порог 12 %.", 12)]))[0]
    assert "Порог 12" in page.text and page.state == "text"


def test_scanned_pdf_asks_for_a_reader(tmp_path):
    page = pdf_pages(scanned(tmp_path / "a.pdf"))[0]
    assert page.state == "scan" and page.reasons


def test_blank_page_is_empty_and_numbers_stay(tmp_path):
    pages = pdf_pages(pdf(tmp_path / "a.pdf", [(PARAGRAPH, 11)], [], [(PARAGRAPH, 11)]))
    assert [(x.page, x.state) for x in pages] == [(1, "text"), (2, "empty"), (3, "text")]
    assert sorted(read_pages(to_md(pages), [(1, 3)])) == [1, 2, 3]


@pytest.mark.parametrize("raw", [b"", b"not a pdf", b"%PDF-1.4 broken"])
def test_broken_pdf_is_named(tmp_path, raw):
    (tmp_path / "a.pdf").write_bytes(raw)
    with pytest.raises(LibraryError):
        extract_pages(tmp_path / "a.pdf", "pdf", tmp_path / "scan.pdf")


def test_image_becomes_a_scan_page(tmp_path):
    import pymupdf

    pixels = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50))
    pixels.clear_with(200)
    pixels.save(tmp_path / "a.png")
    assert image_pages(tmp_path / "a.png", tmp_path / "scan.pdf")[0].state == "scan"
    assert (tmp_path / "scan.pdf").read_bytes().startswith(b"%PDF")


# ---------- DOCX
def test_docx_headings_tables_and_pages(tmp_path):
    table = "<w:tbl><w:tr><w:tc>" + p("а") + "</w:tc><w:tc>" + p("б|в") + "</w:tc></w:tr><w:tr><w:tc>" + p("1") + "</w:tc></w:tr></w:tbl>"
    body = p("Глава", "Heading1") + p(PARAGRAPH) + table + p("Вторая", extra='<w:r><w:br w:type="page"/></w:r>')
    first, second = docx_pages(docx(tmp_path / "a.docx", body))
    assert first.text.startswith("# Глава") and "| а | б/в |" in first.text and "| 1 | |" in first.text
    assert second.page == 2 and second.text == "Вторая"


def run(inner, look=""):
    return f"<w:r>{f'<w:rPr>{look}</w:rPr>' if look else ''}{inner}</w:r>"


@pytest.mark.parametrize(("body", "expected"), [
    ("<w:p>" + run("<w:t>10</w:t>") + run("<w:t>6</w:t>", '<w:vertAlign w:val="superscript"/>') + "</w:p>", "10⁶"),
    ("<w:sdt><w:sdtContent>" + p("из поля") + "</w:sdtContent></w:sdt>", "из поля"),
    ("<w:customXml>" + p("из разметки") + "</w:customXml>", "из разметки"),
    ("<w:p><w:ins>" + run("<w:t>вставка</w:t>") + "</w:ins><w:del>" + run("<w:delText>удалено</w:delText>") + "</w:del></w:p>", "вставка"),
    ("<w:p>" + run("<w:t>газо</w:t><w:noBreakHyphen/><w:t>водяной</w:t>") + "</w:p>", "газо-водяной"),
])
def test_docx_keeps_what_word_shows(tmp_path, body, expected):
    page = docx_pages(docx(tmp_path / "a.docx", body + p(PARAGRAPH)))[0]
    assert expected in page.text and "удалено" not in page.text


def test_docx_text_box_is_not_doubled(tmp_path):
    ns = 'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'
    box = "<w:txbxContent>" + p("Врезка 15 м") + "</w:txbxContent>"
    body = f"<w:p><w:r><mc:AlternateContent {ns}><mc:Choice>{box}</mc:Choice><mc:Fallback>{box}</mc:Fallback></mc:AlternateContent></w:r></w:p>"
    page = docx_pages(docx(tmp_path / "a.docx", body + p(PARAGRAPH)))[0]
    assert page.text.count("Врезка 15 м") == 1 and page.state == "doubtful"


def test_docx_footnotes_are_read(tmp_path):
    file = docx(tmp_path / "a.docx", "<w:p>" + run("<w:t>Порог</w:t>") + run('<w:footnoteReference w:id="2"/>') + "</w:p>")
    with zipfile.ZipFile(file, "a") as archive:
        archive.writestr("word/footnotes.xml", f'<w:footnotes {W_NS}><w:footnote w:id="2">{p("Только для песков")}</w:footnote></w:footnotes>')
    assert "Только для песков" in docx_pages(file)[0].text


def test_docx_hidden_text_is_named(tmp_path):
    page = docx_pages(docx(tmp_path / "a.docx", p(PARAGRAPH) + "<w:p>" + run("<w:t>тайна</w:t>", "<w:vanish/>") + "</w:p>"))[0]
    assert "тайна" not in page.text and page.state == "doubtful"


def test_docx_break_inside_a_paragraph_splits_it(tmp_path):
    body = "<w:p>" + run('<w:t>до</w:t><w:br w:type="page"/><w:lastRenderedPageBreak/><w:t>после</w:t>') + "</w:p>"
    assert [(x.page, x.text) for x in docx_pages(docx(tmp_path / "a.docx", body))] == [(1, "до"), (2, "после")]


def test_docx_section_and_break_before(tmp_path):
    body = "<w:p><w:pPr><w:sectPr/></w:pPr>" + run("<w:t>один</w:t>") + "</w:p>" + p("два") + "<w:p><w:pPr><w:pageBreakBefore/></w:pPr>" + run("<w:t>три</w:t>") + "</w:p>"
    assert [x.text for x in docx_pages(docx(tmp_path / "a.docx", body))] == ["один", "два", "три"]


def test_docx_merged_cells_keep_columns(tmp_path):
    wide = '<w:tc><w:tcPr><w:gridSpan w:val="2"/></w:tcPr>' + p("шапка") + "</w:tc>"
    table = f"<w:tbl><w:tr>{wide}<w:tc>{p('в')}</w:tc></w:tr><w:tr><w:tc>{p('1')}</w:tc><w:tc>{p('2')}</w:tc><w:tc>{p('3')}</w:tc></w:tr></w:tbl>"
    page = docx_pages(docx(tmp_path / "a.docx", table))[0]
    assert "| шапка | | в |" in page.text and page.state == "doubtful"


def test_docx_formula_is_doubtful(tmp_path):
    body = p(PARAGRAPH) + "<w:p><m:oMath><m:r><m:t>a=b</m:t></m:r></m:oMath></w:p>"
    page = docx_pages(docx(tmp_path / "a.docx", body))[0]
    assert "a=b" in page.text and page.state == "doubtful"


@pytest.mark.parametrize("head", ['<!DOCTYPE x [<!ENTITY a "b">]>', "<broken"])
def test_dangerous_or_broken_docx_is_refused(tmp_path, head):
    with pytest.raises(LibraryError):
        docx_pages(docx(tmp_path / "a.docx", p("а"), head))


def test_not_a_docx(tmp_path):
    (tmp_path / "a.docx").write_bytes(b"zip?")
    with pytest.raises(LibraryError):
        docx_pages(tmp_path / "a.docx")


def test_previews_are_drawn_and_a_huge_sheet_is_scaled_down(tmp_path):
    import pymupdf

    document = pymupdf.open()
    document.new_page()
    document.new_page(width=14000, height=14000)
    document.save(tmp_path / "a.pdf")
    assert make_previews(tmp_path / "a.pdf", tmp_path / "preview") == 2
    assert pymupdf.Pixmap(preview_file(tmp_path / "preview", 2)).width <= 2001


# ---------- чтение моделью
class Reader:
    name, model = "fake", "fake"

    def __init__(self, *answers):
        self.answers, self.files = list(answers), []

    def ask(self, system, prompt, files=()):
        self.files.append(files)
        return Reply(self.answers.pop(0), "fake", 1, 1, 0.01)


def test_page_read_by_model_is_marked_and_numbers_are_compared(tmp_path):
    file = pdf(tmp_path / "a.pdf", [("Порог равен 12 %. " + PARAGRAPH, 11)])
    page = pdf_pages(file)[0]
    found, replies = read_page(Reader(json.dumps({"md": "Порог равен 72 %. " + PARAGRAPH, "unreadable": ["сноска"]})), "s", page, file, tmp_path / "scans")
    assert (found.state, found.method, len(replies)) == ("doubtful", "vision", 1)
    assert any("72" in r for r in found.reasons) and any("не прочитано" in r for r in found.reasons)


def test_short_retelling_does_not_replace_the_page(tmp_path):
    file = pdf(tmp_path / "a.pdf", [("Порог равен 12 %. " + PARAGRAPH, 11)])
    page = pdf_pages(file)[0]
    found, _ = read_page(Reader(json.dumps({"md": "Коротко."})), "s", page, file, tmp_path / "scans")
    assert found.text == page.text and found.method == "text" and found.state == "doubtful"


def test_failed_reading_keeps_the_page_as_it_was(tmp_path):
    file = scanned(tmp_path / "a.pdf")
    page = pdf_pages(file)[0]
    assert read_page(Reader("{}", "{}"), "s", page, file, tmp_path / "scans")[0] == page


def test_reading_without_json_does_not_stop_the_book(tmp_path):
    file = scanned(tmp_path / "a.pdf")
    page = pdf_pages(file)[0]
    assert read_page(Reader("не могу", "не могу"), "s", page, file, tmp_path / "scans") == (page, [])


def test_picture_is_a_note_and_not_a_doubt(tmp_path):
    body = p(PARAGRAPH) + "<w:p><w:r><w:drawing/></w:r></w:p>"
    page = docx_pages(docx(tmp_path / "a.docx", body))[0]
    assert page.state == "text" and page.reasons


@pytest.mark.parametrize("data", [[], {}, {"md": " "}, {"md": 1}, {"md": "<!-- page 3 --> а"}, {"md": "а", "unreadable": "б"}])
def test_reader_answer_is_checked(data):
    assert page_issues(data)


# ---------- глава из базы знаний
@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACE", tmp_path)
    folder = tmp_path / "library" / "book1"
    folder.mkdir(parents=True)
    (folder / "original.txt").write_text(f"{PARAGRAPH}\f" + "Пopистoсть пopoды пoкaзывaeт дoлю " * 10, encoding="utf-8")
    (folder / "source.json").write_text(json.dumps({"id": "book1", "file": "original.txt", "kind": "txt"}), encoding="utf-8")
    (tmp_path / "chapters.json").write_text('{"root": ".", "pdf_root": ".", "chapters": {}}', encoding="utf-8")
    entry = {"source": "book1", "pages": [[1, 2]], "prefix": "book1", "domain": "general", "title": "Глава", "book": "Книга"}
    (tmp_path / "library" / "chapters.json").write_text(json.dumps({"chapters": {"lib_one": entry}}), encoding="utf-8")
    return tmp_path


def test_chapter_from_library_is_loaded_and_unsure_pages_are_marked(library):
    build_extract("book1", False)
    chapter = load_chapter("lib_one")
    assert {u.page_pdf: u.needs_scan for u in chapter.units} == {1: False, 2: True}
    assert chapter.pdf is None and chapter.domain.name == "general"
    assert unsure_pages(load_source(library, "book1")) == {2}


def test_claim_from_an_unsure_page_is_unsure_even_if_the_quote_is_elsewhere(library):
    build_extract("book1", False)
    units = load_chapter("lib_one").units
    node = {"claims": [{"page_pdf": 2, "quote": "нет такой единицы", "needs_scan": False}, {"page_pdf": 1, "quote": "x", "needs_scan": False}]}
    assert [c["needs_scan"] for c in mark_unsure_claims(node, units)["claims"]] == [True, False]


def test_missing_page_report_is_not_trust(library):
    build_extract("book1", False)
    (library / "library" / "book1" / "pages.json").unlink()
    with pytest.raises(LibraryError):
        load_chapter("lib_one")


def test_registry_chapter_is_not_shadowed(library):
    (library / "chapters.json").write_text(json.dumps({"root": "books", "pdf_root": "books", "chapters": {
        "lib_one": {"file": "a.md", "pages": [[1, 1]], "prefix": "reg", "domain": "general", "title": "Из реестра", "book": "К"}}}), encoding="utf-8")
    (library / "books").mkdir()
    (library / "books" / "a.md").write_text("<!-- page 1 -->\n\nТекст", encoding="utf-8")
    assert load_chapter("lib_one").title == "Из реестра"


def test_unknown_chapter_is_explained(library):
    with pytest.raises(LibraryError, match="нет ни в"):
        load_chapter("lib_absent")


def test_chapter_before_extraction_is_explained(library):
    with pytest.raises(LibraryError, match="extract"):
        load_chapter("lib_one")


@pytest.mark.parametrize("name", ["../x", "", "a/b", ".."])
def test_source_never_leaves_the_library(library, name):
    with pytest.raises(LibraryError):
        load_source(library, name)


def test_original_outside_the_folder_is_refused(library):
    (library / "library" / "book1" / "source.json").write_text(json.dumps({"file": "../../secret", "kind": "txt"}), encoding="utf-8")
    with pytest.raises(LibraryError):
        load_source(library, "book1")


def test_other_chapters_do_not_touch_the_library(tmp_path):
    assert library_chapter(tmp_path, "latyshova_gl5_par17-20") is None
    assert library_chapter(tmp_path, "lib_absent") is None


# ---------- общая предметная область
def test_general_domain_is_enough_for_every_stage():

    domain = paths.workspace() / "domain" / "general"
    chapter = Chapter("demo", "dm", "Глава", "Книга", domain, (), "demo.md")
    assert "Заблуждения" in context_of(chapter) and routing_context(chapter)
    assert json.loads((domain / "physics_checklist.json").read_text(encoding="utf-8"))
    style, templates = load_style(domain), load_templates(domain / "templates")
    scenes = {"flow": {"nodes": [{"id": "a", "text": "Вход", "kind": "data"}, {"id": "b", "text": "Итог", "kind": "result"}], "edges": [{"from": "a", "to": "b"}]},
              "plot": {"x_label": "х", "y_label": "у", "numeric": True, "series": [{"name": "ряд", "points": [[0, 1], [1, 2]]}]}}
    for name, data in scenes.items():
        assert scene_issues(templates[name], data, style) == []
        assert render(templates[name], data, style).startswith("<svg")


def test_units_know_nothing_about_scans_by_default():
    assert not any(u.needs_scan for u in parse_units({1: PARAGRAPH}))
