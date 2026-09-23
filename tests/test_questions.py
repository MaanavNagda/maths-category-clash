import os
import tempfile
import unittest

from game import questions


def clue(cat, pts, q="Q", a="A", extra=""):
    return (f"Category: {cat}\nPoints: {pts}\nQuestion: {q}\nAnswer: {a}\n"
            + (extra + "\n" if extra else ""))


def board_text(n_cats=4, n_clues=4):
    blocks = []
    for c in range(n_cats):
        for i in range(n_clues):
            blocks.append(clue(f"Cat {c}", (i + 1) * 100))
    return "\n".join(blocks)


def write(tmp, name, text):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class TestParseBlocks(unittest.TestCase):
    def test_basic(self):
        blocks, errors = parse = questions.parse_blocks(
            "Category: A\nPoints: 100\nQuestion: q\nAnswer: a\n")
        self.assertEqual(errors, [])
        self.assertEqual(blocks, [
            {"category": "A", "points": "100", "question": "q",
             "answer": "a"}])

    def test_blank_line_separates(self):
        blocks, _ = questions.parse_blocks(
            "Category: A\nPoints: 1\nQuestion: q\nAnswer: a\n\n"
            "Category: B\nPoints: 2\nQuestion: q2\nAnswer: a2\n")
        self.assertEqual(len(blocks), 2)

    def test_multiline_question(self):
        blocks, _ = questions.parse_blocks(
            "Category: A\nPoints: 1\nQuestion: line one\nline two\n"
            "Answer: a\n")
        self.assertEqual(blocks[0]["question"], "line one\nline two")

    def test_unknown_key_is_continuation(self):
        """A 'Key:' line that isn't a known field joins the current value."""
        blocks, _ = questions.parse_blocks(
            "Category: A\nPoints: 1\n"
            "Question: Note: this stays in the question\nAnswer: a\n")
        self.assertIn("Note:", blocks[0]["question"])

    def test_stray_text_errors(self):
        _, errors = questions.parse_blocks("hello\n")
        self.assertTrue(errors)


class TestBoards(unittest.TestCase):
    def test_valid_board(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "b.md", board_text())
            board, errors = questions.load_board(path)
        self.assertEqual(errors, [])
        self.assertEqual(len(board["categories"]), 4)
        self.assertEqual(board["timers"], [30, 45, 60, 120])
        for cat in board["categories"]:
            self.assertEqual(len(cat["clues"]), 4)
            self.assertEqual([c["value"] for c in cat["clues"]],
                             [100, 200, 300, 400])

    def test_clues_sorted_by_points(self):
        text = ""
        for c in range(4):
            for v in (400, 100, 300, 200):      # scrambled order
                text += clue(f"C{c}", v) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            board, errors = questions.load_board(write(tmp, "b.md", text))
        self.assertEqual(errors, [])
        self.assertEqual(
            [c["value"] for c in board["categories"][0]["clues"]],
            [100, 200, 300, 400])

    def test_wrong_category_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, errors = questions.load_board(
                write(tmp, "b.md", board_text(n_cats=3)))
        self.assertTrue(any("4 categories" in e for e in errors))

    def test_wrong_clue_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, errors = questions.load_board(
                write(tmp, "b.md", board_text(n_clues=3)))
        self.assertTrue(any("4 clues" in e for e in errors))

    def test_missing_field(self):
        bad = "Category: A\nPoints: 100\nQuestion: q\n"  # no Answer
        with tempfile.TemporaryDirectory() as tmp:
            _, errors = questions.load_board(write(tmp, "b.md", bad))
        self.assertTrue(any("answer" in e for e in errors))

    def test_bad_points(self):
        bad = board_text() + clue("Cat 0", "abc")
        with tempfile.TemporaryDirectory() as tmp:
            _, errors = questions.load_board(write(tmp, "b.md", bad))
        self.assertTrue(any("integer" in e for e in errors))

    def test_all_in_flag(self):
        blocks = []
        for c in range(4):
            for i in range(4):
                extra = "All In: yes" if (c == 0 and i == 3) else ""
                blocks.append(clue(f"Cat {c}", (i + 1) * 100, extra=extra))
        with tempfile.TemporaryDirectory() as tmp:
            board, errors = questions.load_board(
                write(tmp, "b.md", "\n".join(blocks)))
        self.assertEqual(errors, [])
        self.assertTrue(board["categories"][0]["clues"][3]["all_in"])
        self.assertFalse(board["categories"][0]["clues"][0]["all_in"])

    def test_point_amount_alias(self):
        text = board_text().replace("Points:", "Point amount:")
        with tempfile.TemporaryDirectory() as tmp:
            board, errors = questions.load_board(write(tmp, "b.md", text))
        self.assertEqual(errors, [])
        self.assertEqual(
            board["categories"][0]["clues"][0]["value"], 100)

    def test_inline_daily_double_marker(self):
        blocks = []
        for c in range(4):
            for i in range(4):
                pts = f"{(i + 1) * 100} **daily double**" if (c, i) == (1, 2) \
                    else str((i + 1) * 100)
                blocks.append(clue(f"Cat {c}", pts))
        with tempfile.TemporaryDirectory() as tmp:
            board, errors = questions.load_board(
                write(tmp, "b.md", "\n".join(blocks)))
        self.assertEqual(errors, [])
        self.assertTrue(board["categories"][1]["clues"][2]["all_in"])
        self.assertEqual(board["categories"][1]["clues"][2]["value"], 300)

    def test_valid_bonus(self):
        with tempfile.TemporaryDirectory() as tmp:
            bonus, errors = questions.load_bonus(
                write(tmp, "x.md", board_text(n_cats=2, n_clues=2)))
        self.assertEqual(errors, [])
        self.assertEqual(len(bonus["categories"]), 2)
        self.assertEqual(bonus["timers"], [120, 300])

    def test_missing_file(self):
        _, errors = questions.load_board("/nonexistent/file.md")
        self.assertTrue(any("not found" in e.lower() for e in errors))


class TestFinale(unittest.TestCase):
    def test_valid(self):
        text = ("Category: Finals\nQuestion: FQ\nAnswer: FA\n"
                "Seconds: 240\n")
        with tempfile.TemporaryDirectory() as tmp:
            fin, errors = questions.load_finale(write(tmp, "f.md", text))
        self.assertEqual(errors, [])
        self.assertEqual(fin["category"], "Finals")
        self.assertEqual(fin["seconds"], 240)

    def test_default_seconds(self):
        text = "Category: Finals\nQuestion: FQ\nAnswer: FA\n"
        with tempfile.TemporaryDirectory() as tmp:
            fin, errors = questions.load_finale(write(tmp, "f.md", text))
        self.assertEqual(errors, [])
        self.assertEqual(fin["seconds"], 300)

    def test_two_blocks_rejected(self):
        text = ("Category: A\nQuestion: q\nAnswer: a\n\n"
                "Category: B\nQuestion: q\nAnswer: a\n")
        with tempfile.TemporaryDirectory() as tmp:
            _, errors = questions.load_finale(write(tmp, "f.md", text))
        self.assertTrue(any("one block" in e for e in errors))

    def test_missing_question(self):
        text = "Category: A\nAnswer: a\n"
        with tempfile.TemporaryDirectory() as tmp:
            _, errors = questions.load_finale(write(tmp, "f.md", text))
        self.assertTrue(any("question" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
