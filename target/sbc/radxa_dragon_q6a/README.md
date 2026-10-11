# IMX519 на Radxa Dragon Q6A

**Статус: драйверы, три оверлея и демка собраны на Q6A; захват и фокус пока не проверены.**
Проверка выполнена на Ubuntu 24.04.5 LTS / `7.0.11-7-qcom`.
Оверлеи установлены как `.dtbo.disabled`; активная конфигурация камер
и загрузки не менялась. Имеющийся IMX519 с объективом 80° планируется
проверить на CAM3. Маркировка физического модуля и схема кабеля не зафиксированы.

## Оверлеи CAM1, CAM2 и CAM3

| Файл | Название в меню | CCI / CSIPHY | GPIO включения модуля |
| --- | --- | --- | --- |
| [imx519-cam1.dts](overlay/imx519-cam1.dts) | Enable IMX519 camera on CAM1 | `cci0_i2c0` / 0 | GPIO36 |
| [imx519-cam2.dts](overlay/imx519-cam2.dts) | Enable IMX519 camera on CAM2 | `cci1_i2c0` / 2 | GPIO77 |
| [imx519-cam3.dts](overlay/imx519-cam3.dts) | Enable IMX519 camera on CAM3 | `cci1_i2c1` / 3 | GPIO78 |

