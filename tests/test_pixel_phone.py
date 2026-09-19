import importlib.util
import json
import pathlib
import unittest
from unittest.mock import patch

REPO = pathlib.Path(__file__).parents[1]
BRIDGE_PATH = REPO / "pixel-phone-bridge.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("pixel_phone_bridge", BRIDGE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class BridgeUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = load_bridge()

    def test_png_dimensions(self):
        png = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR"
               + (1080).to_bytes(4, "big") + (2400).to_bytes(4, "big"))
        self.assertEqual((1080, 2400), self.bridge.png_dimensions(png))
        with self.assertRaises(ValueError):
            self.bridge.png_dimensions(b"not a png")

    def test_denorm_clamps(self):
        self.assertEqual(0, self.bridge.denorm(-5, 1080))
        self.assertEqual(540, self.bridge.denorm(500, 1080))
        self.assertEqual(1079, self.bridge.denorm(1000, 1080))

    def test_keycodes_cover_basics(self):
        for key in ("BACK", "HOME", "RECENTS", "ENTER", "ESC", "TAB"):
            self.assertTrue(self.bridge.KEYCODES[key].startswith("KEYCODE_"))

    def test_bridge_detects_shizuku_recovery_without_restarting(self):
        bridge = self.bridge.BRIDGE
        with patch.object(bridge, 'backend', 'unavailable'), \
             patch.object(bridge, '_checked_at', 0), \
             patch.object(bridge, '_detect', return_value='rish') as detect:
            self.assertEqual('rish', bridge.refresh())
            self.assertEqual('rish', bridge.refresh())
            detect.assert_called_once()

    def test_opencode_default_is_free_muse_spark(self):
        cfg = json.loads((REPO / "pixel-opencode" / "opencode.json").read_text())
        self.assertEqual("opencode/muse-spark-1.3-contributor-free", cfg["model"])
        self.assertEqual("opencode/muse-spark-1.3-contributor-free", cfg["small_model"])

    def test_tool_files_present(self):
        tools = REPO / "pixel-opencode" / "tools"
        for name in ("pixel_run.ts", "pixel_ui.ts", "pixel_screenshot.ts"):
            self.assertTrue((tools / name).exists(), name)
        # Tools must point at the shared-localhost bridge, never a public host.
        for name in ("pixel_run.ts", "pixel_ui.ts", "pixel_screenshot.ts"):
            text = (tools / name).read_text()
            self.assertIn("127.0.0.1:18080", text)
            self.assertIn("Bearer", text)

    def test_inspection_returns_normalized_centers_and_hides_password_text(self):
        xml='''<hierarchy><node text="Open" clickable="true" enabled="true" bounds="[100,200][300,400]"/>
        <node text="secret" password="true" focusable="true" bounds="[0,0][200,100]"/>
        <node text="offscreen" bounds="[0,2500][100,2600]"/>
        <node text="hidden" bounds="[0,0][0,0]"/></hierarchy>'''
        data=self.bridge.ui_elements(xml,1000,2000)
        self.assertEqual(2,len(data['elements']))
        self.assertEqual([200,150],data['elements'][0]['center'])
        self.assertEqual('',data['elements'][1]['text'])
        self.assertTrue(data['elements'][1]['password'])


if __name__ == "__main__":
    unittest.main()
