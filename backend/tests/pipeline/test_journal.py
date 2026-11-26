"""Сверка журнала ручных правок с историей git: без сети и модели."""

import subprocess

from glava.pipeline.steps.journal import Commit, build_journal_check, chapter_of, check, count_minutes, diff_rows, rows_of

CH = "demo_gl1"
LAYER = f"workspace/work/{CH}/layer.json"
HEADER = "time,chapter,file,what_changed,person_minutes,people,run_no,reason\n"


def row(file: str = LAYER, minutes: str = "5", chapter: str = CH) -> dict[str, str]:
    return {"time": "2026-12-02T10:15", "chapter": chapter, "file": file, "what_changed": "число", "person_minutes": minutes, "people": "1", "run_no": "1", "reason": "опечатка"}


def test_chapter_of_knows_work_out_and_errata():
    assert chapter_of(LAYER) == CH
    assert chapter_of(f"workspace/out/{CH}/data.js") == CH
    assert chapter_of(f"workspace/domain/geology/errata/{CH}.manual.json") == CH
    assert chapter_of("backend/glava/x.py") is None


def test_manual_edit_with_its_row_and_rebuilt_course_passes():
    commit = Commit("a" * 40, "fix: число в слое", (LAYER, f"workspace/out/{CH}/data.js", f"workspace/work/{CH}/audit.json", "manual_edits.csv"), (row(),))
    assert check([commit]).problems == []


def test_manual_edit_without_row_is_named():
    commit = Commit("b" * 40, "fix: число в слое", (LAYER,))
    problems = check([commit]).problems
    assert len(problems) == 1 and LAYER in problems[0]


def test_build_commit_needs_no_row_but_must_not_carry_one():
    built = Commit("c" * 40, f"run 1: {CH}", (LAYER, f"workspace/out/{CH}/data.js"))
    assert check([built]).problems == []
    mixed = Commit("d" * 40, "build: пересборка", (LAYER, "manual_edits.csv"), (row(),))
    assert "коммите сборки" in check([mixed]).problems[0]


def test_row_without_change_in_its_commit_is_named():
    commit = Commit("e" * 40, "docs: журнал", ("manual_edits.csv",), (row(),))
    assert "не меняет" in check([commit]).problems[0]


def test_folder_and_several_files_in_one_row_cover_their_paths():
    pictures = f"workspace/work/{CH}/pictures"
    commit = Commit("f" * 40, "fix: рисунки", (f"{pictures}/a.svg", f"workspace/work/{CH}/tasks.json", "manual_edits.csv"), (row(f"{pictures}; workspace/work/{CH}/tasks.json"),))
    assert check([commit]).problems == []


def test_other_chapter_is_skipped_when_one_is_asked():
    commit = Commit("1" * 40, "fix: другая глава", ("workspace/work/other/layer.json",))
    assert check([commit], CH).problems == []


def test_minutes_are_summed_and_missing_ones_counted():
    result = count_minutes(check([]), [row(minutes="10"), row(minutes="2,5"), row(minutes="")])
    assert result.minutes[CH] == 12.5 and result.no_minutes[CH] == 1


def test_rows_added_and_removed_by_a_commit():
    before = rows_of(HEADER + "t,c,f,w,1,1,1,r\n")
    after = rows_of(HEADER + "t,c,f,w,1,1,1,r\nt2,c,f,w,2,1,1,r\n")
    added, removed = diff_rows(before, after)
    assert [r["time"] for r in added] == ["t2"] and removed == []
    assert diff_rows(after, before)[1][0]["time"] == "t2"


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True, capture_output=True)


def _commit(repo, message, files):
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def test_real_git_history_is_read(tmp_path):
    # Arrange: заморозка, сборка, ручная правка со строкой журнала, правка без строки
    _git(tmp_path, "init", "-q")
    _commit(tmp_path, "init", {"manual_edits.csv": HEADER})
    _git(tmp_path, "tag", "freeze")
    _commit(tmp_path, f"run 1: {CH}", {LAYER: "{}", f"workspace/out/{CH}/data.js": "1"})
    _commit(tmp_path, "fix: число", {LAYER: '{"a": 1}', f"workspace/out/{CH}/data.js": "2",
                                    "manual_edits.csv": HEADER + f"2026-12-02T10:15,{CH},{LAYER},число,5,1,1,опечатка\n"})
    assert build_journal_check(tmp_path, None, CH)

    # Act: правка без строки журнала
    _commit(tmp_path, "fix: ещё", {LAYER: '{"a": 2}'})

    # Assert
    assert not build_journal_check(tmp_path, "freeze", CH)
