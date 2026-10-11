# IMX519 Autofocus на NVIDIA Jetson

**Статус: путь производителя; экземпляр не проверен.**
Модель Jetson, carrier, JetPack/L4T и драйвер для имеющейся камеры не выбраны.

## Подготовка

1. Зафиксировать модуль/carrier и порт CSI, подобрать шлейф по реальной
   ревизии IMX519 и [распиновке](../../../docs/reference/pinout.md).
2. Выбрать маршрут своего семейства в
   [руководстве IMX519](https://docs.arducam.com/Nvidia-Jetson-Camera/Native-Camera/imx519/):
   Nano/Xavier, Orin Nano/NX или AGX Orin.
   [Orin Nano/NX](https://docs.arducam.com/Nvidia-Jetson-Camera/Nvidia-Jetson-Orin-Series/NVIDIA-Jetson-Orin-Nano%26NX/Quick-Start/)
   отдельно связывает установку native-camera с матрицей JetPack/L4T.
3. Проверить соответствие carrier/BSP, закрепить драйвер, DT, userspace,
   скрипт установки и tuning. Следовать инструкции выбранного release.
4. Получить один кадр; проверить RAW/Bayer или обработанный цвет,
   экспозицию/gain, затем ручной фокус и autofocus.
5. Измерить длительный поток, frame gaps и rolling-shutter timing.
   Сохранить crop, формат и положение фокуса для калибровки.

Таблицы advertised fps относятся к разным вариантам и L4T:
[справочник режимов](../../../docs/reference/module.md#заявленные-режимы).
Рабочую частоту определяет результат конкретной конфигурации.
[Критерии записи результата](../../../docs/development/README.md).
