# Документация Arducam IMX519

## Справочник

- [Модуль, объектив 80° и варианты Arducam](reference/module.md).
- [Распиновка 15 контактов и сопоставление с RPi 22](reference/pinout.md).
- [Драйвер и управление фокусом](reference/drivers.md).

## Запуск на SBC

| SBC | Материал | Статус |
| --- | --- | --- |
| Raspberry Pi | [Стек Arducam и автофокус](../target/sbc/raspberry_pi/README.md) | Есть инструкция производителя; экземпляр не проверен |
| Radxa Dragon Q6A | [Оверлеи, драйверы и демка](../target/sbc/radxa_dragon_q6a/README.md) | Сборка и GPU/DT-тесты пройдены; оверлеи отключены, захват и автофокус не проверены |
| NVIDIA Jetson | [Стек Arducam](../target/sbc/nvidia_jetson/README.md) | Есть инструкция производителя; экземпляр не проверен |

## Микроконтроллеры

[Waveshare ESP32-P4](../target/mcu/waveshare_esp32_p4_wifi6_dev_kit/README.md):
драйвер, сборка и физический захват не проверены.

Подтверждённых аппаратных инструкций в `docs/guides` пока нет.
[Правила оформления результата](development/README.md) отделяют разбор
источников, сборку и физическую проверку.

## Оригиналы

[Каталог источников](vendor/README.md): материалы продавца, два PDF Arducam,
три исходных HTML, справочник Raspberry Pi и манифесты происхождения.
