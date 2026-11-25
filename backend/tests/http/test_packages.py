import io
import json
import stat
import zipfile
from pathlib import Path
from typing import Any

import pytest
from glava.modules.review.packages import Limits, extract_package
from glava.shared.http.errors import ApiError

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


def package(**extra: Any) -> dict[str, Any]:
    return {"package_id": "pkg", "chapter": "alpha_gl1", "items": [], "scenes": [],
            "frames": [{"id": "F1", "file": "frames/F1.png"}], **extra}


def archive(files: dict[str, bytes | str]) -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as file:
        for name, content in files.items():
            file.writestr(name, content)
    buffer.seek(0)
    return buffer


def good(extra: dict[str, bytes | str] | None = None, **fields: Any) -> io.BytesIO:
    return archive({"package.json": json.dumps(package(**fields)), "frames/F1.png": PNG, **(extra or {})})


def files_in(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


def test_good_package_is_extracted(tmp_path: Path) -> None:
    found = extract_package(good(), tmp_path / "up")

    assert (found.package_id, found.chapter) == ("pkg", "alpha_gl1")
    assert files_in(tmp_path / "up") == ["frames/F1.png", "package.json"]


def test_single_top_folder_is_removed(tmp_path: Path) -> None:
    source = archive({"мой пакет/package.json": json.dumps(package()), "мой пакет/frames/F1.png": PNG, "__MACOSX/мой пакет/._F1.png": b"x"})

    extract_package(source, tmp_path / "up")

    assert files_in(tmp_path / "up") == ["frames/F1.png", "package.json"]


def test_key_files_and_foreign_types_are_dropped(tmp_path: Path) -> None:
    extra = {"key.json": "{}", "KEY.PNG": PNG, "frames/answer_Key_1.png": PNG, "run.py": "x", "a.exe": "x", "frames/package.json": "{}", ".env": "x"}

    extract_package(good(extra), tmp_path / "up")

    assert files_in(tmp_path / "up") == ["frames/F1.png", "package.json"]


@pytest.mark.parametrize("name", ["../evil.png", "frames/../../evil.png", "/abs.png", "C:/evil.png", "..\\evil.png", "frames/con.png", "frames/a.png ",
                                  "frames/b:ads.png", "//host/share/x.png", "../key.json"])
def test_unsafe_path_rejects_whole_archive(tmp_path: Path, name: str) -> None:
    with pytest.raises(ApiError) as caught:
        extract_package(good({name: PNG}), tmp_path / "up")

    assert caught.value.status == 422
    assert not (tmp_path / "up").exists()
    assert not list(tmp_path.rglob("evil.png"))


def test_symlink_entry_is_rejected(tmp_path: Path) -> None:
    buffer = good()
    link = zipfile.ZipInfo("frames/link.png")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(buffer, "a") as file:
        file.writestr(link, "/etc/passwd")
    buffer.seek(0)

    with pytest.raises(ApiError) as caught:
        extract_package(buffer, tmp_path / "up")

    assert caught.value.status == 422


def test_same_file_twice_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ApiError) as caught:
        extract_package(good({"FRAMES/f1.PNG": PNG}), tmp_path / "up")

    assert caught.value.status == 422


@pytest.mark.parametrize(("limits", "extra"), [
    (Limits(total_bytes=2000), {"frames/F2.png": b"0" * 5000}), (Limits(file_bytes=1000), {"frames/F2.png": b"0" * 5000}),
    (Limits(entries=3), {f"frames/F{n}.png": PNG for n in range(2, 9)}), (Limits(), {"frames/F2.png": b"0" * 30_000_000}),
])
def test_zip_bomb_is_rejected_and_cleaned(tmp_path: Path, limits: Limits, extra: dict[str, bytes | str]) -> None:
    with pytest.raises(ApiError) as caught:
        extract_package(good(extra), tmp_path / "up", limits)

    assert caught.value.status == 413
    assert not (tmp_path / "up").exists()


def test_size_is_counted_by_real_bytes_not_by_header(tmp_path: Path) -> None:
    buffer = good({"frames/F2.png": b"0" * 5000})
    raw = buffer.getvalue().replace((5000).to_bytes(4, "little"), (10).to_bytes(4, "little"))

    with pytest.raises(ApiError) as caught:
        extract_package(io.BytesIO(raw), tmp_path / "up", Limits(total_bytes=2000))

    assert caught.value.status in (413, 422)
    assert not (tmp_path / "up").exists()


@pytest.mark.parametrize("source", [
    io.BytesIO(b"not a zip"), archive({"readme.txt": "x"}), archive({"package.json": "{нет"}), archive({"package.json": "[]"}),
    good(package_id="../x"), good(package_id=5), good(package_id="has_key"), good(package_id="con"), good(frames=[{"id": "F1", "file": "frames/none.png"}]),
    good(frames=[{"id": "F1", "file": "../F1.png"}]), good(frames="нет"), good(frames=[{"id": "F1"}]),
    archive({"a/package.json": "{}", "b/package.json": "{}"}),
])
def test_wrong_package_is_422_with_russian_text(tmp_path: Path, source: io.BytesIO) -> None:
    with pytest.raises(ApiError) as caught:
        extract_package(source, tmp_path / "up")

    assert caught.value.status == 422
    assert any("а" <= letter <= "я" for letter in caught.value.message)
    assert not (tmp_path / "up").exists()


def test_encrypted_entry_is_rejected(tmp_path: Path) -> None:
    raw = bytearray(good().getvalue())
    start = raw.find(b"PK\x01\x02")
    while start != -1:
        raw[start + 8] |= 1
        start = raw.find(b"PK\x01\x02", start + 4)

    with pytest.raises(ApiError) as caught:
        extract_package(io.BytesIO(bytes(raw)), tmp_path / "up")

    assert caught.value.status == 422
