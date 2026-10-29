import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kindle_books import books, covers
from PIL import Image


def candidate(name="Books\\John Steinbeck\\Of Mice and Men.epub", **kwargs):
    return dict(username="book-peer", filename=name, size=130000, free=True,
                speed=100000, queue=0, attributes={}, **kwargs)


class FakeSoulseek:
    def __init__(self):
        self.connected = False

    def connect(self):
        self.connected = True

    def search(self, query):
        return [candidate()]

    def close(self):
        pass


class FakeJobs:
    added = []

    def __init__(self, client):
        pass

    def add(self, *args):
        self.added.append(args)
        return "Queued"

    def listing(self, **kwargs):
        return []

    def close(self):
        pass


class BooksTests(unittest.TestCase):
    def test_rank_prefers_matching_epub_and_rejects_audio(self):
        result = books.rank([
            candidate("Books\\Of Mice and Men.pdf"),
            candidate("Books\\John Steinbeck\\Of Mice and Men.epub"),
            candidate("Audiobooks\\Of Mice and Men.mp3"),
            candidate("Books\\A Different Book.epub"),
        ], "Of Mice and Men", "John Steinbeck")
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0]["filename"].endswith(".epub"))

    def test_terminal_control_sequences_are_not_displayed(self):
        self.assertNotIn("\x1b", books.display_name(candidate("\x1b[2JBook.epub")))
        self.assertNotIn("\n", books.clean("Book\nForged prompt"))

    def test_duplicate_peers_do_not_fill_the_result_picker(self):
        original = candidate()
        duplicate = dict(original, username="another-peer")
        result = books.rank([original, duplicate], "Of Mice and Men", "John Steinbeck")
        self.assertEqual(len(result), 1)

    def test_library_hides_opaque_file_identifiers(self):
        self.assertEqual(books.library_title("Of Mice and Men - John Steinbeck-2fcac4e9.azw3"),
                         "Of Mice and Men - John Steinbeck")

    def test_epub_cannot_escape_its_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "unsafe.epub"
            with zipfile.ZipFile(p, "w") as archive:
                archive.writestr("mimetype", "application/epub+zip")
                archive.writestr("../outside", "unsafe")
            with self.assertRaisesRegex(ValueError, "unsafe paths"):
                books.validate_book(p)

    def test_symlink_book_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p / "source.txt").write_text("Book text")
            (p / "link.txt").symlink_to(p / "source.txt")
            with self.assertRaises(ValueError):
                books.validate_book(p / "link.txt")

    def run_chat(self, messages):
        FakeJobs.added = []
        value = dict(action="search", title="Of Mice and Men", author="John Steinbeck",
                     query="Mice Men Steinbeck", reply="I’ll search for it.")
        stream = io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(books, "STATE", Path(folder)), patch.object(books, "Soulseek", FakeSoulseek), \
                 patch.object(books, "Jobs", FakeJobs), patch.object(books, "intent", return_value=value), \
                 patch("builtins.input", side_effect=messages), contextlib.redirect_stdout(stream):
                self.assertEqual(books.main([]), 0)
        return stream.getvalue()

    def test_search_requires_selection_before_download(self):
        output = self.run_chat(["Find Of Mice and Men", "quit"])
        self.assertIn("Choose a result number", output)
        self.assertFalse(FakeJobs.added)

    def test_first_result_can_be_selected(self):
        self.run_chat(["Find Of Mice and Men", "1", "quit"])
        self.assertEqual(len(FakeJobs.added), 1)
        self.assertEqual(FakeJobs.added[0][1], "Of Mice and Men")

    def test_library_includes_untracked_kindle_books(self):
        with patch.object(books, "kindle_library", return_value=[
            dict(name="Existing Personal Book.azw3", path="Existing Personal Book.azw3", size=123)
        ]):
            output = self.run_chat(["2", "quit"])
        self.assertIn("Existing Personal Book", output)
        self.assertFalse(FakeJobs.added)

    def test_blank_cover_rejected_and_custom_cover_is_usable(self):
        with tempfile.TemporaryDirectory() as folder:
            blank = Path(folder) / "blank.jpg"
            Image.new("RGB", (400, 600), "white").save(blank)
            self.assertFalse(covers.usable(blank))
            custom = Path(folder) / "custom.jpg"
            covers.compose("A Book Without a Cover", "A. Reader", custom)
            self.assertTrue(covers.usable(custom))
            with Image.open(custom) as image:
                self.assertEqual(image.size, (1200, 1800))

    def test_cover_lookup_rejects_wrong_author(self):
        import json
        data = json.dumps({"docs": [dict(title="Of Mice and Men", author_name=["Wrong Author"], cover_i=123)]}).encode()
        with tempfile.TemporaryDirectory() as folder, patch.object(covers, "_request", return_value=data) as request:
            self.assertIsNone(covers.lookup("Of Mice and Men", "John Steinbeck", Path(folder) / "cover.jpg"))
            self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
