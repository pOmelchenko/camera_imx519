"""Prepare the IMX519 and AK7375 modules for the running Q6A kernel."""
from pathlib import Path
import hashlib
import shutil
import subprocess
from urllib.request import urlopen

REVISION = "42d9bb9081f1c55e11abb5cbf4d7bede01d7bdde"
SOURCE = f"https://raw.githubusercontent.com/raspberrypi/linux/{REVISION}/drivers/media/i2c"
DIGESTS = {
    "imx519": "687afa60dd4f7eabc428ff5ea60a50ab7f3501a798f52a80167739d1b191d0fe",
    "ak7375": "00bbe54d59367ccb33c1e281a4bf19edacf47203ab0c664f0c2c1f535a89202c",
}

CAM3_VERSION = "q6a-cam3.1"
CAM3_PATCH = Path(__file__).parent / "patches/imx519-linux-7.patch"

MODULES = ("i2c-qcom-cci", *DIGESTS, "qcom_camss")


def read_source(name, cache):
    filename = name + ".c"
    if (cache / filename).is_file():
        data = (cache / filename).read_bytes()
    else:
        with urlopen(f"{SOURCE}/{filename}", timeout=30) as response:
            data = response.read()
    if hashlib.sha256(data).hexdigest() != DIGESTS[name]:
        raise ValueError(f"Неверная контрольная сумма {filename}.")
    return data


def module_field(kernel, field, module):
    result = subprocess.run(["modinfo", "-k", kernel, "-F", field, str(module)],
                            capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def prepare_modules(kernel, work, atomic_write, modules_dir=Path("/lib/modules"),
                    *, cam3=False, loaded=Path("/sys/module/imx519")):
    tree = modules_dir / kernel
    updates = tree / "updates"
    missing = [name for name in DIGESTS if subprocess.run(
        ["modinfo", "-k", kernel, name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode]
    # A previous run may have finished writing a .ko just before depmod.
    build = [name for name in missing if not (updates / (name + ".ko")).is_file()]
    indexed = False
    if cam3 and module_field(kernel, "version", "imx519") != CAM3_VERSION:
        if module_field(kernel, "filename", "imx519") == "(builtin)":
            raise ValueError("IMX519 встроен в ядро. Для CAM3 требуется ядро с исправлениями IMX519.")
        indexed = True
        pending = updates / "imx519.ko"
        if not pending.is_file() or module_field(kernel, "version", pending) != CAM3_VERSION:
            if "imx519" not in build:
                build.append("imx519")
    if build:
        headers = tree / "build"
        packages = []
        if not all(shutil.which(tool) for tool in ("gcc", "ld", "make")):
            packages.append("build-essential")
        if cam3 and "imx519" in build and not shutil.which("patch"):
            packages.append("patch")
        if not (headers / "Makefile").is_file():
            packages.append("linux-headers-" + kernel)
        if packages:
            subprocess.run(["apt-get", "install", "-y", "--no-install-recommends", "--no-remove",
                            *packages], check=True)
        src = work / "driver"
        src.mkdir()
        for name in build:
            (src / (name + ".c")).write_bytes(read_source(name, Path(__file__).parent / "vendor"))
        if cam3 and "imx519" in build:
            subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", CAM3_PATCH], cwd=src, check=True)
            with (src / "imx519.c").open("a") as source:
                source.write(f'\nMODULE_VERSION("{CAM3_VERSION}");\n')
        (src / "Kbuild").write_text("obj-m += " + " ".join(n + ".o" for n in build) + "\n")
        subprocess.run(["make", "-C", headers, f"M={src}", "modules"], check=True)
        updates.mkdir(exist_ok=True)
        for name in build:
            dst = updates / (name + ".ko")
            if name == "imx519" and cam3 and dst.is_file():
                backup = dst.with_suffix(".ko.before-q6a-cam3")
                if not backup.exists():
                    atomic_write(backup, dst.read_bytes())
            atomic_write(dst, (src / (name + ".ko")).read_bytes())
    if missing or indexed:
        subprocess.run(["depmod", "-a", kernel], check=True)
    if cam3 and module_field(kernel, "version", "imx519") != CAM3_VERSION:
        raise ValueError("depmod не выбрал модуль IMX519 для CAM3. Проверьте modinfo -n imx519.")
    for module in MODULES:
        subprocess.run(["modprobe", module], check=True)
    if cam3 and loaded.is_dir():
        version = loaded / "version"
        return not version.is_file() or version.read_text().strip() != CAM3_VERSION
    return False