Каждый оверлей описывает IMX519 по адресу `0x1a`, две линии CSI-2 RAW10,
24 МГц и `link-frequencies = 408000000` по контракту выбранного драйвера.
Сенсор связан через `lens-focus` с AK7375 по адресу `0x0c` на той же шине,
как в [описании модуля Raspberry Pi](https://github.com/raspberrypi/linux/blob/43c132e8863c3bff3647033b6a7d2bf87b15501c/arch/arm/boot/dts/overlays/imx519.dtsi).
Имена узлов, clocks, regulators и endpoints различаются между портами.
Общий CMA — 128 МиБ; его достаточность для трёх потоков не измерена.

`make overlay-check` проверяет все 15 порядков применения: отдельные порты,
пары и три камеры. Дополнительно проверено сочетание AR0234 на CAM2
с IMX519 на CAM3 в обоих порядках. Это проверка скомпонованного дерева,
а не физического захвата. На одном порту выбирается один камерный оверлей;
поле `exclusive` использует имя его CCI-шины.

## Подключение

Q6A J16/CAM2 и J7/CAM3 имеют 15 контактов с шагом 1 мм, две линии и
[распиновку Raspberry Pi](https://docs.radxa.com/en/dragon/q6a/hardware-use/mipi-csi).
I2C/reset проходят через преобразователи 1,8↔3,3 В; питание разъёма 3,3 В.
J14/CAM1 — 31 контакт, 0,3 мм, четыре линии и управляющая шина 1,8 В.
Оверлей CAM1 использует первые две линии, но не решает согласование
управления и переход с 31 на 15 контактов. Сверить
[распиновку камеры](../../../docs/reference/pinout.md), контактную сторону
шлейфа и [схему платы](https://github.com/pOmelchenko/radxa_dragon_q6a/blob/main/docs/reference/hardware.md#камерные-разъёмы).

Оверлеи предполагают локальный генератор 24 МГц на модуле; SoC MCLK
они не выводят. `VANA-supply` и `vdd-supply` моделируют включение модуля
через GPIO. Внутренние `VDIG`, `VDDL` сенсора и `vio` привода оставлены
на dummy regulators ядра: схема внутренних стабилизаторов экземпляра
не установлена. Fixed-clock описывает частоту, но не создаёт физический
такт. Эти предположения требуют проверки на подключённой камере.

## Сборка на Q6A

В каталоге этой платформы, из обычной учётной записи:

```sh
sudo apt install build-essential pkg-config device-tree-compiler patch \
    python3 v4l-utils libcamera-dev libcamera-tools libsdl2-dev \
    libgles2-mesa-dev linux-headers-$(uname -r)
make driver overlay demo
mkdir -p build
sudo cp /boot/efi/RadxaOS/$(uname -r)/qcs6490-radxa-dragon-q6a.dtb build/base-q6a.dtb
sudo chown "$(id -u):$(id -g)" build/base-q6a.dtb
make overlay-check
```

Для другого BSP передать чистое дерево платы:
`make overlay-check BASE_DTB=/path/to/base.dtb`.
Базовый DT должен содержать `__symbols__`; дерево с уже применённой камерой
того же порта не подходит.

`make driver` получает закреплённые SHA-256 исходники IMX519 из Raspberry Pi
Linux и AK7375 из Linux 7.0. Единственный патч сенсора заменяет Pi-specific
`MEDIA_BUS_FMT_SENSOR_DATA` на mainline `MEDIA_BUS_FMT_METADATA_FIXED`
для незадействованного metadata pad; регистры изображения не меняются.
Сборка проверена с `-Werror` под `7.0.11-7-qcom`. После смены ядра
модули нужно пересобрать. Источники и лицензии — [sources.json](sources.json).

## Установка без включения

```sh
sudo make install-overlays-disabled
sudo install -d /lib/modules/$(uname -r)/updates
sudo install -m 0644 build/driver/imx519.ko build/driver/ak7375.ko \
    /lib/modules/$(uname -r)/updates/
sudo depmod -a
```

Первый шаг создаёт только `imx519-cam1.dtbo.disabled`,
`imx519-cam2.dtbo.disabled`, `imx519-cam3.dtbo.disabled` в каталоге
`/boot/efi/RadxaOS/<kernel>/dtbo/`. Скрипт отказывается заменять отличающийся
файл или уже включённый оверлей и проверяет сохранность активных `.dtbo`
и boot entries. Установка драйверов не выполняет `modprobe`.
Эти команды не включают камеру и не перезагружают плату.

Для последующей аппаратной проверки выбрать нужный IMX519 в `rsetup`,
отключив другие камерные оверлеи этого же порта, и обновить конфигурацию
загрузки обычным способом RadxaOS. Первую активацию выполнять с доступным
резервным вариантом загрузки по [репозиторию платы](https://github.com/pOmelchenko/radxa_dragon_q6a).
После загрузки проверить `dmesg`, `v4l2-ctl --list-devices`,
`media-ctl -d /dev/media0 -p` и `cam -l`. Первый кадр ещё не получен;
это этап проверки, а не подтверждённая инструкция захвата.

## Демка

Из терминала графической сессии Q6A:

```sh
make check
sh tools/preview.sh --list-cameras
sh tools/preview.sh
```

`make check` проверяет шейдер на синтетических кадрах без камеры.
Просмотр автоматически выбирает единственную IMX519; при нескольких
требуется точный `--camera=ID` из списка. По умолчанию запрашивается
1920×1080, фактический размер/stride печатается после настройки libcamera.
Фильтр, сравнение, полный экран и снимок аналогичны демке AR0234.
Подробнее — [demo/README.md](demo/README.md).

Автофокус в демку не добавлен. Узел AK7375 готовит драйвер привода;
распознавание, ручное управление и алгоритм AF ещё требуют проверки.
Поддержка IMX519 в Pi libcamera не подтверждает tuning или автофокус
в CAMSS simple/software ISP на Q6A.

## Код и результаты

| Файл | Назначение |
| --- | --- |
| [Makefile](Makefile) | Сборка драйверов, оверлеев, демки и проверки |
| [tools/fetch-driver.py](tools/fetch-driver.py) | Загрузка исходников с проверкой SHA-256 |
| [patches/imx519-linux-7.patch](patches/imx519-linux-7.patch) | Адаптация metadata code к mainline Linux |
| [tools/check-overlays.py](tools/check-overlays.py) | Проверка CSI, питания, clocks, lens-focus и 15 сочетаний |
| [tools/install-overlays-disabled.py](tools/install-overlays-disabled.py) | Установка без активации |
| [demo/imx519-demo.cpp](demo/imx519-demo.cpp) | libcamera + SDL2 + OpenGL ES 3 |
| [validation/2026-10-11.json](validation/2026-10-11.json) | Конфигурация, сборка, тесты и ограничения |

Драйверы и адаптация — GPL-2.0; оверлеи — GPL-2.0-only с сохранением
Radxa [BSD-условий](LICENSE.Radxa). Демка — [MIT](LICENSE.MIT).
Зависимости остаются в исключённом `vendor/`, сборки — в `build/`,
захваты и журналы — в `runs/`. Первый захват, Bayer/crop, частота,
цвет/экспозиция, ручной фокус и AF, cold boot и длительный прогон
не подтверждены.
