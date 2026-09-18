import unittest
from repair_svg import apply_validated_patch, FAILED_ELEMENT


class RepairGateTest(unittest.TestCase):
    def setUp(self):
        self.original = '<svg xmlns="http://www.w3.org/2000/svg">' + FAILED_ELEMENT + '</svg>'
        self.patch = '<line x1="110" y1="100" x2="120" y2="100"/>'

    def test_applies_only_model_patch(self):
        result = apply_validated_patch(self.original, self.patch)
        self.assertTrue(result['corrected_validation']['valid'])
        self.assertEqual(result['corrected_output'], self.original.replace(FAILED_ELEMENT, self.patch))

    def test_rejects_changed_geometry(self):
        with self.assertRaises(ValueError):
            apply_validated_patch(self.original, self.patch.replace('110', '111'))

    def test_rejects_extra_content(self):
        with self.assertRaises(Exception):
            apply_validated_patch(self.original, self.patch + '<script>alert(1)</script>')

    def test_rejects_ambiguous_target(self):
        with self.assertRaises(ValueError):
            apply_validated_patch(self.original.replace(FAILED_ELEMENT, FAILED_ELEMENT * 2), self.patch)

    def test_full_document_must_pass(self):
        with self.assertRaises(ValueError):
            apply_validated_patch(self.original.replace('</svg>', '<script>alert(1)</script></svg>'), self.patch)


if __name__ == '__main__':
    unittest.main()
