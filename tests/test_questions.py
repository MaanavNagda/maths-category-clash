import json
import os
import tempfile
import unittest

from game import questions


def valid_data():
    return {
        "rounds": [{
            "name": "Round 1",
            "categories": [
                {"name": f"Cat {c}", "clues": [
                    {"value": v, "question": f"Q{v}?", "answer": f"A{v}"}
                    for v in (100, 200, 300, 400)]}
                for c in range(4)],
        }],
        "finale": {"category": "F", "question": "FQ", "answer": "FA"},
    }


class TestValidate(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(questions.validate(valid_data()), [])

    def test_root_not_object(self):
        self.assertTrue(questions.validate([1, 2, 3]))

    def test_missing_rounds(self):
        self.assertTrue(questions.validate({}))

    def test_wrong_category_count(self):
        d = valid_data()
        d["rounds"][0]["categories"].pop()
        errs = questions.validate(d)
        self.assertTrue(any("categories" in e for e in errs))

    def test_wrong_clue_count(self):
        d = valid_data()
        d["rounds"][0]["categories"][0]["clues"].pop()
        self.assertTrue(questions.validate(d))

    def test_bad_values(self):
        d = valid_data()
        d["rounds"][0]["categories"][0]["clues"][0]["value"] = 150
        errs = questions.validate(d)
        self.assertTrue(any("values" in e for e in errs))

    def test_missing_question(self):
        d = valid_data()
        del d["rounds"][0]["categories"][0]["clues"][0]["question"]
        self.assertTrue(questions.validate(d))

    def test_all_in_must_be_bool(self):
        d = valid_data()
        d["rounds"][0]["categories"][0]["clues"][0]["all_in"] = "yes"
        self.assertTrue(questions.validate(d))

    def test_finale_optional_but_checked(self):
        d = valid_data()
        del d["finale"]
        self.assertEqual(questions.validate(d), [])
        d["finale"] = {"category": "F"}
        self.assertTrue(questions.validate(d))

    def test_too_many_rounds(self):
        d = valid_data()
        d["rounds"] = d["rounds"] * 3
        self.assertTrue(questions.validate(d))


class TestLoad(unittest.TestCase):
    def _write(self, obj):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as fh:
            json.dump(obj, fh)
        self.addCleanup(os.unlink, path)
        return path

    def test_load_valid(self):
        data, errs = questions.load(self._write(valid_data()))
        self.assertEqual(errs, [])
        self.assertIsNotNone(data)

    def test_load_missing_file(self):
        data, errs = questions.load("/nonexistent/file.json")
        self.assertIsNone(data)
        self.assertTrue(errs)

    def test_load_bad_json(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as fh:
            fh.write("{not json")
        self.addCleanup(os.unlink, path)
        data, errs = questions.load(path)
        self.assertIsNone(data)
        self.assertTrue(any("JSON" in e for e in errs))

    def test_normalise_sorts_clues(self):
        d = valid_data()
        clues = d["rounds"][0]["categories"][0]["clues"]
        clues.reverse()
        data, _ = questions.load(self._write(d))
        values = [c["value"] for c in
                  data["rounds"][0]["categories"][0]["clues"]]
        self.assertEqual(values, [100, 200, 300, 400])


if __name__ == "__main__":
    unittest.main()
