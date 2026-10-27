import tempfile
import unittest
from pathlib import Path

from moviecheck.inputs import extract_listing_names, load_queries, parse_filename


class DirectoryInputTests(unittest.TestCase):
    def test_extensionless_release_names_from_user_examples(self):
        names = [
            "Final.Interview.2026.1080p.SCREENER.WEB-DL.H264.AAC-AOC",
            "Mayday.2026.1080p.WEB.h264-ETHEL",
            "Matchbox The Movie 2026 1080p WEB-DL HEVC x265 10Bit DDP5.1 Subs KINGDOM",
            "The.Fix.(2026).1080p.WEB-DL.DDP2.0.x264",
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "movies.txt"
            source.write_text("\n".join(names), encoding="utf-8")
            queries = load_queries(source)
            self.assertEqual(len(queries), 4)
            self.assertEqual({query.title for query in queries}, {"Final Interview", "Mayday", "Matchbox The Movie", "The Fix"})
            self.assertTrue(all(query.year == 2026 for query in queries))

    def test_mixed_files_directories_and_sidecars(self):
        content = "Movie.2020.mkv\nAnother.Movie.2021.1080p-WEB\nTotal Recall (1990)\nFilm.srt\nposter.jpg\nnotes.nfo\narchive.zip\nreport.html\n.DS_Store\nSamples\n"
        self.assertEqual(extract_listing_names(content), ["Movie.2020.mkv", "Another.Movie.2021.1080p-WEB", "Total Recall (1990)"])

    def test_powershell_directory_rows_have_no_length_column(self):
        content = '''Directory: D:\\Filmy
Mode LastWriteTime Length Name
---- ------------- ------ ----
d----- 27.10.2026 12:00 Final.Interview.2026.1080p-WEB
d----- 10/27/2026 12:00 PM 1984 (1984)
-a---- 27.10.2026 12:00 1234 Movie.2020.mp4
-a---- 27.10.2026 12:00 100 Movie.srt
'''
        self.assertEqual(extract_listing_names(content), ["Final.Interview.2026.1080p-WEB", "1984 (1984)", "Movie.2020.mp4"])

    def test_unix_directory_rows_and_totals(self):
        content = '''total 10
drwxr-xr-x 2 user staff 4096 Oct 27 12:00 Final.Interview.2026.1080p-WEB
-rw-r--r-- 1 user staff 1234 Oct 27 12:00 Movie.2020.mkv
drwxr-xr-x 2 user staff 4096 Oct 27 12:00 Samples
'''
        self.assertEqual(extract_listing_names(content), ["Final.Interview.2026.1080p-WEB", "Movie.2020.mkv"])

    def test_directory_paths_and_trailing_separators(self):
        for name in ("Inception.2010/", "Inception.2010\\", r"D:\Filmy\Inception.2010" + "\\", "/Volumes/Movies/Inception.2010/"):
            with self.subTest(name=name):
                query = parse_filename(name)
                self.assertEqual((query.title, query.year), ("Inception", 2010))

    def test_plain_titles_and_dotted_titles_without_year(self):
        self.assertEqual(extract_listing_names("Inception\nDr.Strangelove\n1917\n"), ["Inception", "Dr.Strangelove", "1917"])
        self.assertEqual(parse_filename("Dr.Strangelove").title, "Dr Strangelove")
        self.assertIsNone(parse_filename("1917").year)

    def test_duplicate_folder_and_video_entry_keep_video_and_remakes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "movies.txt"
            path.write_text("Dune.1984\nDune.1984.mkv\nDune.2021\nDune.2021.mp4\n", encoding="utf-8")
            queries = load_queries(path)
            self.assertEqual([(query.title, query.year) for query in queries], [("Dune", 1984), ("Dune", 2021)])
            self.assertTrue(all(query.filename.endswith((".mkv", ".mp4")) for query in queries))

    def test_separate_video_editions_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "movies.txt"
            path.write_text("Movie.2020.720p.mp4\nMovie.2020.1080p.mkv\n", encoding="utf-8")
            self.assertEqual(len(load_queries(path)), 2)

    def test_movie_folder_is_one_entry_with_or_without_recursion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            movie = root / "Inception.2010.1080p-WEB"
            movie.mkdir()
            (movie / "Inception.2010.mkv").touch()
            (movie / "Inception.2010.mp4").touch()
            (movie / "Samples").mkdir()
            (movie / "Samples" / "Sample.mkv").touch()
            (movie / "poster.jpg").touch()
            for recursive in (False, True):
                with self.subTest(recursive=recursive):
                    queries = load_queries(root, recursive)
                    self.assertEqual(len(queries), 1)
                    self.assertEqual((queries[0].title, queries[0].year), ("Inception", 2010))
                    self.assertEqual(queries[0].filename, movie.name)

    def test_selected_movie_folder_uses_its_name_for_generic_video_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            movie = Path(directory) / "Final.Interview.2026.1080p-WEB"
            movie.mkdir()
            (movie / "video.mkv").touch()
            queries = load_queries(movie)
            self.assertEqual([(query.title, query.year) for query in queries], [("Final Interview", 2026)])

    def test_folder_without_year_can_use_year_of_matching_video(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            movie = root / "Inception"
            movie.mkdir()
            (movie / "Inception.2010.mkv").touch()
            query = load_queries(root)[0]
            self.assertEqual((query.title, query.year), ("Inception", 2010))

    def test_collection_folders_only_descend_when_recursive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Loose.Movie.2021.mp4").touch()
            category = root / "Dramaty"
            category.mkdir()
            (category / "Another.Movie.2020.1080p-WEB").mkdir()
            self.assertEqual(len(load_queries(root)), 1)
            queries = load_queries(root, recursive=True)
            self.assertEqual({query.title for query in queries}, {"Loose Movie", "Another Movie"})

    def test_extensionless_movie_folder_needs_no_local_video_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Mayday.2026.1080p.WEB.h264-ETHEL").mkdir()
            self.assertEqual(load_queries(root)[0].title, "Mayday")
