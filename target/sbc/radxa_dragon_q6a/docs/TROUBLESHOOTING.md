# Диагностика

| Наблюдение | Что установлено / следующий шаг |
| --- | --- |
| `Device found is imx519` | Сенсор ответил с ожидаемым ID. Это ещё не проверка потока; запустить capture.sh. |
| `imx519.yaml not found` | Запущена штатная сборка без профиля. Использовать `bash cam.sh` или `bash snapshot.sh`; отдельный runtime содержит helper и базовый профиль. |
| `Failed to create camera sensor helper for imx519` | В установленной сборке нет helper IMX519. Расчёт усиления не откалиброван для сенсора. Исправляется поддержкой в коде libcamera, а не только YAML. |
| Тёмная картинка | Получена в первом тесте. Проверить освещение, экспозицию и усиление; сначала нужен корректный helper. Не доказано, что темнота вызвана только отсутствием профиля. |
| `loading out-of-tree module taints kernel` | Загружен внешний DKMS-модуль; само сообщение не означает отказ камеры. |
| `disp_cc_mdss_dp_pixel_clk_src ... rcg didn't update` | В предоставленном стеке DP clock/PHY → msm_dp/DRM/fbcon. Это предупреждение настройки дисплея; захват камеры отдельно проверен. |
| В WARNING перечислены imx519/ak7375 | `Modules linked in` — общий список; смотреть функцию и Call trace, а не считать каждый модуль источником. |
| Qt подтягивается при установке | libcamera-tools объединяет консольный cam и графический qcam. По ldd Qt нужен qcam. |
| `qcam: could not connect to display` / ошибка xcb | Обычный SSH не даёт графического сеанса. Запускать qcam в терминале рабочего стола Radxa; по SSH использовать cam/capture.sh. |
| `sudo: a password is required` в SSH агента | Для установки/boot config пользователь выполняет sudo в своём терминале. Захват от radxa уже работает без sudo. |
| Kernel log пуст при journalctl | radxa не состоит в adm/systemd-journal. `sudo -v; bash collect-diagnostics.sh` из терминала пользователя сохраняет полный dmesg через sudo -n. |
| `/dev/video0` не камера | В этом запуске video0/video1 — Iris codec. Искать camera ID через cam -l, media graph через media-ctl. |
| `Camera ... in use` | Проверить, не открыт ли qcam/другой захват. Завершить свой процесс перед новым тестом. Скрипт не завершает чужие процессы. |
| Сборка ругается на другой GCC | На проверенной плате GCC 13.3 против GCC 12.2 сборки ядра; модули собрались и загрузились. Другие предупреждения проверять отдельно. |
| `rsync: command not found` на плате | Для переноса комплекта использовать sync-to-radxa.sh (SSH+tar). |
| SSH пропадает, `Host is down` | В проверенном обрыве плата ушла в s2idle. Полный журнал показал `The system will suspend now!`; отключён AC autosuspend GDM/radxa. |
| `systemctl show systemd-suspend.service` без timestamps | Завершённый unit может быть выгружен; это не доказательство отсутствия сна. Проверять полный journalctl. |
| `v4l2-ctl --set-ctrl=focus_absolute=...` не удерживает фокус | После закрытия lens subdev драйвер паркует линзу. Для прямого V4L2-захвата используйте `focus.py`; для цветного захвата через частную libcamera — `snapshot.sh`, `focus-sweep.sh` или `web-preview.py`, которые задают `LensPosition` через libcamera. |

## Устранённый обрыв SSH: автоматический сон

Полный журнал пользователя доказал:
22:42:41 UTC (01:42:41 МСК) — вход в `s2idle`, NetworkManager отключает Wi-Fi
с причиной `sleeping`; 22:47:10 — выход из сна, 22:47:13 — сеть восстановлена.
Перезагрузки не было. Сам факт `Power save: on` у Wi-Fi не был причиной,
установленной этим журналом.

Пользователь выполнил `sudo bash ~/camera-imx519/disable-autosuspend.sh`.
Для GDM и radxa `sleep-inactive-ac-type` изменён с `suspend` на `nothing`.
Скрипт использует действующую D-Bus-сессию каждого пользователя, если она есть.
Ручной сон и гашение экрана не отключаются. Откат этого запуска:

```sh
sudo bash /var/backups/imx519-autosuspend.9uYvqG2y/restore.sh
```

Исходные 900 секунд таймера остаются, но действие по AC бездействию отключено.
Если обрыв повторится, сохранять новый полный журнал, а не автоматически
приписывать его той же причине.

## Полный диагностический снимок

```sh
cd ~/camera-imx519
sudo -v
bash collect-diagnostics.sh
```

Каталог содержит версии, modinfo/DKMS, media graph, controls, права устройств,
список камер, check.sh и полный dmesg. Ошибки отдельных команд сохранены в
их файлах и `status.tsv`; отсутствие доступа к журналу не означает пустой журнал.
`collect-diagnostics.sh` не запускает захват и не меняет установку.

Для быстрого чтения предупреждения:

```sh
sudo dmesg | grep -A55 -B10 -E 'WARNING:|BUG:|Oops:'
```

## Доступ к устройствам

В проверенной системе пользователь radxa состоит в video и render.
`/dev/dma_heap/system` доступен render; CMA heaps принадлежат root с правами 0600.
RAW и цветной захват от radxa прошли с этими правами. Массовый `chmod 666`
для устройств в нашей настройке не применялся и для проверенных режимов не нужен.

## Профиль и фокус

Не копировать Raspberry Pi tuning JSON в simple IPA: это разные форматы и
конвейеры. Файл YAML отвечает за настройку алгоритмов, sensor helper — за
специфичные для сенсора вычисления, например перевод кодов analogue gain.
AK7375 предоставляет управление линзой; наличие узла Lens не подтверждает AF.

Исходники, на которых основан этот разбор:
[Simple IPA](https://github.com/libcamera-org/libcamera/blob/master/src/ipa/simple/soft_simple.cpp),
[sensor helpers](https://github.com/libcamera-org/libcamera/blob/master/src/ipa/libipa/camera_sensor_helper.cpp).
Точная сборка Radxa отличается от upstream; будущие изменения проверять на ней.
