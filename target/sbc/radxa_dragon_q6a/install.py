#!/usr/bin/env python3
"""Установить IMX519 в существующую конфигурацию Radxa Dragon Q6A."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

from drivers import MODULES, prepare_modules
from ports import PORTS
from replacement import (check_removal, endpoints, exists, get, listing, overlay_paths,
                         preserve_cma, routes, sensor_on_port)

HERE = Path(__file__).resolve().parent
ESP = Path("/boot/efi")


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def efi_file(esp, name):
    path = PurePosixPath(name)
    if path.root != "/" or ".." in path.parts or "\\" in name:
        raise ValueError(f"Недопустимый путь EFI: {name}")
    target = esp.joinpath(*path.parts[1:])
    if not target.resolve().is_relative_to(esp.resolve()):
        raise ValueError(f"Путь вне EFI: {name}")
    return target


def dependencies():
    packages = {"device-tree-compiler": ("dtc", "fdtoverlay", "fdtget"),
                "cpp": ("cpp",), "v4l-utils": ("media-ctl", "v4l2-ctl"), "kmod": ("modinfo", "modprobe", "depmod")}
    missing = [pkg for pkg, cmds in packages.items() if not all(shutil.which(c) for c in cmds)]
    if missing:
        subprocess.run(["apt-get", "install", "-y", "--no-remove", "--no-install-recommends",
                        *missing], check=True)


def fields(lines, key):
    return [line.split()[1:] for line in lines if line.split()[:1] == [key]]


def single_path(lines, key):
    rows = fields(lines, key)
    if len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError(f"В записи загрузки ожидается один путь {key}.")
    return rows[0][0]


def atomic_write(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".imx519-", delete=False) as f:
        tmp = Path(f.name)
        try:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def build_overlay(work, port):
    source = HERE / "overlay" / f"imx519-{port}.dts"
    expanded = work / source.name
    subprocess.run(["cpp", "-nostdinc", "-undef", "-P", "-x", "assembler-with-cpp",
                    source, "-o", expanded], check=True)
    overlay = expanded.with_suffix(".dtbo")
    subprocess.run(["dtc", "-@", "-Wno-graph_child_address", "-I", "dts", "-O", "dtb",
                    "-o", overlay, expanded], check=True)
    return overlay


def read_default(esp, stock, token):
    loader = esp / "loader/loader.conf"
    lines = loader.read_bytes().decode().splitlines(keepends=True) if loader.exists() else []
    rows = fields(lines, "default")
    if not rows:
        normal = re.compile(re.escape(token) + r"-\d[\w.+-]*\.conf")
        if any(entry != stock and not normal.fullmatch(entry.name) for entry in stock.parent.glob("*.conf")):
            raise ValueError("В EFI несколько записей и default не задан. Нельзя безопасно определить конфигурацию.")
        return stock, lines
    if any(len(row) != 1 for row in rows) or len({row[0].removesuffix(".conf") for row in rows}) != 1:
        raise ValueError(f"Неоднозначное значение default в {loader}.")
    name = rows[0][0].removesuffix(".conf")
    if Path(name).name != name or not name:
        raise ValueError(f"Недопустимое имя записи: {name}")
    entry = stock.with_name(name + ".conf")
    if not entry.is_file():
        raise ValueError(f"Не удалось однозначно определить текущую запись по default {name}.")
    return entry, lines


def loader_config(esp, entry, lines):
    # embloader builds its menu IDs without .conf; systemd-boot uses the filename.
    if not fields(lines, "default"):
        return "".join(lines).encode()
    efis = [esp / p for p in ("EFI/systemd/systemd-bootaa64.efi", "EFI/BOOT/BOOTAA64.EFI")]
    kinds = set()
    for path in efis:
        if path.is_file():
            data = path.read_bytes()
            if re.search(rb"\(embloader 0\.(?:4|7)(?:[.) ])", data):
                kinds.add("embloader")
            elif b"#### LoaderInfo: systemd-boot " in data or b"#### LoaderInfo: systemd " in data:
                if b"(embloader " not in data:
                    kinds.add("systemd-boot")
                else:
                    kinds.add("unknown")
            else:
                kinds.add("unknown")
    if kinds not in ({"embloader"}, {"systemd-boot"}):
        raise ValueError("Не удалось однозначно определить загрузчик EFI. Конфигурация сохранена без изменений.")
    desired = entry.stem if kinds == {"embloader"} else entry.name
    return replace_field(lines, "default", desired)


def replace_field(lines, key, value):
    data = "".join(lines)
    if fields(lines, key) == [value.split()]:
        return data.encode()
    result = []
    inserted = False
    for line in lines:
        if line.split()[:1] == [key]:
            if not inserted:
                result.append(f"{key} {value}\n")
                inserted = True
        else:
            result.append(line)
    if not inserted:
        if result and not result[-1].endswith("\n"):
            result.append("\n")
        result.append(f"{key} {value}\n")
    return "".join(result).encode()


def write_if_changed(path, data, backup=False):
    before = path.read_bytes() if path.exists() else None
    if before == data:
        return False
    saved = path.with_name(path.name + ".before-imx519")
    if backup and before is not None and not saved.exists():
        atomic_write(saved, before)
    atomic_write(path, data)
    return True


def bound_peripherals(dt_root, buses):
    devices = {}
    for bus in ("i2c", "spi", "mipi-dsi"):
        for dev in (buses / bus / "devices").glob("*"):
            node = (dev / "of_node").resolve()
            if (dev / "driver").exists() and node.is_relative_to(dt_root) and (node / "compatible").is_file():
                devices["/" + str(node.relative_to(dt_root))] = (
                    (node / "compatible").read_bytes().rstrip(b"\0").decode().split("\0"))
    return devices


def verify_peripherals(tree, devices):
    checked = set()
    for node, compatible in devices.items():
        found = get(tree, node, "compatible")
        same = found and found.split() == compatible
        if not same:
            raise ValueError(f"В итоговом DTB отсутствует работающее устройство {node} ({compatible[0]}).")
        path = PurePosixPath(node)
        for parent in (path, *path.parents):
            if parent not in checked:
                status = output("fdtget", "-d", "okay", tree, str(parent), "status")
                if status not in ("ok", "okay"):
                    raise ValueError(f"Итоговый DTB отключает работающее устройство {node} через {parent}.")
                checked.add(parent)


def retire_catalog_profile(esp, catalog, entry, profile, digest):
    """Plan how to disable a catalog item without invalidating other BLS entries."""
    old = efi_file(esp, profile)
    if old.parent != catalog or old.suffix != ".dtbo" or not old.exists():
        return None
    data = old.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"Содержимое {old.name} изменилось. Нельзя автоматически отключить профиль.")
    inactive = old.with_suffix(".dtbo.disabled")
    if inactive.exists() and inactive.read_bytes() != data:
        raise ValueError(f"В {inactive.name} уже сохранён другой оверлей.")
    archive = catalog.parent / "imx519-saved-overlays" / (digest + ".dtbo")
    archived = "/" + archive.relative_to(esp).as_posix()
    updates = {}
    for other in entry.parent.glob("*.conf"):
        if other == entry:
            continue
        lines = other.read_bytes().decode().splitlines(keepends=True)
        # EFI paths are case insensitive. Preserve surrounding whitespace and fields.
        def relocate(match):
            value = match.group()
            return archived if str(PurePosixPath(value)).casefold() == profile.casefold() else value

        updated = [re.sub(r"\S+", relocate, line) if line.split()[:1] == ["devicetree-overlay"]
                   else line for line in lines]
        if updated != lines:
            updates[other] = "".join(updated).encode()
    if updates and archive.exists() and archive.read_bytes() != data:
        raise ValueError(f"Архивная копия {archive} отличается от прежнего профиля.")
    return old, inactive, archive, updates, data


def confirm_replacement(port, compatible, profile, replace):
    detail = f"{port.upper()}: {' '.join(compatible)} ({PurePosixPath(profile).name}) → IMX519."
    print(detail)
    if replace:
        return
    if not sys.stdin.isatty():
        raise ValueError("Для подтверждения откройте терминал или укажите --replace.")
    try:
        answer = input("Заменить камеру на этом порту? [д/Н] ").strip().casefold()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer not in ("д", "да", "y", "yes"):
        raise ValueError("Замена отменена. Конфигурация камеры сохранена.")


def install(esp, token, kernel, work, port, modules_file, devices, replace=False, boot_id=None, prepare_driver=None):
    if not token or Path(token).name != token or token == "..":
        raise ValueError("Некорректный идентификатор в /etc/kernel/entry-token.")
    images = efi_file(esp, f"/{token}/{kernel}")
    catalog = images / "dtbo"
    stock = esp / f"loader/entries/{token}-{kernel}.conf"
    entry, loader_lines = read_default(esp, stock, token)
    if entry.is_symlink() or not entry.is_file():
        raise ValueError(f"Отсутствует исходная загрузочная запись: {entry}")
    lines = entry.read_bytes().decode().splitlines(keepends=True)
    base = efi_file(esp, single_path(lines, "devicetree"))
    linux = efi_file(esp, single_path(lines, "linux"))
    if not (linux.is_relative_to(images) and linux.is_file()
            and "radxa,dragon-q6a" in output("fdtget", base, "/", "compatible").split()):
        raise ValueError(f"{entry.name} должна указывать на ядро {kernel} и DTB Dragon Q6A.")
    loader = esp / "loader/loader.conf"
    next_loader = loader_config(esp, entry, loader_lines)
    built = {p: build_overlay(work, p) for p in PORTS}
    name = built[port].name
    enabled_camera = catalog / name
    inactive_camera = catalog / (name + ".disabled")
    selected = next((p for p in (enabled_camera, inactive_camera) if p.is_file()), built[port])
    camera = "/" + enabled_camera.relative_to(esp).as_posix()
    old = [p for row in fields(lines, "devicetree-overlay") for p in row]
    material = {camera: selected}

    def assemble(name, order):
        if not order:
            return base
        result = work / name
        subprocess.run(["fdtoverlay", "-i", base, "-o", result,
                        *(material[p] if p in material else efi_file(esp, p) for p in order)], check=True)
        return result

    current = assemble("current.dtb", old)
    bus_symbol, phy_index = PORTS[port]
    bus = output("fdtget", current, "/__symbols__", bus_symbol)
    camss = output("fdtget", current, "/__symbols__", "camss")
    phy = camss + f"/ports/port@{phy_index}"
    sensor = bus + "/imx519@1a"
    lens = bus + "/ak7375@c"
    tx, rx = sensor + "/port/endpoint", phy + "/endpoint"

    def linked(tree):
        out_handle = get(tree, tx, "phandle", "x")
        in_handle = get(tree, rx, "phandle", "x")
        return (get(tree, sensor, "compatible") == "sony,imx519" and out_handle and in_handle
                and get(tree, rx, "remote-endpoint", "x") == out_handle
                and get(tree, tx, "remote-endpoint", "x") == in_handle)

    def address_users(tree, address):
        return {bus + "/" + n for n in listing(tree, bus)
                if get(tree, bus + "/" + n, "reg", "x") == address
                or n.partition("@")[2].lower().lstrip("0") == address}

    def occupied(tree):
        return (address_users(tree, "1a") or address_users(tree, "c")
                or (exists(tree, phy) and any(n.split("@")[0] == "endpoint" for n in listing(tree, phy)))
                or any(endpoints(tree, bus)))

    wanted = list(old)
    previous = None
    replaced = None
    retirement = None
    extra_files = {}
    merged = current
    # A repeated installation before reboot can still see the driver we retired.
    marker = f"# q6a-imx519 replaced {port} "
    configured = linked(current)
    protected = dict(devices)
    for line in lines:
        if not line.startswith("# q6a-imx519 replaced "):
            continue
        _, _, _, saved_port, payload = line.split(maxsplit=4)
        if saved_port not in PORTS:
            continue
        node, compatible, profile, digest, saved_boot = json.loads(payload)
        saved_camera = "/" + (catalog / built[saved_port].name).relative_to(esp).as_posix()
        saved_bus = get(current, "/__symbols__", PORTS[saved_port][0])
        if saved_camera not in old or str(PurePosixPath(node).parent) != saved_bus:
            continue
        if saved_boot == boot_id and protected.get(node) == compatible:
            del protected[node]
        if saved_port == port and configured and profile not in old:
            retirement = retire_catalog_profile(esp, catalog, entry, profile, digest)
    if not configured and occupied(current):
        old_node, compatible, old_rx = sensor_on_port(current, bus, phy, port)
        if camera in old:
            raise ValueError(f"{port.upper()} занят конфликтующими профилями, включая IMX519.")
        owners = []
        for index, profile in enumerate(old):
            blob = efi_file(esp, profile)
            paths = overlay_paths(blob, current)
            if old_node in paths or old_rx in paths:
                owners.append((index, blob, paths))
        if len(owners) != 1 or old_node not in owners[0][2] or old_rx not in owners[0][2]:
            raise ValueError(f"{port.upper()} занят. Прежний маршрут не принадлежит одному отдельному оверлею.")
        index, blob, paths = owners[0]
        prior = assemble("prior.dtb", old[:index])
        remaining = assemble("without-camera.dtb", old[:index] + old[index + 1:])
        if exists(remaining, old_node) or occupied(remaining):
            raise ValueError(f"{port.upper()} занят также в базовом DTB или другом оверлее.")
        replaced = wanted[index]
        wanted[index] = camera
        merged = assemble("camera.dtb", wanted)
        digest = hashlib.sha256(blob.read_bytes()).hexdigest()
        retirement = retire_catalog_profile(esp, catalog, entry, replaced, digest)
        previous = (old_node, compatible)
    elif not configured:
        if camera in old:
            raise ValueError(f"Профиль IMX519 уже указан, но маршрут {port.upper()} отсутствует.")
        wanted.append(camera)
        merged = assemble("camera.dtb", wanted)

    # Each shipped IMX519 overlay supplies 128 MiB. Keep any pre-existing
    # shared pool, even when installing on a free port or replacing its provider.
    cma = "/reserved-memory/linux,cma"
    if merged != current and exists(current, cma):
        props = set(listing(current, cma, "-p")) | set(listing(merged, cma, "-p"))
        differences = {prop for prop in props if get(current, cma, prop, "bx") != get(merged, cma, prop, "bx")}
        if differences == {"size"}:
            cma_blob = preserve_cma(current, cma, work)
            destination = catalog / cma_blob.name
            if destination.exists() and destination.read_bytes() != cma_blob.read_bytes():
                raise ValueError(f"Уже существует другой профиль {destination.name}.")
            profile = "/" + destination.relative_to(esp).as_posix()
            material[profile] = cma_blob
            extra_files[destination] = cma_blob.read_bytes()
            wanted = [p for p in wanted if p != profile]
            wanted.append(profile)
            merged = assemble("camera.dtb", wanted)
        elif differences:
            raise ValueError("Профиль меняет конфигурацию существующего пула CMA.")
    if replaced:
        check_removal(blob, paths, current, merged, prior, old_node, old_rx, port)

    if not linked(merged) or [n for n in listing(merged, phy) if n.split("@")[0] == "endpoint"] != ["endpoint"]:
        raise ValueError(f"Проверка связи {port.upper()} с CSIPHY{phy_index} не прошла.")
    if (get(merged, tx, "data-lanes", "u") != "1 2" or get(merged, rx, "data-lanes", "u") != "0 1"
            or get(merged, tx, "link-frequencies", "u") != "0 408000000"):
        raise ValueError(f"Маршрут {port.upper()} не соответствует двухлинейному профилю IMX519 RAW10.")
    if (any(device != sensor for device, _ in endpoints(merged, bus))
            or address_users(merged, "1a") != {sensor} or address_users(merged, "c") != {lens}):
        raise ValueError(f"{port.upper()} занят также другим сенсором.")
    if merged != current:
        for other, (symbol, index) in PORTS.items():
            if other == port:
                continue
            other_bus = output("fdtget", current, "/__symbols__", symbol)
            other_phy = camss + f"/ports/port@{index}"
            if routes(current, other_bus, other_phy) != routes(merged, other_bus, other_phy):
                raise ValueError(f"Итоговая конфигурация меняет маршрут соседнего {other.upper()}.")
    if previous and protected.get(previous[0]) == previous[1]:
        del protected[previous[0]]
    verify_peripherals(merged, protected)
    verify_peripherals(merged, {sensor: ["sony,imx519"], lens: ["asahi-kasei,ak7375"]})
    lens_handle = get(merged, lens, "phandle", "x")
    if (not lens_handle or get(merged, sensor, "lens-focus", "x") != lens_handle
            or get(merged, sensor, "reg", "x") != "1a" or get(merged, lens, "reg", "x") != "c"):
        raise ValueError(f"Некорректная привязка IMX519 к AK7375 на {port.upper()}.")
    if replaced:
        confirm_replacement(port, previous[1], replaced, replace)
        lines = [line for line in lines if not line.startswith(marker)]
    next_entry = (replace_field(lines, "devicetree-overlay", " ".join(wanted))
                  if wanted != old else "".join(lines).encode())
    if replaced:
        next_entry = next_entry.rstrip(b"\n") + b"\n" + (marker + json.dumps([*previous, replaced, digest, boot_id]) + "\n").encode()
    files = extra_files
    for p, blob in built.items():
        enabled = catalog / blob.name
        inactive = enabled.with_suffix(".dtbo.disabled")
        if p == port and camera in wanted:
            files[enabled] = selected.read_bytes()
        elif not enabled.exists() and not inactive.exists():
            files[inactive] = blob.read_bytes()
    # Every prerequisite is published before the entry referencing it. If interrupted
    # at any point, the previous or new entry is usable and the install can be retried.
    if prepare_driver is not None:
        prepare_driver()
    catalog.mkdir(exist_ok=True)
    changed = False
    for path, data in files.items():
        if write_if_changed(path, data) and path == catalog / name:
            changed = True
    config = modules_file.read_bytes() if modules_file.exists() else b""
    missing = [m for m in MODULES if m.encode() not in config.splitlines()]
    if missing:
        separator = b"\n" if config and not config.endswith(b"\n") else b""
        write_if_changed(modules_file, config + separator + ("\n".join(missing) + "\n").encode(), backup=True)
    if retirement:
        old_file, inactive, archive, updates, data = retirement
        if updates:
            archive.parent.mkdir(exist_ok=True)
            write_if_changed(archive, data)
            for other, new_config in updates.items():
                write_if_changed(other, new_config, backup=True)
    if write_if_changed(entry, next_entry, backup=True):
        changed = True
    if (next_loader or loader.exists()) and write_if_changed(loader, next_loader, backup=True):
        changed = True
    if retirement:
        os.replace(old_file, inactive)
    if enabled_camera in files and inactive_camera.exists() and inactive_camera.read_bytes() == files[enabled_camera]:
        inactive_camera.unlink()
    return entry, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=str.lower, choices=PORTS, default="cam3",
                        help="разъём IMX519 (по умолчанию cam3/J7)")
    parser.add_argument("--replace", action="store_true",
                        help="подтвердить замену камеры на выбранном порту без диалога")
    args = parser.parse_args()
    if sys.platform != "linux" or os.geteuid() != 0:
        parser.exit(1, "Запустите на Q6A: sudo python3 install.py\n")
    dt_root = Path("/sys/firmware/devicetree/base")
    if b"radxa,dragon-q6a" not in (dt_root / "compatible").read_bytes().split(b"\0"):
        raise ValueError("Ожидается плата Radxa Dragon Q6A.")
    if not ESP.is_mount():
        raise ValueError("EFI System Partition не смонтирован в /boot/efi.")
    kernel = os.uname().release
    token = Path("/etc/kernel/entry-token").read_text().strip()
    import fcntl  # Linux target only.
    # Share the lock used by the IMX296 installer when editing the same EFI files.
    with open("/run/lock/q6a-imx296.lock", "a") as lock, tempfile.TemporaryDirectory() as work:
        fcntl.flock(lock, fcntl.LOCK_EX)
        dependencies()
        entry, changed = install(ESP, token, kernel, Path(work), args.port,
                                 Path("/etc/modules-load.d/q6a-imx519.conf"),
                                 bound_peripherals(dt_root, Path("/sys/bus")), replace=args.replace,
                                 boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                                 prepare_driver=lambda: prepare_modules(kernel, Path(work), atomic_write))
    print(f"IMX519 {args.port.upper()}: {entry.name}")
    if not changed:
        from capture import find_camera
        try:
            media, sensor = find_camera(args.port, f"msm_csiphy{PORTS[args.port][1]}")
        except (ValueError, subprocess.SubprocessError) as error:
            bus = (dt_root / "__symbols__" / PORTS[args.port][0]).read_bytes().rstrip(b"\0").decode()
            node = dt_root / bus.lstrip("/") / "imx519@1a/compatible"
            if node.is_file() and b"sony,imx519" in node.read_bytes().split(b"\0"):
                print(f"Оверлей уже загружен. Захват пока недоступен.\n{error}")
                return
        else:
            print(f"Камера доступна: {media}, {sensor}. Можно запускать capture.py.")
            return
    print("При следующей обычной перезагрузке настройки вступят в силу: sudo reboot")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
