"""Inspect the selected connector and establish which DTBO can be removed safely."""
from pathlib import PurePosixPath
import posixpath
import subprocess


def get(tree, node, prop, kind="s"):
    result = subprocess.run(["fdtget", "-t", kind, tree, node, prop],
                            capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def listing(tree, node, flag="-l"):
    return subprocess.check_output(["fdtget", flag, tree, node], text=True).split()


def walk(tree, node):
    yield node
    for child in listing(tree, node):
        yield from walk(tree, posixpath.join(node, child))


def under(path, parent):
    return path == parent or path.startswith(parent + "/")


def endpoints(tree, bus):
    for child in listing(tree, bus):
        device = bus + "/" + child
        for node in walk(tree, device):
            if PurePosixPath(node).name.split("@")[0] == "endpoint":
                yield device, node


def routes(tree, bus, phy):
    """Compare links by device path. Overlay order can renumber every phandle."""
    if not exists(tree, phy):
        return {}
    senders = {get(tree, node, "phandle", "x"): node for _, node in endpoints(tree, bus)}
    result = {}
    for child in listing(tree, phy):
        if child.split("@")[0] != "endpoint":
            continue
        rx = phy + "/" + child
        remote = get(tree, rx, "remote-endpoint", "x")
        tx = senders.get(remote) if remote else None
        back = tx and get(tree, tx, "remote-endpoint", "x") == get(tree, rx, "phandle", "x")
        result[rx] = (tx, bool(back), remote is not None)
        for ep in (rx, tx):
            if ep:
                for prop in ("data-lanes", "clock-lanes", "clock-noncontinuous", "link-frequencies", "status"):
                    result[ep, prop] = get(tree, ep, prop, "bx")
    return result


def sensor_on_port(tree, bus, phy, port):
    error = f"{port.upper()} занят. Не удалось выделить единственный двусторонний маршрут прежнего сенсора."
    if not exists(tree, phy):
        raise ValueError(error)
    receivers = [phy + "/" + n for n in listing(tree, phy) if n.split("@")[0] == "endpoint"]
    if len(receivers) != 1:
        raise ValueError(error)
    rx = receivers[0]
    endpoint = get(tree, rx, "remote-endpoint", "x")
    receiver = get(tree, rx, "phandle", "x")
    if not endpoint or not receiver:
        raise ValueError(error)
    matches = []
    for device, child in endpoints(tree, bus):
        if (get(tree, child, "phandle", "x") == endpoint
                and get(tree, child, "remote-endpoint", "x") == receiver):
            compatible = get(tree, device, "compatible")
            if compatible:
                matches.append((device, compatible.split(), rx))
    if len(matches) != 1:
        raise ValueError(error)
    return matches[0]


def overlay_paths(blob, tree):
    """Map fragment nodes to absolute paths using dtc's external target fixups."""
    targets = {}
    if "__fixups__" in listing(blob, "/"):
        for symbol in listing(blob, "/__fixups__", "-p"):
            for fixup in get(blob, "/__fixups__", symbol).split():
                fragment, prop, offset = fixup.rsplit(":", 2)
                if prop == "target" and offset == "0":
                    targets[fragment] = get(tree, "/__symbols__", symbol)
    paths = {}
    for name in listing(blob, "/"):
        fragment = "/" + name
        if "__overlay__" not in listing(blob, fragment):
            continue
        destination = get(blob, fragment, "target-path") or targets.get(fragment)
        if not destination or not destination.startswith("/"):
            raise ValueError(f"Не удалось определить назначение фрагмента {name} в {blob.name}.")
        root = fragment + "/__overlay__"
        for node in walk(blob, root):
            path = destination.rstrip("/") + node[len(root):] or "/"
            paths.setdefault(path, []).append(node)
    return paths


def camera_resources(tree, sensor, paths, pins, power_gpio):
    """Only clocks, regulators and pin groups actually referenced by the old camera."""
    candidates = {}
    resources = set()
    for path in paths:
        parent = posixpath.dirname(path)
        if ((parent == "/" and get(tree, path, "compatible") in ("regulator-fixed", "fixed-clock"))
                or parent == pins):
            handle = get(tree, path, "phandle", "x")
            if handle:
                candidates[handle] = path
        # Some Radxa profiles drive CAM_POWER_EN with an always-on regulator
        # without a sensor supply phandle, e.g. IMX219 on J16.
        if parent == "/" and get(tree, path, "compatible") == "regulator-fixed" and power_gpio:
            gpio = get(tree, path, "gpios", "x") or get(tree, path, "gpio", "x")
            if (gpio and gpio.split()[:2] == power_gpio.split()[:2]
                    and get(tree, path, "regulator-always-on", "bx") == ""):
                resources.add(path)
    pending = [sensor, *resources]
    while pending:
        node = pending.pop()
        for prop in listing(tree, node, "-p"):
            if prop.endswith("-supply") or prop == "clocks" or prop.startswith("pinctrl-") and prop[8:].isdigit():
                refs = get(tree, node, prop, "x").split()
                # For clocks only the first cell is unambiguously a provider.
                for ref in refs[:1] if prop == "clocks" else refs:
                    target = candidates.get(ref)
                    if target and target not in resources:
                        resources.add(target)
                        pending.append(target)
    return resources


def check_removal(blob, paths, current, merged, prior, sensor, rx, port):
    """Everything besides the old route and its private resources must survive."""
    pins = get(current, "/__symbols__", "tlmm")
    power_gpio = get(merged, f"/imx519-{port}-enable", "gpios", "x")
    private = {p for p in camera_resources(current, sensor, paths, pins, power_gpio)
               if not exists(prior, p) and not exists(merged, p)}
    for path, sources in paths.items():
        if under(path, sensor) or under(path, rx) or any(under(path, p) for p in private):
            continue
        if not exists(merged, path):
            raise ValueError(f"{blob.name} также настраивает {path}. Автозамена невозможна.")
        for source in sources:
            for prop in listing(blob, source, "-p"):
                # IMX296 sets its dedicated CCI bus to 100 kHz. On an otherwise
                # empty bus IMX519 can return to the board's own clock setting.
                if (prop == "clock-frequency" and path == posixpath.dirname(sensor)
                        and listing(current, path) == [posixpath.basename(sensor)]):
                    continue
                if prop in ("phandle", "linux,phandle"):
                    continue
                if get(current, path, prop, "bx") != get(merged, path, prop, "bx"):
                    raise ValueError(f"{blob.name} также изменяет {path} ({prop}). Автозамена невозможна.")


def exists(tree, path):
    return subprocess.run(["fdtget", "-p", tree, path], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def preserve_cma(tree, node, work):
    """Reproduce the board-wide CMA pool with exactly the original size in cells."""
    props = set(listing(tree, node, "-p"))
    size = get(tree, node, "size", "x")
    if (props != {"compatible", "size", "reusable", "linux,cma-default"} or listing(tree, node)
            or get(tree, node, "compatible") != "shared-dma-pool" or not size):
        raise ValueError("Оверлей также задаёт нестандартный пул CMA. Автозамена невозможна.")
    cells = ["0x" + cell for cell in size.split()]
    target = work / ("q6a-camera-cma-" + "-".join(size.split()) + ".dtbo")
    source = f"""/dts-v1/; /plugin/;
        / {{ metadata {{
            title = "Keep camera CMA pool"; compatible = "radxa,dragon-q6a"; category = "camera";
            description = "Retain shared DMA memory when replacing a camera.";
        }}; }};
        &{{/reserved-memory}} {{ linux,cma {{
            compatible = "shared-dma-pool"; size = <{' '.join(cells)}>; reusable; linux,cma-default;
        }}; }};
    """
    subprocess.run(["dtc", "-@", "-O", "dtb", "-o", target, "-"], input=source, text=True, check=True)
    return target
