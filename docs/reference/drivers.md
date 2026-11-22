# Драйвер и автофокус IMX519

[Arducam](https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/16MP-IMX519/)
описывает программные маршруты Raspberry Pi и Jetson. На Q6A сохранена [конфигурация CAM3](../guides/sbc/radxa_dragon_q6a.md) с проверенным цветным потоком. Для Q6A закреплены исходники сенсора и привода. Рабочий комплект libcamera и tuning для автофокуса пока не определён.

## Raspberry Pi

Для autofocus-моделей руководство использует собственные пакеты libcamera
и приложения Arducam, затем вручную включает `imx519` в `config.txt`.
Распространение идёт через
[Arducam-Pivariety-V4L2-Driver](https://github.com/ArduCAM/Arducam-Pivariety-V4L2-Driver).
Название установщика не определяет тип интерфейса этого native CSI-модуля.

Поддержка сенсора в ядре, управление приводом объектива и алгоритм автофокуса
должны быть согласованы. Overlay сам по себе не доказывает работоспособность
фокуса. Пример `vcm=off` относится к fixed-focus и отключает нужный здесь привод.
Версию скрипта, скачанные пакеты и tuning нужно закрепить для воспроизводимости.
Конкретные настройки: [разработка Raspberry Pi](../../target/sbc/raspberry_pi/README.md).

## NVIDIA Jetson

[Руководство IMX519](https://docs.arducam.com/Nvidia-Jetson-Camera/Native-Camera/imx519/)
разделяет Nano/Xavier, Orin Nano/NX и AGX Orin.
[Orin Nano/NX](https://docs.arducam.com/Nvidia-Jetson-Camera/Nvidia-Jetson-Orin-Series/NVIDIA-Jetson-Orin-Nano%26NX/Quick-Start/)
ссылается на матрицу JetPack/L4T и установку native-camera драйвера.
Carrier, разъём, BSP и release определяют путь установки; проверенного
проектного сочетания нет. Захват, ISP и управление фокусом проверяются вместе.
[Подготовка Jetson](../../target/sbc/nvidia_jetson/README.md).

## Другие SBC

Pi overlay и NVIDIA integration не задают путь Qualcomm CAMSS.
Для Q6A подготовлены модули IMX519 и AK7375, оверлеи CAMSS и пробный захват V4L2. Для текущего установщика нужны проверка захвата и отдельный тест фокуса. [Комплект Q6A](../../target/sbc/radxa_dragon_q6a/README.md).
Работа на ESP32-P4 также не подтверждена; наличие CSI у хоста не определяет
поддержку IMX519 или автофокуса.

Частоты из каталога производителя остаются отдельными
[заявленными режимами](module.md#заявленные-режимы). Первый результат должен
содержать фактические размеры, Bayer/разрядность, crop, rate, положение фокуса
и версии всех компонентов.

Источники и датированные оригиналы: [каталог](../vendor/README.md),
[сохранённое руководство IMX519](../vendor/arducam-imx519-guide-2026-10-11.html).
