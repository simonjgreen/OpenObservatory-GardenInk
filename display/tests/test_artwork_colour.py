"""Colour washes must survive reduction without tinting neutral feather detail."""
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gardenink.render import _load_art
from gardenink.palette import COLOURS


class ArtworkColourTests(unittest.TestCase):
    def render_patch(self, colour, mode='colour'):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'patch.png'
            Image.new('RGB', (32, 32), colour).save(path)
            return _load_art(str(path), 32, 32, mode)

    def test_light_coloured_wash_keeps_substantial_colour_coverage(self):
        image = self.render_patch((240, 180, 120))
        data = list(image.get_flattened_data() if hasattr(image, 'get_flattened_data') else image.getdata())
        coloured = sum(pixel not in COLOURS[:2] for pixel in data)
        self.assertGreater(coloured, len(data) * 0.65)
        self.assertLess(coloured, len(data) * 0.9)
        self.assertTrue(set(data) <= set(COLOURS))

    def test_neutral_and_dark_plumage_match_ink_rendering(self):
        for colour in ((255, 255, 255), (180, 180, 180), (80, 80, 80), (90, 50, 20)):
            with self.subTest(colour=colour):
                self.assertEqual(self.render_patch(colour).tobytes(),
                                 self.render_patch(colour, 'ink').tobytes())

    def test_ink_mode_keeps_coloured_source_monochrome(self):
        image = self.render_patch((240, 180, 120), 'ink')
        data = image.get_flattened_data() if hasattr(image, 'get_flattened_data') else image.getdata()
        self.assertTrue(set(data) <= set(COLOURS[:2]))


if __name__ == '__main__':
    unittest.main()
