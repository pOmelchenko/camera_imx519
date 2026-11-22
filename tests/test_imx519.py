"""Regression coverage for selecting among the three physical Q6A CSI ports."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "target/sbc/radxa_dragon_q6a"
# Physical routing of the three Q6A connectors.
ROUTES = (("cam1", "cci0_i2c0", 0, 36), ("cam2", "cci1_i2c0", 2, 77),
          ("cam3", "cci1_i2c1", 3, 78))


def load_script(name):
    spec = importlib.util.spec_from_file_location("imx519_" + name, TOOLS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, "path", [str(TOOLS), *sys.path]):
        spec.loader.exec_module(module)
    return module


class CameraPortsTest(unittest.TestCase):
    def test_color_preview_uses_negotiated_bayer_order_and_skips_padding(self):
        import io
        frame = bytes([10, 30, 50, 70, 255, 99, 5, 20, 25, 60, 255, 98])
        expected = {"RGGB": [10, 17, 20, 50, 47, 60], "GRBG": [30, 15, 5, 70, 55, 25],
                    "GBRG": [5, 15, 30, 25, 55, 70], "BGGR": [20, 17, 10, 60, 47, 50]}
        for order, pixels in expected.items():
            with self.subTest(order=order):
                out = io.BytesIO()
                load_script("capture").write_preview(out, frame, 4, 2, 6, order)
                self.assertEqual(out.getvalue(), b"P6\n2 1\n255\n" + bytes(pixels))

    def test_capture_records_the_format_negotiated_on_the_sensor(self):
        import json
        capture = load_script("capture")
        ctl = ["media-ctl", "-d", "/dev/media0"]
        with tempfile.TemporaryDirectory() as tmp:
            def output(cmd, **kwargs):
                if "--get-v4l2" in cmd:
                    return "[stream:0 fmt:SGBRG10_1X10/4x2 field:none]"
                if cmd == [*ctl, "-e", "imx519 22-001a"]:
                    return "/dev/v4l-subdev28"
                if cmd == ["v4l2-ctl", "-d", "/dev/v4l-subdev28", "--get-ctrl=exposure,analogue_gain,digital_gain"]:
                    return "exposure: 3000\nanalogue_gain: 768\ndigital_gain: 256"
                if "-e" in cmd:
                    return "/dev/video42"
                return "Pixel Format : 'pGAA'\nWidth/Height : 4/2\nBytes per Line : 6\nSize Image : 12"
            def run(*args, **kwargs):
                if "--stream-count=1" in args:
                    (Path(tmp) / "frame.raw").write_bytes(bytes(range(12)))
            with patch.object(capture, "mkdtemp", return_value=tmp), patch.object(capture, "run", side_effect=run) as calls, \
                    patch.object(subprocess, "check_output", side_effect=output):
                capture.capture_frame(ctl, "imx519 22-001a", "msm_csiphy3", "msm_csid0",
                                      "msm_vfe0_rdi0", "msm_vfe0_video0", "4x2", 500)
            calls.assert_any_call("v4l2-ctl", "-d", "/dev/video42", "--set-fmt-video=width=4,height=2,pixelformat=pGAA")
            meta = json.loads((Path(tmp) / "frame.json").read_text())
            self.assertEqual((meta["fourcc"], meta["stride"], meta["sizeimage"]), ("pGAA", 6, 12))
            self.assertEqual(meta["v4l2_controls"], {"exposure": 3000, "analogue_gain": 768, "digital_gain": 256})
            self.assertTrue((Path(tmp) / "preview.ppm").read_bytes().startswith(b"P6\n2 1\n255\n"))

    def test_unavailable_controls_are_explicitly_unknown(self):
        capture = load_script("capture")
        with patch.object(subprocess, "check_output", side_effect=subprocess.CalledProcessError(1, "v4l2-ctl")):
            self.assertIsNone(capture.read_sensor_controls(["media-ctl", "-d", "/dev/media0"], "imx519 20-001a"))

    def test_manual_focus_keeps_selected_lens_open_during_capture(self):
        from unittest.mock import mock_open
        capture = load_script("capture")
        ctl = ["media-ctl", "-d", "/dev/media2"]
        handle = mock_open()
        with patch.object(subprocess, "check_output", return_value="/dev/v4l-subdev6\n") as entity, \
                patch.object(subprocess, "run") as run, patch("builtins.open", handle):
            with capture.lens_position(ctl, "imx519 22-001a", 500):
                handle().__exit__.assert_not_called()
                run.assert_called_once_with(("v4l2-ctl", "-d", "/dev/v4l-subdev6",
                                             "--set-ctrl=focus_absolute=500"), check=True)
            entity.assert_called_once_with([*ctl, "-e", "ak7375 22-000c"], text=True)
            handle().__exit__.assert_called_once()

    def test_detected_but_unlinked_sensor(self):
        capture = load_script("capture")
        graph = "- entity 422: imx519 16-001a (1 pad, 0 link, 0 routes)\n  pad0: Source\n"
        with patch.object(Path, "glob", return_value=[Path("/dev/media0")]), \
                patch.object(subprocess, "check_output", return_value=graph), \
                self.assertRaisesRegex(ValueError, r"imx519 16-001a \(1 pad, 0 link"):
            capture.find_camera("cam1", "msm_csiphy0")

    def test_find_same_model_by_physical_port(self):
        capture = load_script("capture")
        graph = "".join(f'- entity {n}: imx519 {n}-001a (1 pad, 1 link)\n'
                        f'  pad0: Source\n   -> "msm_csiphy{phy}":0 [ENABLED,IMMUTABLE]\n'
                        for n, (_, _, phy, _) in enumerate(ROUTES))
        media = Path("/dev/media7")
        with patch.object(Path, "glob", return_value=[media]), patch.object(subprocess, "check_output", return_value=graph):
            for n, (port, _, phy, _) in enumerate(ROUTES):
                self.assertEqual(capture.find_camera(port, f"msm_csiphy{phy}"), (media, f"imx519 {n}-001a"))

    def test_route_preserves_other_sensor(self):
        capture = load_script("capture")
        graph = """- entity 1: imx519 16-001a (1 pad, 1 link, 0 routes)
          pad0: Source
            -> "msm_csiphy0":0 [ENABLED,IMMUTABLE]
        - entity 2: msm_csiphy0 (2 pads)
          pad1: Source
            -> "msm_csid0":0 []
            -> "msm_csid1":0 []
        - entity 3: msm_csiphy2 (2 pads)
          pad1: Source
            -> "msm_csid0":0 [ENABLED]
            -> "msm_csid1":0 []
        - entity 4: msm_csid0 (5 pads)
          pad1: Source
            -> "msm_vfe0_rdi0":0 [ENABLED]
            -> "msm_vfe1_rdi0":0 []
        - entity 5: msm_csid1 (5 pads)
          pad1: Source
            -> "msm_vfe0_rdi0":0 []
            -> "msm_vfe1_rdi0":0 []
        - entity 6: msm_vfe0_rdi0 (2 pads)
          pad1: Source
            -> "msm_vfe0_video0":0 [ENABLED,IMMUTABLE]
        - entity 7: msm_vfe1_rdi0 (2 pads)
          pad1: Source
            -> "msm_vfe1_video0":0 [ENABLED,IMMUTABLE]"""
        def route(g):
            return capture.select_route(g, "imx519 16-001a", "msm_csiphy0")
        self.assertEqual(route(graph)[2], "msm_vfe1_video0")
        self.assertEqual(route(graph.replace("[ENABLED]", "[]"))[2], "msm_vfe0_video0")
        busy = graph.replace('-> "msm_vfe1_rdi0":0 []', '-> "msm_vfe1_rdi0":0 [ENABLED]', 1)
        with self.assertRaisesRegex(ValueError, "Нет свободного маршрута"):
            route(busy)

    @unittest.skipIf(sys.platform == "win32", "flock is used on the Linux target")
    def test_capture_releases_only_its_new_links_on_success_and_failure(self):
        capture = load_script("capture")
        graph = """- entity 1: imx519 16-001a (1 pad)
          pad0: Source
            -> "msm_csiphy0":0 [ENABLED,IMMUTABLE]
        - entity 2: msm_csiphy0 (2 pads)
          pad1: Source
            -> "msm_csid0":0 [ENABLED]
        - entity 3: msm_csid0 (5 pads)
          pad1: Source
            -> "msm_vfe0_rdi0":0 []
        - entity 4: msm_vfe0_rdi0 (2 pads)
          pad1: Source
            -> "msm_vfe0_video0":0 [ENABLED,IMMUTABLE]"""
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "media0"
            media.touch()
            for error in (None, OSError("stream failed")):
                with patch.object(capture, "find_camera", return_value=(media, "imx519 16-001a")), \
                        patch.object(subprocess, "check_output", return_value=graph), \
                        patch.object(subprocess, "run") as update, \
                        patch.object(capture, "capture_frame", side_effect=error), patch.dict("os.environ"):
                    update.return_value.returncode = 0
                    if error:
                        with self.assertRaises(OSError):
                            capture.capture("cam1")
                    else:
                        capture.capture("cam1")
                    route = '"msm_csid0":1 -> "msm_vfe0_rdi0":0'
                    self.assertEqual([call.args[0][-1] for call in update.call_args_list],
                                     [route + " [1]", route + " [0]"])


@unittest.skipUnless(all(shutil.which(c) for c in ("fdtput", "dtc", "fdtget", "fdtoverlay")),
                     "Device Tree command-line tools required")
class InstallerTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.installer = load_script("install")
        self.esp = self.root / "efi"
        self.images = self.esp / "RadxaOS/test-kernel"
        self.catalog = self.images / "dtbo"
        self.catalog.mkdir(parents=True)
        entries = self.esp / "loader/entries"
        entries.mkdir(parents=True)
        self.stock = entries / "RadxaOS-test-kernel.conf"
        self.original = ("title Ubuntu\nlinux /RadxaOS/test-kernel/linux\ninitrd /RadxaOS/test-kernel/initrd\n"
                         "options quiet root=UUID=test\ndevicetree /RadxaOS/test-kernel/board.dtb\n")
        self.stock.write_text(self.original)
        self.loader = self.esp / "loader/loader.conf"
        self.loader.write_text("# keep\ntimeout 3\ndefault RadxaOS-test-kernel.conf\n")
        binary = self.esp / "EFI/BOOT/BOOTAA64.EFI"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"#### LoaderInfo: systemd 999.0.7 (embloader 0.7.r1.f3a03df) ####")
        (self.images / "linux").touch()
        self.modules = self.root / "q6a-imx519.conf"
        self.compile(self.images / "board.dtb", """/dts-v1/;
            / { compatible = "radxa,dragon-q6a";
                reserved-memory { #address-cells = <2>; #size-cells = <2>; ranges; };
                tlmm: gpio { gpio-controller; #gpio-cells = <2>; };
                vreg_l10c_0p88: supply1 {}; vreg_l6b_1p2: supply2 {};
                cci0: cci0 { cci0_i2c0: bus0 {}; };
                cci1: cci1 { cci1_i2c0: bus0 {}; cci1_i2c1: bus1 {}; };
                camss: isp { ports { #address-cells = <1>; #size-cells = <0>;
                    port@0 { reg = <0>; }; port@2 { reg = <2>; }; port@3 { reg = <3>; };
                }; };
            };""")

    def compile(self, target, source):
        src = self.root / "test.dts"
        src.write_text(source)
        subprocess.run(["dtc", "-q", "-@", "-o", target, src], check=True)

    def install(self, port="cam1", devices=None, replace=False):
        return self.installer.install(self.esp, "RadxaOS", "test-kernel", self.root, port,
                                      self.modules, devices or {}, replace=replace)

    def overlay(self, name, fragment):
        target = self.catalog / (name + ".dtbo")
        self.compile(target, "/dts-v1/; /plugin/;\n" + fragment)
        return "/" + target.relative_to(self.esp).as_posix()

    def test_fresh_install_all_ports_on_one_existing_entry(self):
        get = self.installer.output
        for port, bus, phy, gpio in ROUTES:
            entry, changed = self.install(port)
            self.assertEqual((entry, changed), (self.stock, True))
            paths = self.installer.fields(entry.read_text().splitlines(), "devicetree-overlay")[0]
            merged = self.root / "boot.dtb"
            subprocess.run(["fdtoverlay", "-i", self.images / "board.dtb", "-o", merged,
                            *(self.esp / p[1:] for p in paths)], check=True)
            node = get("fdtget", merged, "/__symbols__", bus) + "/imx519@1a"
            lens = node.rsplit("/", 1)[0] + "/ak7375@c"
            self.assertEqual(get("fdtget", merged, lens, "compatible"), "asahi-kasei,ak7375")
            self.assertEqual(get("fdtget", merged, node, "lens-focus"), get("fdtget", merged, lens, "phandle"))
            rx = f"/isp/ports/port@{phy}/endpoint"
            self.assertEqual(get("fdtget", merged, rx, "remote-endpoint"),
                             get("fdtget", merged, node + "/port/endpoint", "phandle"))
            self.assertEqual(get("fdtget", "-t", "u", merged, f"/imx519-{port}-enable", "gpios").split()[1],
                             str(gpio))
            self.assertEqual(sorted(entry.parent.glob("*.conf")), [entry])
            self.assertEqual(self.install(port)[1], False)
        self.assertEqual(self.loader.read_text(), "# keep\ntimeout 3\ndefault RadxaOS-test-kernel\n")
        self.assertEqual(self.stock.with_suffix(".conf.before-imx519").read_text(), self.original)

    def test_already_working_board_and_previous_rsetup_files(self):
        self.loader.write_text("timeout 3\ndefault RadxaOS-test-kernel\n")
        camera = self.installer.build_overlay(self.root, "cam1")
        shutil.copyfile(camera, self.catalog / camera.name)
        self.stock.write_text(self.original + f"devicetree-overlay /RadxaOS/test-kernel/dtbo/{camera.name}\n")
        other = self.catalog / "imx519-cam2.dtbo.disabled"
        other.write_bytes(b"existing custom profile")
        before = {p: p.read_bytes() for p in (self.stock, self.loader, other)}
        self.assertFalse(self.install()[1])
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertFalse(self.stock.with_suffix(".conf.before-imx519").exists())
        self.assertIn("qcom_camss", self.modules.read_text().splitlines())

    def test_old_manual_install_with_duplicate_defaults(self):
        self.loader.write_text(f"default {self.stock.name}\ntimeout 3\ndefault {self.stock.stem}\n")
        self.install()
        self.assertEqual(self.loader.read_text(), f"default {self.stock.stem}\ntimeout 3\n")

    def test_missing_unused_phy_node_can_be_added_by_camera_overlay(self):
        subprocess.run(["fdtput", "-r", self.images / "board.dtb", "/isp/ports/port@2"], check=True)
        self.install("cam1")
        self.assertTrue(self.install("cam2")[1])

    def test_driver_failure_keeps_efi_and_module_list(self):
        before = self.snapshot()
        def broken_driver():
            raise OSError("driver build failed")
        with self.assertRaisesRegex(OSError, "driver build failed"):
            self.installer.install(self.esp, "RadxaOS", "test-kernel", self.root, "cam2",
                                   self.modules, {}, prepare_driver=broken_driver)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.modules.exists())

    def test_build_only_missing_driver_and_retry_after_interrupted_depmod(self):
        drivers = load_script("drivers")
        kernel = "test-kernel"
        modules = self.root / "modules"
        headers = modules / kernel / "build"
        headers.mkdir(parents=True)
        (headers / "Makefile").touch()
        commands = []
        def run(cmd, **kwargs):
            commands.append(cmd)
            if cmd[0] == "make":
                self.assertEqual(cmd[2], headers)
                src = self.root / "driver"
                self.assertEqual((src / "Kbuild").read_text(), "obj-m += ak7375.o\n")
                (src / "ak7375.ko").write_bytes(b"test module")
            return subprocess.CompletedProcess(cmd, int(cmd[0] == "modinfo" and cmd[-1] == "ak7375"))
        with patch.object(subprocess, "run", side_effect=run), patch.object(drivers, "read_source", return_value=b""):
            for _ in range(2):
                drivers.prepare_modules(kernel, self.root, self.installer.atomic_write, modules)
            self.assertEqual((modules / kernel / "updates/ak7375.ko").read_bytes(), b"test module")
            self.assertEqual(sum(c[0] == "make" for c in commands), 1)
            self.assertEqual(sum(c[0] == "depmod" for c in commands), 2)

    def test_cam3_migrates_only_selected_entry_and_preserves_cam2_clock(self):
        self.check_cam3_migration("cam3")

    def test_cam3_migrates_previous_400khz_package(self):
        self.check_cam3_migration("cam3-400khz")

    def check_cam3_migration(self, source):
        old = self.installer.build_overlay(self.root, source)
        shutil.copyfile(old, self.catalog / old.name)
        clock = self.overlay("cam2-clock", '&cci1_i2c0 { clock-frequency = <1000000>; };')
        self.stock.write_text(self.original + f"devicetree-overlay {clock} /RadxaOS/test-kernel/dtbo/{old.name}\n")
        saved = self.stock.with_name("rollback.conf")
        saved.write_bytes(self.stock.read_bytes())
        self.assertTrue(self.install("cam3")[1])
        profile = "/RadxaOS/test-kernel/dtbo/imx519-cam3-100khz.dtbo"
        self.assertIn(profile, self.stock.read_text())
        self.assertNotIn(profile, saved.read_text())
        self.assertEqual(old.read_bytes(), (self.catalog / old.name).read_bytes())
        get = self.installer.get
        self.assertEqual(get(self.root / "camera.dtb", "/cci1/bus1", "clock-frequency", "u"), "100000")
        self.assertEqual(get(self.root / "camera.dtb", "/cci1/bus0", "clock-frequency", "u"), "1000000")
        self.assertEqual(get(self.root / "camera.dtb", "/imx519-cam3-enable", "startup-delay-us", "u"), "100000")
        self.assertFalse(self.install("cam3")[1])

    def test_cam3_changes_only_bus_clock_in_a_custom_camera_profile(self):
        stock = self.installer.build_overlay(self.root, "cam3-400khz")
        legacy = self.catalog / "imx519-cam3.dtbo"
        shutil.copyfile(stock, legacy)
        paths = self.installer.overlay_paths(legacy, self.images / "board.dtb")
        regulator = paths["/imx519-cam3-enable"][0]
        subprocess.run(["fdtput", legacy, regulator, "regulator-always-on"], check=True)
        backup = legacy.read_bytes()
        self.stock.write_text(self.original + f"devicetree-overlay /RadxaOS/test-kernel/dtbo/{legacy.name}\n")
        rollback = self.stock.with_name("cam3-original.conf")
        rollback.write_bytes(self.stock.read_bytes())
        self.assertTrue(self.install("cam3")[1])
        self.assertEqual(legacy.read_bytes(), backup)
        self.assertIn(legacy.name, rollback.read_text())
        self.assertNotIn(legacy.name, self.stock.read_text())
        self.assertEqual(self.installer.get(self.root / "camera.dtb", "/imx519-cam3-enable", "regulator-always-on", "bx"), "")
        self.assertEqual(self.installer.get(self.root / "camera.dtb", "/cci1/bus1", "clock-frequency", "u"), "100000")
        self.assertFalse(self.install("cam3")[1])

    def test_cam3_refuses_to_retime_unrelated_i2c_device(self):
        eeprom = self.overlay("cam3-eeprom", '&cci1_i2c1 { eeprom@50 { reg = <0x50>; }; };')
        self.stock.write_text(self.original + f"devicetree-overlay {eeprom}\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "устройств"):
            self.install("cam3")
        self.assertEqual(self.snapshot(), before)

    def test_cam3_driver_upgrade_backup_and_retry(self):
        drivers = load_script("drivers")
        modules = self.root / "modules"
        updates = modules / "test-kernel/updates"
        headers = updates.parent / "build"
        headers.mkdir(parents=True)
        (headers / "Makefile").touch()
        updates.mkdir()
        old = updates / "imx519.ko"
        old.write_bytes(b"old driver")
        loaded = self.root / "loaded"
        loaded.mkdir()
        index = {"version": ""}
        calls = []
        def field(kernel, key, name):
            if key == "filename":
                return str(old)
            if isinstance(name, Path):
                return drivers.CAM3_VERSION if name.read_bytes() == b"fixed driver" else ""
            return index["version"]
        def run(cmd, **options):
            calls.append(cmd[0])
            if cmd[0] == "patch":
                self.assertTrue(Path(cmd[-1]).is_file())
            if cmd[0] == "make":
                self.assertIn(drivers.CAM3_VERSION, (self.root / "driver/imx519.c").read_text())
                (self.root / "driver/imx519.ko").write_bytes(b"fixed driver")
            if cmd[0] == "depmod":
                index["version"] = drivers.CAM3_VERSION
            return subprocess.CompletedProcess(cmd, 0)
        with patch.object(drivers, "module_field", side_effect=field), patch.object(subprocess, "run", side_effect=run), \
                patch.object(drivers, "read_source", return_value=b""):
            def install():
                return drivers.prepare_modules("test-kernel", self.root, self.installer.atomic_write,
                                               modules, cam3=True, loaded=loaded)
            self.assertTrue(install())
            self.assertEqual(old.with_suffix(".ko.before-q6a-cam3").read_bytes(), b"old driver")
            # A lost depmod index is repaired without recompiling or replacing the backup.
            index["version"] = ""
            (loaded / "version").write_text(drivers.CAM3_VERSION)
            self.assertFalse(install())
            self.assertEqual(calls.count("make"), 1)
            self.assertEqual(calls.count("depmod"), 2)
            self.assertFalse(install())
            self.assertEqual(calls.count("depmod"), 2)

    def test_existing_drivers_need_no_build_or_source_download(self):
        drivers = load_script("drivers")
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            drivers.prepare_modules("test-kernel", self.root, self.installer.atomic_write, self.root / "modules")
            self.assertEqual([call.args[0][0] for call in run.call_args_list],
                             ["modinfo"] * 2 + ["modprobe"] * 4)

    def test_reject_modified_cached_driver(self):
        drivers = load_script("drivers")
        (self.root / "imx519.c").write_text("wrong source")
        with self.assertRaisesRegex(ValueError, "контрольная сумма"):
            drivers.read_source("imx519", self.root)

    def test_lens_address_conflict_does_not_change_efi(self):
        old = self.overlay("peripheral", '&cci0_i2c0 { other@0c { compatible = "vendor,chip"; reg = <12>; }; };')
        self.stock.write_text(self.original + f"devicetree-overlay {old}\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "занят"):
            self.install(replace=True)
        self.assertEqual(before, self.snapshot())

    def test_absent_default_keeps_factory_selection_policy(self):
        self.loader.unlink()
        self.install()
        self.assertFalse(self.loader.exists())
        self.stock.with_name("Q6A-other.conf").write_text(self.original)
        with self.assertRaisesRegex(ValueError, "несколько записей"):
            self.install()

    def test_user_entry_and_other_peripherals_survive_migration(self):
        btt = self.overlay("display", '&{/} { panel { compatible = "btt,panel"; }; };')
        lcd = self.overlay("lcd-power", '&{/} { power { compatible = "regulator-fixed"; }; };')
        cam2 = self.overlay("neighbor-cam2", '&cci1_i2c0 { camera@1a { compatible = "sony,imx296"; }; };')
        cam3 = self.overlay("neighbor-cam3", '&cci1_i2c1 { camera@1a { compatible = "sony,imx296"; }; };')
        custom = self.stock.with_name("Q6A-display.conf")
        original = self.original + f"devicetree-overlay {btt} {cam2} {cam3} {lcd}\n"
        custom.write_text(original)
        old_trial = custom.with_name("imx519-cam1-Q6A-display.conf")
        old_trial.write_text("# Generated by q6a imx519/install.py\n" + original)
        self.loader.write_text(f"default {custom.name}\n")
        self.modules.write_text("another_module\n")
        before = {f: f.read_bytes() for f in (self.stock, old_trial, *self.catalog.iterdir())}
        entry, changed = self.install(devices={"/panel": ["btt,panel"],
                                               "/cci1/bus0/camera@1a": ["sony,imx296"]})
        self.assertEqual((entry, changed), (custom, True))
        self.assertTrue(entry.read_text().startswith(self.original))
        paths = self.installer.fields(entry.read_text().splitlines(), "devicetree-overlay")[0]
        self.assertEqual(paths[:-1], [btt, cam2, cam3, lcd])
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertEqual(self.loader.read_text(), "default Q6A-display\n")
        self.assertTrue(self.modules.read_text().startswith("another_module\n"))
        self.assertFalse(self.install()[1])

    def test_conflicting_camera_or_missing_peripheral_aborts_before_writes(self):
        camera = self.overlay("occupied", '&camss { ports { port@0 { endpoint {}; }; }; };')
        self.stock.write_text(self.original + f"devicetree-overlay {camera}\n")
        before = {p: p.read_bytes() for p in self.esp.rglob("*") if p.is_file()}
        with self.assertRaisesRegex(ValueError, "занят"):
            self.install()
        with self.assertRaisesRegex(ValueError, "работающее устройство"):
            self.install("cam2", devices={"/old-touch": ["vendor,touch"]})
        self.assertEqual({p: p.read_bytes() for p in self.esp.rglob("*") if p.is_file()}, before)
        self.assertFalse(self.modules.exists())

    def old_camera(self, port="cam1", address="1a", extra=""):
        bus, phy = self.installer.PORTS[port]
        return self.overlay("previous-" + port, f"""
            &{bus} {{ previous@{address} {{ compatible = "sony,imx296"; reg = <0x{address}>;
                port {{ old_tx: endpoint {{ remote-endpoint = <&old_rx>; }}; }};
            }}; }};
            &camss {{ ports {{ port@{phy} {{ old_rx: endpoint {{ remote-endpoint = <&old_tx>; }}; }}; }}; }};
            {extra}""")

    def snapshot(self):
        return {p: p.read_bytes() for p in self.esp.rglob("*") if p.is_file()}

    def test_replace_on_selected_port_with_live_driver_and_shared_boot_profile(self):
        old = self.old_camera()
        btt = self.overlay("display", '&{/} { panel { compatible = "btt,panel"; }; };')
        neighbor = self.overlay("neighbor-cam2", """
            &cci1_i2c0 { camera@1a { compatible = "sony,imx296";
                port { next_tx: endpoint { remote-endpoint = <&next_rx>; }; }; }; };
            &camss { ports { port@2 { next_rx: endpoint { remote-endpoint = <&next_tx>; }; }; }; };""")
        initial = self.original + f"devicetree-overlay {btt} {old} {neighbor}\n"
        self.stock.write_text(initial)
        recovery = self.stock.with_name("recovery.conf")
        recovery.write_text(initial)
        old_bytes = (self.esp / old[1:]).read_bytes()
        devices = {"/cci0/bus0/previous@1a": ["sony,imx296"], "/panel": ["btt,panel"],
                   "/cci1/bus0/camera@1a": ["sony,imx296"]}
        with patch.object(sys.stdin, "isatty", return_value=True), patch("builtins.input", return_value="Да") as ask:
            self.assertTrue(self.install(devices=devices)[1])
            self.assertFalse(self.install(devices=devices)[1])
            ask.assert_called_once()
        new = self.installer.fields(self.stock.read_text().splitlines(), "devicetree-overlay")[0]
        self.assertEqual(new, [btt, "/RadxaOS/test-kernel/dtbo/imx519-cam1.dtbo", neighbor])
        merged = self.root / "camera.dtb"
        get = self.installer.get
        self.assertEqual(get(merged, "/isp/ports/port@2/endpoint", "remote-endpoint", "x"),
                         get(merged, "/cci1/bus0/camera@1a/port/endpoint", "phandle", "x"))
        self.assertFalse(self.installer.exists(merged, "/cci0/bus0/previous@1a"))
        self.assertFalse((self.esp / old[1:]).exists())
        self.assertEqual((self.esp / (old[1:] + ".disabled")).read_bytes(), old_bytes)
        saved = self.installer.fields(recovery.read_text().splitlines(), "devicetree-overlay")[0][1]
        self.assertEqual((self.esp / saved[1:]).read_bytes(), old_bytes)
        self.assertEqual(recovery.read_text().replace(saved, old), initial)
        self.assertEqual(self.stock.with_suffix(".conf.before-imx519").read_text(), initial)

    def test_empty_negative_eof_and_no_tty_preserve_configuration(self):
        old = self.old_camera()
        self.stock.write_text(self.original + f"devicetree-overlay {old}\n")
        before = self.snapshot()
        for answer in ("", "нет", EOFError(), KeyboardInterrupt()):
            with self.subTest(answer=answer), patch.object(sys.stdin, "isatty", return_value=True), \
                    patch("builtins.input", side_effect=[answer]), self.assertRaisesRegex(ValueError, "отменена"):
                self.install()
        with patch.object(sys.stdin, "isatty", return_value=False), patch("builtins.input") as ask, \
                self.assertRaisesRegex(ValueError, "--replace"):
            self.install()
        ask.assert_not_called()
        self.assertEqual(before, self.snapshot())
        self.assertFalse(self.modules.exists())

    def test_replace_imx296_bus_clock_only_on_dedicated_port(self):
        for shared in (True, False):
            extra = '&cci1_i2c0 { clock-frequency = <100000>; };'
            if shared:
                extra += '&cci1_i2c0 { eeprom@50 { compatible = "atmel,24c02"; }; };'
            old = self.old_camera("cam2", address="1a", extra=extra)
            self.stock.write_text(self.original + f"devicetree-overlay {old}\n")
            if shared:
                with self.assertRaisesRegex(ValueError, "Автозамена невозможна"):
                    self.install("cam2", replace=True)
            else:
                self.assertTrue(self.install("cam2", replace=True)[1])

    def test_unattended_replacement_on_cam3_same_i2c_address(self):
        old = self.old_camera("cam3", "1a")
        self.stock.write_text(self.original + f"devicetree-overlay {old}\n")
        with patch("builtins.input", side_effect=AssertionError), patch.object(sys.stdin, "isatty", return_value=False):
            self.assertTrue(self.install("cam3", replace=True)[1])
        merged = self.root / "camera.dtb"
        self.assertEqual(self.installer.get(merged, "/cci1/bus1/imx519@1a", "compatible"), "sony,imx519")
        self.assertFalse(self.installer.exists(merged, "/cci1/bus1/previous@1a"))

    def test_replace_cannot_remove_shared_peripheral_or_built_in_camera(self):
        extra = '&{/} { touch { compatible = "vendor,touch"; }; };'
        old = self.old_camera(extra=extra)
        self.stock.write_text(self.original + f"devicetree-overlay {old}\n")
        before = self.snapshot()
        with patch("builtins.input", side_effect=AssertionError), self.assertRaisesRegex(ValueError, "/touch"):
            self.install(replace=True)
        self.assertEqual(before, self.snapshot())
        merged = self.root / "embedded.dtb"
        subprocess.run(["fdtoverlay", "-i", self.images / "board.dtb", "-o", merged, self.esp / old[1:]], check=True)
        shutil.copyfile(merged, self.images / "board.dtb")
        self.stock.write_text(self.original)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "отдельному оверлею"):
            self.install(replace=True)
        self.assertEqual(before, self.snapshot())

    def test_retires_catalog_after_interruption_on_retry(self):
        old = self.old_camera()
        self.stock.write_text(self.original + f"devicetree-overlay {old}\n")
        rename = self.installer.os.replace
        def interrupted(src, dst):
            if Path(src) == self.esp / old[1:]:
                raise OSError("power loss")
            return rename(src, dst)
        with patch.object(self.installer.os, "replace", side_effect=interrupted), self.assertRaises(OSError):
            self.install(replace=True)
        self.assertTrue((self.esp / old[1:]).exists())
        with patch("builtins.input", side_effect=AssertionError):
            self.install()
        self.assertFalse((self.esp / old[1:]).exists())
        self.assertTrue((self.esp / (old[1:] + ".disabled")).is_file())

    def test_standalone_camera_cma_and_power_enable_survive_replacement(self):
        extra = """
            &{/reserved-memory} { linux,cma { compatible = "shared-dma-pool";
                size = <0 0x20000000>; reusable; linux,cma-default; }; };
            &{/} { old-power { compatible = "regulator-fixed"; regulator-always-on;
                gpios = <&tlmm 77 0>; pinctrl-0 = <&old_pin>; }; };
            &tlmm { old_pin: old-pin-state { pins = "gpio77"; function = "gpio"; }; };"""
        old = self.old_camera("cam2", extra=extra)
        self.stock.write_text(self.original + f"devicetree-overlay {old}\n")
        self.assertTrue(self.install("cam2", replace=True)[1])
        merged = self.root / "camera.dtb"
        self.assertEqual(self.installer.get(merged, "/reserved-memory/linux,cma", "size", "x"), "0 20000000")
        self.assertFalse(self.installer.exists(merged, "/old-power"))
        self.assertEqual(self.installer.get(merged, "/imx519-cam2-enable", "gpios", "u").split()[1], "77")
        self.assertFalse(self.install("cam2")[1])

    def test_rejects_new_profile_that_overwrites_neighbor_lane_configuration(self):
        other = self.old_camera("cam2")
        self.stock.write_text(self.original + f"devicetree-overlay {other}\n")
        profile = self.installer.build_overlay(self.root, "cam1")
        expanded = (self.root / "imx519-cam1.dts").read_text()
        self.compile(self.catalog / (profile.name + ".disabled"), expanded + """
            &camss { ports { port@2 { endpoint { data-lanes = <1 2 3 4>; }; }; }; };""")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "соседнего CAM2"):
            self.install(replace=True)
        self.assertEqual(before, self.snapshot())
