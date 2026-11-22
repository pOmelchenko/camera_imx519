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


def prepare_modules(kernel, work, atomic_write, modules_dir=Path("/lib/modules")):
    tree = modules_dir / kernel
    updates = tree / "updates"
    missing = [name for name in DIGESTS if subprocess.run(
        ["modinfo", "-k", kernel, name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode]
    # A previous run may have finished writing a .ko just before depmod.
    build = [name for name in missing if not (updates / (name + ".ko")).is_file()]
    if build:
        headers = tree / "build"
        packages = []
        if not all(shutil.which(tool) for tool in ("gcc", "ld", "make")):
            packages.append("build-essential")
        if not (headers / "Makefile").is_file():
            packages.append("linux-headers-" + kernel)
        if packages:
            subprocess.run(["apt-get", "install", "-y", "--no-install-recommends", "--no-remove",
                            *packages], check=True)
        src = work / "driver"
        src.mkdir()
        for name in build:
            (src / (name + ".c")).write_bytes(read_source(name, Path(__file__).parent / "vendor"))
        (src / "Kbuild").write_text("obj-m += " + " ".join(n + ".o" for n in build) + "\n")
        subprocess.run(["make", "-C", headers, f"M={src}", "modules"], check=True)
        updates.mkdir(exist_ok=True)
        for name in build:
            atomic_write(updates / (name + ".ko"), (src / (name + ".ko")).read_bytes())
    if missing:
        subprocess.run(["depmod", "-a", kernel], check=True)
    for module in MODULES:
        subprocess.run(["modprobe", module], check=True)
