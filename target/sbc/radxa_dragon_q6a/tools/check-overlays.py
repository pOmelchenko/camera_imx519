#!/usr/bin/env python3
"""Check individual Q6A overlays and every ordered combination on a base DTB."""
import argparse
from datetime import date
import itertools
import json
from pathlib import Path
import subprocess

PORTS = {
    1: dict(controller='cci0', bus='cci0_i2c0', phy=0, gpio=36),
    2: dict(controller='cci1', bus='cci1_i2c0', phy=2, gpio=77),
    3: dict(controller='cci1', bus='cci1_i2c1', phy=3, gpio=78),
}

def get(dtb, node, prop, numeric=False):
    flags = ['-t', 'x'] if numeric else []
    output = subprocess.check_output(['fdtget', *flags, str(dtb), node, prop], text=True).strip()
    return [int(value, 16) for value in output.split()] if numeric else output

def require(good, message):
    if not good:
        raise RuntimeError(message)

def check_graph(dtb, cameras, symbols):
    identities = dict(sensor=[], clock=[], regulator=[], phy=[], lens=[])
    for camera in cameras:
        config = PORTS[camera]
        sensor = symbols[config['bus']] + '/imx519@1a'
        endpoint = sensor + '/port/endpoint'
        phy = symbols['camss'] + f'/ports/port@{config["phy"]}/endpoint'
        clock = f'/imx519-cam{camera}-clock'
        regulator = f'/imx519-cam{camera}-enable'
        lens = symbols[config['bus']] + '/ak7375@c'
        pinctrl = symbols['tlmm'] + f'/imx519-cam{camera}-enable-state'
        require(get(dtb, symbols[config['controller']], 'status') == 'okay', 'CCI disabled')
        require(get(dtb, symbols[config['bus']], 'status') == 'okay', 'I2C bus disabled')
        require(get(dtb, symbols[config['bus']], 'clock-frequency', True) == [400000], 'Wrong camera I2C speed')
        require(get(dtb, sensor, 'compatible') == 'sony,imx519', 'Wrong sensor')
        require(get(dtb, sensor, 'reg', True) == [0x1a], 'Wrong I2C address')
        require(get(dtb, endpoint, 'data-lanes', True) == [1, 2], 'Wrong sensor lanes')
        require(get(dtb, endpoint, 'clock-lanes', True) == [0], 'Wrong sensor clock lane')
        require(get(dtb, endpoint, 'link-frequencies', True) == [0, 408000000], 'Wrong link frequency')
        require(get(dtb, phy, 'data-lanes', True) == [0, 1], 'Wrong PHY lanes')
        require(get(dtb, phy, 'clock-lanes', True) == [7], 'Wrong PHY clock lane')
        require(get(dtb, endpoint, 'remote-endpoint', True) == get(dtb, phy, 'phandle', True), 'Sensor link is not reciprocal')
        require(get(dtb, phy, 'remote-endpoint', True) == get(dtb, endpoint, 'phandle', True), 'PHY link is not reciprocal')
        require(get(dtb, clock, 'clock-frequency', True) == [24000000], 'Wrong module clock')
        require(get(dtb, sensor, 'clocks', True) == get(dtb, clock, 'phandle', True), 'Clock cross-link')
        require(get(dtb, sensor, 'VANA-supply', True) == get(dtb, regulator, 'phandle', True), 'Supply cross-link')
        require(get(dtb, regulator, 'gpios', True) == get(dtb, symbols['tlmm'], 'phandle', True) + [config['gpio'], 0], 'Wrong enable GPIO')
        require(get(dtb, regulator, 'pinctrl-0', True) == get(dtb, pinctrl, 'phandle', True), 'Pinctrl cross-link')
        require(get(dtb, regulator, 'startup-delay-us', True) == [100000], 'Missing module startup delay')
        require(get(dtb, pinctrl, 'pins') == f'gpio{config["gpio"]}', 'Wrong pinctrl GPIO')
        require(get(dtb, lens, 'compatible') == 'asahi-kasei,ak7375', 'Wrong lens driver')
        require(get(dtb, lens, 'reg', True) == [0x0c], 'Wrong lens address')
        require(get(dtb, sensor, 'lens-focus', True) == get(dtb, lens, 'phandle', True), 'Lens cross-link')
        require(get(dtb, lens, 'vdd-supply', True) == get(dtb, regulator, 'phandle', True), 'Lens supply cross-link')
        require(get(dtb, sensor, 'clock-names') == 'xclk', 'Wrong clock name')
        for key, node in [('sensor', endpoint), ('clock', clock), ('regulator', regulator), ('phy', phy), ('lens', lens)]:
            identities[key].append(tuple(get(dtb, node, 'phandle', True)))
    for name, phandles in identities.items():
        require(len(set(phandles)) == len(cameras), f'{name} phandles collide')
    require(get(dtb, symbols['camss'], 'status') == 'okay', 'CAMSS disabled')
    require(get(dtb, '/reserved-memory/linux,cma', 'size', True) == [0, 0x8000000], 'Unexpected shared CMA size')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--build-dir', type=Path, default=Path('build'))
    args = parser.parse_args()
    symbols = {name: get(args.base, '/__symbols__', name)
               for name in ['camss', 'tlmm', 'cci0', 'cci1', 'cci0_i2c0', 'cci1_i2c0', 'cci1_i2c1']}
    for camera, config in PORTS.items():
        overlay = args.build_dir / f'imx519-cam{camera}.dtbo'
        require(get(overlay, '/metadata', 'title') == f'Enable IMX519 camera on CAM{camera}', 'Wrong title')
        require(get(overlay, '/metadata', 'exclusive') == config['bus'], 'Wrong exclusive bus')
    cases = []
    for count in range(1, 4):
        for order in itertools.permutations(PORTS, count):
            output = args.build_dir / ('q6a-imx519-cam' + '-'.join(map(str, order)) + '-test.dtb')
            overlays = [args.build_dir / f'imx519-cam{camera}.dtbo' for camera in order]
            subprocess.run(['fdtoverlay', '-i', str(args.base), '-o', str(output), *map(str, overlays)], check=True)
            check_graph(output, order, symbols)
            cases.append(dict(order=list(order), graph_valid=True))
            print('PASS ' + ' + '.join(f'CAM{camera}' for camera in order))
    result = dict(verified_on=date.today().isoformat(),
                  validation_kind='Device tree build/apply and graph validation; not physical multi-camera capture',
                  base_sha256=__import__('hashlib').sha256(args.base.read_bytes()).hexdigest(),
                  cases=cases, shared_cma_bytes=0x8000000)
    (args.build_dir / 'overlay-validation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'{len(cases)} ordered combinations passed')

if __name__ == '__main__':
    main()
