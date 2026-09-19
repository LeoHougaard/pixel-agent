import importlib.util
import pathlib
import sys
import unittest
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).parents[1] / "pixel_agent.py"
SPEC = importlib.util.spec_from_file_location("pixel_agent", MODULE_PATH)
pixel_agent = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = pixel_agent
SPEC.loader.exec_module(pixel_agent)


class PixelAgentHelpersTest(unittest.TestCase):
    def test_png_dimensions(self):
        png = (
            b"\x89PNG\r\n\x1a\n"
            + b"\x00\x00\x00\x0dIHDR"
            + (1080).to_bytes(4, "big")
            + (2400).to_bytes(4, "big")
        )
        self.assertEqual((1080, 2400), pixel_agent.png_dimensions(png))

    def test_denormalize_clamps(self):
        self.assertEqual(0, pixel_agent.denormalize(-1, 1080))
        self.assertEqual(540, pixel_agent.denormalize(500, 1080))
        self.assertEqual(1079, pixel_agent.denormalize(1000, 1080))

    def test_child_environment_removes_secrets(self):
        original = pixel_agent.os.environ.copy()
        try:
            pixel_agent.os.environ["GEMINI_API_KEY"] = "secret"
            pixel_agent.os.environ["PATH"] = "/bin"
            env = pixel_agent.child_env()
            self.assertNotIn("GEMINI_API_KEY", env)
            self.assertEqual("/bin", env["PATH"])
        finally:
            pixel_agent.os.environ.clear()
            pixel_agent.os.environ.update(original)

    def test_extract_text(self):
        interaction = {
            "steps": [
                {"type": "model_output", "content": [{"type": "text", "text": "done"}]}
            ]
        }
        self.assertEqual("done", pixel_agent.extract_text(interaction))

    def test_safety_confirmation(self):
        decision, explanation = pixel_agent.safety_status(
            {"safety_decision": {"decision": "require_confirmation", "explanation": "send"}}
        )
        self.assertEqual("require_confirmation", decision)
        self.assertEqual("send", explanation)

    def test_safety_acknowledgement_uses_reference_wire_format(self):
        response = pixel_agent.build_function_response(
            "run_terminal", "call-1", {"exit_code": 0}, b"png", acknowledged=True
        )
        result = pixel_agent.json.loads(response["result"][0]["text"])
        self.assertEqual("true", result["safety_acknowledgement"])

    def test_dedicated_phone_disables_low_consequence_confirmations(self):
        computer_use = pixel_agent.interaction_tools()[0]
        self.assertEqual(
            ["communication_tool", "data_modification"],
            computer_use["disabled_safety_policies"],
        )

    def test_rest_client_keeps_key_out_of_request_body(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"id":"interaction-1","steps":[]}'

        with mock.patch.object(pixel_agent.urllib.request, "urlopen", return_value=FakeResponse()) as send:
            result = pixel_agent.GeminiClient("test-secret-key").create(
                {"model": "gemini-3.7-flash", "input": "hello"}
            )
        request = send.call_args.args[0]
        self.assertEqual("interaction-1", result["id"])
        self.assertEqual("test-secret-key", request.get_header("X-goog-api-key"))
        self.assertNotIn(b"test-secret-key", request.data)


class FakeBridge:
    def __init__(self):
        self.commands = []

    def run(self, command, privileged=False, timeout=60):
        self.commands.append((command, privileged, timeout))
        return pixel_agent.CommandResult(command, 0, "", "", "fake")

    def set_clipboard(self, text):
        self.clipboard = text
        return True

    def open_app(self, requested):
        return {"package": requested}

    def list_apps(self):
        return "com.example/.Main"


class MobileControllerTest(unittest.TestCase):
    def setUp(self):
        self.log_patch = mock.patch.object(pixel_agent, "log_event")
        self.log_patch.start()

    def tearDown(self):
        self.log_patch.stop()

    def test_click_scales_coordinates(self):
        bridge = FakeBridge()
        controller = pixel_agent.MobileController(bridge)
        controller.execute("click", {"x": 500, "y": 250}, 1080, 2400)
        self.assertEqual("input tap 540 600", bridge.commands[-1][0])

    def test_type_uses_clipboard_for_unicode(self):
        bridge = FakeBridge()
        controller = pixel_agent.MobileController(bridge)
        result = controller.execute("type", {"text": "hello ☃"}, 1080, 2400)
        self.assertEqual("hello ☃", bridge.clipboard)
        self.assertEqual("input keyevent KEYCODE_PASTE", bridge.commands[-1][0])
        self.assertEqual("clipboard-paste", result["input_method"])


if __name__ == "__main__":
    unittest.main()
