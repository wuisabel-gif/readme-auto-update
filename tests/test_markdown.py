import unittest

from readme_auto_update.markdown import managed_content, markers, update_document


class MarkdownTests(unittest.TestCase):
    def test_creates_document_and_markers(self):
        updated = update_document("", "readme-auto-update", "## Work\n\nUseful things.")
        start, end = markers("readme-auto-update")
        self.assertTrue(updated.startswith("# GitHub Profile\n"))
        self.assertIn(start, updated)
        self.assertIn("Useful things.", updated)
        self.assertIn(end, updated)

    def test_preserves_manual_content(self):
        source = """# Example User

Manual intro.

<!-- README-AUTO-UPDATE:START:readme-auto-update -->
Old generated text.
<!-- README-AUTO-UPDATE:END:readme-auto-update -->

Manual footer.
"""
        updated = update_document(source, "readme-auto-update", "New generated text.")
        self.assertIn("Manual intro.", updated)
        self.assertIn("Manual footer.", updated)
        self.assertNotIn("Old generated text.", updated)
        self.assertEqual(
            managed_content(updated, "readme-auto-update"), "New generated text."
        )

    def test_rejects_unbalanced_markers(self):
        source = "<!-- README-AUTO-UPDATE:START:readme-auto-update -->\ncontent"
        with self.assertRaisesRegex(ValueError, "Both managed section markers"):
            update_document(source, "readme-auto-update", "replacement")

    def test_rejects_generated_marker_injection(self):
        generated = "<!-- README-AUTO-UPDATE:END:readme-auto-update -->"
        with self.assertRaisesRegex(ValueError, "must not contain"):
            update_document("# Demo\n", "readme-auto-update", generated)


if __name__ == "__main__":
    unittest.main()
