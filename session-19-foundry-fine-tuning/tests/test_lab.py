import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import unittest
from unittest.mock import patch
from lab import main, validate_source
from support import ROOT

class DataTests(unittest.TestCase):
    def source(self):
        return [json.loads(line) for line in (ROOT / "data/curated-tickets.jsonl").read_text().splitlines()]

    def test_corpus_split_counts(self):
        self.assertEqual(validate_source(self.source()), {"train": 160, "validation": 40})

    def test_family_leakage_rejected(self):
        source = self.source()
        source[0]["family"] = source[-1]["family"]
        with self.assertRaisesRegex(ValueError, "family"):
            validate_source(source)

    def test_normalized_duplicates_rejected(self):
        source = self.source()
        source[1]["text"] = "  " + source[0]["text"].upper() + "  "
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_source(source)

    def test_holdout_leakage_rejected(self):
        source = self.source()
        source[0]["text"] = json.loads((ROOT / "data/cases.jsonl").read_text().splitlines()[0])["input"]
        with self.assertRaisesRegex(ValueError, "Holdout"):
            validate_source(source)

    def test_unknown_label_rejected(self):
        source = self.source()
        source[0]["expected"]["priority"] = "critical"
        with self.assertRaisesRegex(ValueError, "label"):
            validate_source(source)

    def test_guard_prevents_upload(self):
        with patch("sys.argv", ["lab.py", "train"]), patch("lab.project") as factory:
            with self.assertRaises(SystemExit):
                main()
            factory.assert_not_called()

if __name__ == "__main__":
    unittest.main()
