import os

import pytest

from rag_mcp.ingest import build_chunks, chunk_words, load_documents


def test_chunk_words_overlaps_windows():
    text = " ".join(f"w{i}" for i in range(10))
    chunks = chunk_words(text, size=4, overlap=1)
    assert chunks == ["w0 w1 w2 w3", "w3 w4 w5 w6", "w6 w7 w8 w9"]


def test_chunk_words_short_and_empty_text():
    assert chunk_words("just a few words", size=50, overlap=10) == ["just a few words"]
    assert chunk_words("", size=50, overlap=10) == []


@pytest.mark.parametrize("size,overlap", [(0, 0), (5, 5), (5, -1)])
def test_chunk_words_rejects_bad_settings(size, overlap):
    with pytest.raises(ValueError):
        chunk_words("a b c", size=size, overlap=overlap)


def test_load_documents_reads_supported_types_only(tmp_path):
    (tmp_path / "notes.txt").write_text("hello world")
    (tmp_path / "data.json").write_text('{"a": 1}')
    (tmp_path / "conf.yaml").write_text("key: value")
    (tmp_path / "image.png").write_bytes(b"\x89PNG")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deep.md").write_text("# Title")

    names = [name for name, _ in load_documents(tmp_path)]
    assert names == ["conf.yaml", "data.json", "notes.txt", "sub/deep.md"]


def test_load_documents_skips_broken_files(tmp_path):
    (tmp_path / "bad.json").write_text("{not valid json")
    (tmp_path / "good.txt").write_text("fine")
    names = [name for name, _ in load_documents(tmp_path)]
    assert names == ["good.txt"]


def test_load_documents_skips_symlinks_leaving_the_data_dir(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("do not index me")
    try:
        os.symlink(secret, data / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported here")
    (data / "ok.txt").write_text("fine")

    names = [name for name, _ in load_documents(data)]
    assert names == ["ok.txt"]


def test_build_chunks_ids_are_source_and_index():
    # windows: [one two three] [three four five] [five six]
    chunks = build_chunks([("a.txt", "one two three four five six")], size=3, overlap=1)
    assert [c.id for c in chunks] == ["a.txt::0", "a.txt::1", "a.txt::2"]
    assert chunks[2].text == "five six"
