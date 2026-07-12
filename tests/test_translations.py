import unittest

from app.translations import build_translations


class TranslationTests(unittest.TestCase):
    def test_languages_expose_the_same_keys(self):
        translations = build_translations({"gpu": "Test GPU"})

        self.assertEqual(set(translations["en"]), set(translations["ru"]))

    def test_gpu_label_uses_system_information(self):
        translations = build_translations({"gpu": "Test GPU"})

        self.assertEqual(translations["en"]["section_gpu"], "Test GPU")
        self.assertEqual(translations["ru"]["section_gpu"], "Test GPU")


if __name__ == "__main__":
    unittest.main()
