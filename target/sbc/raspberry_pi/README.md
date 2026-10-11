# IMX519 Autofocus на Raspberry Pi

**Статус: путь производителя; экземпляр не проверен.**
Рассматривается autofocus-модуль 80°. Конкретная Pi, ОС/ядро,
версия пакетов и рабочий результат пока не зафиксированы.

## Подготовка и настройка

1. Определить ревизию IMX519, число контактов и сторону контактов;
   выбрать кабель по [распиновке](../../../docs/reference/pinout.md).
   Для показанного 15-контактного UC-875 Rev.B используется 15-pin либо
   проверенный 15→22 адаптер к нужному хосту.
2. Выбрать свою модель и ОС в
   [руководстве Arducam](https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/16MP-IMX519/#guide-for-autofocus-cameras).
   Сохранённая [версия HTML](../../../docs/vendor/arducam-imx519-guide-2026-10-11.html)
   фиксирует инструкцию производителя; не является проверенной связкой пакетов.
3. Закрепить скрипт из Arducam-Pivariety-V4L2-Driver и скачиваемые пакеты.
   Для autofocus путь Arducam устанавливает `libcamera_dev` и `libcamera_apps`.
4. В `config.txt` отключить `camera_auto_detect` и включить `imx519`:

   ```ini
   camera_auto_detect=0
   dtoverlay=imx519
   ```

   Для нужного cam0 применяется вариант `dtoverlay=imx519,cam0`.
   Bookworm/Trixie: `/boot/firmware/config.txt`; Bullseye: `/boot/config.txt`.
   Использовать раздел своей Pi из руководства. `vcm=off` относится
   к fixed-focus и отключает привод нужного здесь автофокуса.
5. После перезапуска перечислить камеры и получить кадр. Руководство
   использует `rpicam-still` для новых ОС, `libcamera-still` для Bullseye.
   Проверить отдельно ручное управление фокусом и автофокус.
6. Записать negotiated mode, crop, RAW/Bayer, экспозицию, sustained fps
   и положение фокуса. Для калибровки зафиксировать фокус и проверить
   геометрию после его изменения.

Раздел autofocus в источнике обязателен: настройки fixed-focus не описывают
эту камеру. Overlay сам по себе не подтверждает управление объективом.
[Критерии результата](../../../docs/development/README.md),
[границы стека](../../../docs/reference/drivers.md).
