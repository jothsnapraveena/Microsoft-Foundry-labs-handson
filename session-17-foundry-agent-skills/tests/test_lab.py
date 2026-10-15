import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from io import BytesIO
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from lab import downloaded_instructions, local_validation, main, parse_skill

class SkillTests(unittest.TestCase):
    def test_versions_have_distinct_content(self):
        result = local_validation()
        self.assertNotEqual(result["skills"]["v1"]["body_sha256"], result["skills"]["v2"]["body_sha256"])

    def test_missing_metadata_rejected(self):
        for value in ("plain text", "---\nname: Bad Name\n---\nbody", "---\nname: okay\n---\nbody"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_skill(value)

    def test_zip_reads_only_skill_without_extracting_paths(self):
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("skill/SKILL.md", "---\nname: good\ndescription: demo\n---\nhello")
        self.assertEqual(downloaded_instructions(buffer.getvalue()), "hello")

    def test_ambiguous_download_rejected(self):
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("a/SKILL.md", "x")
            archive.writestr("b/SKILL.md", "x")
        with self.assertRaises(ValueError):
            downloaded_instructions(buffer.getvalue())

    def test_guard(self):
        with patch("sys.argv", ["lab.py", "register"]), patch("lab.project") as factory:
            with self.assertRaises(SystemExit):
                main()
            factory.assert_not_called()

if __name__ == "__main__":
    unittest.main()
