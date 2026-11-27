"""Safety tests for czplatform.host — the uConsole GPIO assumptions must never
reach real GPIOs on the CardputerZero (see the table in host.py)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from czplatform import host                              # noqa: E402


class AioInertTest(unittest.TestCase):
    def setUp(self):
        host.make_aio_inert()
        from watchdogs import aio_manager
        self.aio = aio_manager

    def test_nothing_ever_spawns_pinctrl(self):
        boom = mock.Mock(side_effect=AssertionError("a subprocess was started"))
        with mock.patch.object(self.aio.subprocess, "run", boom), \
                mock.patch.object(self.aio.subprocess, "Popen", boom):
            self.assertFalse(self.aio.AioManager.is_installed())
            self.assertIsNone(self.aio.AioManager.get_status())
            for feature in self.aio.FEATURES:
                self.assertFalse(self.aio.AioManager.toggle(feature, True))
                self.assertFalse(self.aio.AioManager.toggle(feature, False))
            self.assertFalse(self.aio._pinctrl_set(27, True))
            self.assertFalse(self.aio._pinctrl_get(27))
        boom.assert_not_called()

    def test_install_is_refused_with_a_message(self):
        messages = []
        self.aio.AioManager.install(lambda text, kind: messages.append((text, kind)))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0][1], "error")


class LoraPinsTest(unittest.TestCase):
    def test_constants_point_at_the_cap(self):
        host.point_lora_at_the_cap()
        from watchdogs import lora_manager as lm
        self.assertEqual((lm.SPI_BUS, lm.SPI_CS), (0, 1))
        self.assertEqual((lm.PIN_RESET, lm.PIN_BUSY, lm.PIN_IRQ), (26, 22, 23))

    def test_none_of_the_pins_is_a_display_or_keyboard_line(self):
        # G24/G25 = display enable/dc, G27 = keyboard interrupt, G7/G8 = SPI CS,
        # G9-G11 = SPI0 bus, G14/G15 = UART (GPS), G2/G3 = I2C
        forbidden = {24, 25, 27, 7, 8, 9, 10, 11, 14, 15, 2, 3}
        self.assertFalse(forbidden & {host.LORA_PIN_RESET, host.LORA_PIN_BUSY,
                                      host.LORA_PIN_IRQ})


class EnvironmentTest(unittest.TestCase):
    def test_gps_defaults_without_overriding_the_user(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            host.prepare_environment()
            self.assertEqual(os.environ["WDG_GPS_DEVICE"], "/dev/ttyS0")
            self.assertEqual(os.environ["WDG_GPS_BAUD"], "115200")
        with mock.patch.dict(os.environ, {"WDG_GPS_DEVICE": "/dev/ttyUSB0"},
                             clear=True):
            host.prepare_environment()
            self.assertEqual(os.environ["WDG_GPS_DEVICE"], "/dev/ttyUSB0")


class CapRailTest(unittest.TestCase):
    def make_rail(self, brightness="0"):
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        Path(d, "brightness").write_text(brightness)
        Path(d, "max_brightness").write_text("1")
        return d

    def test_on_then_restore(self):
        d = self.make_rail("0")
        rail = host.CapRail(d)
        self.assertTrue(rail.available())
        self.assertTrue(rail.on())
        self.assertEqual(Path(d, "brightness").read_text(), "1")
        rail.restore()
        self.assertEqual(Path(d, "brightness").read_text(), "0")

    def test_an_already_on_rail_stays_on(self):
        d = self.make_rail("1")
        rail = host.CapRail(d)
        rail.on()
        rail.restore()
        self.assertEqual(Path(d, "brightness").read_text(), "1")

    def test_missing_rail_is_not_an_error(self):
        rail = host.CapRail("/nonexistent/leds/ext_5v_out")
        self.assertFalse(rail.available())
        self.assertFalse(rail.on())
        rail.restore()                                  # no-op


class RedirectUserStateTest(unittest.TestCase):
    """A `.deb` install's /usr/share/APPLaunch/apps/<pkg>/ is read-only, so
    secrets.conf/plugin state must not depend on being writable there."""

    def setUp(self):
        self.state_dir = Path(tempfile.mkdtemp()) / "dotwatchdogs"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.state_dir.parent, ignore_errors=True)

    def test_creates_the_state_dir_and_seeds_from_the_example(self):
        host.redirect_user_state(self.state_dir)
        secrets_path = self.state_dir / "secrets.conf"
        self.assertTrue(secrets_path.is_file())
        example = Path(__file__).resolve().parent.parent / "secrets.conf.example"
        self.assertEqual(secrets_path.read_text(), example.read_text())

    def test_stadia_key_is_read_from_the_redirected_path(self):
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "secrets.conf").write_text("STADIA_API_KEY=abc123\n")
        host.redirect_user_state(self.state_dir)
        from watchdogs import tile_manager
        self.assertEqual(tile_manager._load_stadia_key(), "abc123")

    def test_wardrive_state_and_secret_writes_land_in_the_state_dir(self):
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "secrets.conf").write_text("")  # skip the example seed
        host.redirect_user_state(self.state_dir)
        from plugins import wardrive_upload

        class _Fake(wardrive_upload.WardriveUpload):
            def __init__(self):
                pass

        plugin = _Fake()
        self.assertEqual(plugin._state_file(), self.state_dir / "wardrive_state.json")

        plugin._save_secret("WARDRIVE_API_KEY", "deadbeef")
        content = (self.state_dir / "secrets.conf").read_text()
        self.assertIn("WARDRIVE_API_KEY=deadbeef", content)

        # a second save of the same key replaces the line, it doesn't duplicate it
        plugin._save_secret("WARDRIVE_API_KEY", "cafef00d")
        content = (self.state_dir / "secrets.conf").read_text()
        self.assertEqual(content.count("WARDRIVE_API_KEY="), 1)
        self.assertIn("WARDRIVE_API_KEY=cafef00d", content)

    def test_config_module_constants_reread_from_the_redirected_path(self):
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "secrets.conf").write_text("WDG_WPASEC_KEY=sekret\n")
        host.redirect_user_state(self.state_dir)
        from watchdogs import config
        self.assertEqual(config.WPASEC_KEY, "sekret")


if __name__ == "__main__":
    unittest.main()


class EnsureWorkingRpiGpioTests(unittest.TestCase):
    def test_broken_rpi_gpio_becomes_clean_import_error(self):
        import sys, tempfile, os, importlib
        from czplatform import host
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "RPi", "GPIO"))
        open(os.path.join(d, "RPi", "__init__.py"), "w").close()
        with open(os.path.join(d, "RPi", "GPIO", "__init__.py"), "w") as f:
            f.write("raise Exception('Could not determine Jetson model')\n")
        saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] == "RPi"}
        for k in saved:
            del sys.modules[k]
        sys.path.insert(0, d)
        old_dist = host._SYSTEM_DIST
        host._SYSTEM_DIST = "/nonexistent"
        try:
            self.assertFalse(host.ensure_working_rpi_gpio())
            with self.assertRaises(ImportError):
                import RPi.GPIO  # noqa: F401
        finally:
            host._SYSTEM_DIST = old_dist
            sys.path.remove(d)
            for k in [m for m in sys.modules if m.split(".")[0] == "RPi"]:
                del sys.modules[k]
            sys.modules.update(saved)
