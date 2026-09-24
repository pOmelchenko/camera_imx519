# Происхождение и воспроизводимость

## Сохранённые исходники

`driver/imx519.c` и `driver/ak7375.c` скачаны 2026-09-09 по Москве
без изменений из ветки Raspberry Pi Linux `rpi-6.18.y`:

- [imx519.c](https://github.com/raspberrypi/linux/blob/rpi-6.18.y/drivers/media/i2c/imx519.c)
- [ak7375.c](https://github.com/raspberrypi/linux/blob/rpi-6.18.y/drivers/media/i2c/ak7375.c)
- [IMX519 device-tree bindings используемого overlay](https://github.com/raspberrypi/linux/blob/rpi-6.18.y/arch/arm/boot/dts/overlays/imx519.dtsi)
- [Репозиторий Arducam с описанием поддержки IMX519/AK7375](https://github.com/ArduCAM/IMX519_AK7375)

Ветка может изменяться. Точный commit SHA при скачивании не был записан;
этот пробел не подменяется предположением о коммите. Для повторной сборки
используются уже сохранённые файлы и `SOURCES.sha256`:

```sh
sha256sum -c SOURCES.sha256   # на Radxa/Linux
shasum -a 256 -c SOURCES.sha256   # на macOS
```

Сборка не скачивает актуальную ветку заново. При будущих изменениях драйвера
нужно сохранить diff, commit/источник, обновить DKMS-версию и хеши с записью
в WORKLOG. SPDX GPL-2.0 и уведомления об авторах сохранены в исходниках.

## Overlay

База — установленный на плате файл:

```text
/usr/src/radxa-overlays-0.2.30/arch/arm64/boot/dts/qcom/overlays/qcs6490-radxa-dragon-q6a-cam3-radxa-camera-8m-219.dtso
```

Сохранённая копия базы: `reference-q6a-cam3-imx219.dtso` в этом каталоге.
Готовый изменённый исходник — `../overlays/qcs6490-radxa-dragon-q6a-cam3-imx519.dts`.
Из базы перенесена разводка CAM3; из IMX519 dtsi — параметры сенсора/линзы.
Резерв CMA увеличен с 128 до 256 MiB. Метаданные содержат CAM3 и конфликтующие
ресурсы для rsetup. Проверка fdtoverlay выполняется в build.sh.

## Окружение

Первичная система: Ubuntu 24.04.4 LTS, arm64, `7.0.11-6-qcom`,
`linux-headers-7.0.11-6-qcom`, rsetup 0.4.28, radxa-overlays-dkms 0.2.30.
libcamera-tools/ipa/libcamera0.7: `0.7.1-1-radxa-3` из репозитория Radxa
`qcs6490-noble`; v4l-utils: `1.26.1-4build3`.

Комплект сохраняет исходники камеры, но не архивирует весь образ ОС, .deb
пакеты или компилятор. Поэтому побитовая воспроизводимость всей системы
не заявляется. Перед обновлениями сохранять диагностический снимок.

## Отдельная libcamera с поддержкой IMX519

- Источник: [radxa-pkg/libcamera, commit de1e9bc0](https://github.com/radxa-pkg/libcamera/tree/de1e9bc095e23085e77533357d2582176de0a582).
  Совпадает с commit prefix установленной сборки `0.7.1-1-radxa-3`.
- Применяются все patches из `debian/patches/series`, включая Radxa per-sensor
  tuning, затем сохранённый `../libcamera/imx519.patch`.
- Закон усиления сверён с [официальным Raspberry Pi IMX519 helper](https://github.com/raspberrypi/libcamera/blob/main/src/ipa/rpi/cam_helper/cam_helper_imx519.cpp).
  Black level 4096 в 16-битном представлении — из [Raspberry Pi tuning IMX519](https://github.com/raspberrypi/libcamera/blob/main/src/ipa/rpi/vc4/data/imx519.json).
  Эти ссылки фиксируют происхождение параметров; собственный патч хранится локально.
- Контейнер Ubuntu 24.04 arm64. В проверенной сборке образ ubuntu разрешён
  в digest `sha256:561618e2c15bf2397621dd04f96926663a3b5616c189cf7e38db7e82f5c538ea`.
  Пакеты сборки перечислены внутри runtime в `build-packages.tsv`, конфигурация
  Docker — локально в `build/userspace/builder-image.json`.
- Версия runtime `0.7.1+radxa.de1e9bc0.imx519.1`; архив SHA-256
  `48c432913b9e9fefcfe1ebd3c0b434bd864421e183d0c9e901ec73869c61bc21`.
  Тесты: `build/userspace/testlog.txt`, 8 passed / 0 failed.
- Источник и патч закреплены, но apt-репозитории обновляются, а IPA signing key
  создаётся заново при сборке. Побитовая идентичность повторной сборки не заявляется.

Активный профиль v2 хранится отдельно в `../libcamera/tuning/simple/imx519.yaml`.
Он изменяет targetMsv с 2.5 на 2.0, не меняя бинарный runtime или его SHA-256.
`run.sh` задаёт этот каталог первым в LIBCAMERA_IPA_CONFIG_PATH. Отдельный YAML
входит в обычную синхронизацию исходников/документации.

## Аппаратная документация

- [CSI-разъёмы Dragon Q6A](https://docs.radxa.com/en/dragon/q6a/hardware-use/mipi-csi)
- [Штатная настройка CAM2/CAM3 на примере IMX219](https://docs.radxa.com/en/dragon/q6a/accessories/camera-8m-219)

Документация IMX219 использована для разводки и механизма загрузки overlay.
Она не является подтверждением штатной поддержки IMX519.

## Дополнение 2026-09-25: автофокус

Патч `../libcamera/autofocus-simple.patch` применяется после `imx519.patch` к
тому же закреплённому commit Radxa. Его SHA-256:
`fd25bd5842f392c617ddaf63b143f570d019fe41c4ef25b5bf68a18aa3e4fbae`.
В качестве исходной структуры ручного управления линзой использован
[незавершённый upstream patch](https://patchwork.libcamera.org/patch/26241/),
сохранённый как `../libcamera/upstream-focus-reference.patch` (SHA-256
`3cf5824d0b1772aca38ddf019f9c559b7bee4356e4ee34bbb5685e0ea78a413a`).
Он не применяется при сборке. Статистика резкости и алгоритм CDAF добавлены
в собственном патче; источник сопоставления 0..15 диоптрий с 0..4095 кодами —
[Arducam/Raspberry Pi PDAF proposal](https://lists.libcamera.org/pipermail/libcamera-devel/2023-June/038275.html),
для варианта объектива 80° оно пока не откалибровано.

Результат последней сборки: runtime archive SHA-256
`989d44efdfd20091514a1c9607c10a1e8f9b0758ada8b7438c38c7c125423f03`;
8 IPA tests passed. Предыдущий runtime archive с SHA-256 `48c432...` оставлен
как точка возврата. Источники CAMSS для исследования, их версии и хеши
записаны в [`../research/autofocus.md`](../research/autofocus.md).
