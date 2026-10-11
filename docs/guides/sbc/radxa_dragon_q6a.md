# IMX519: проверенный захват на Q6A CAM3

Конфигурация из сохранённых проверок сентября 2026 года: Radxa Dragon Q6A / QCS6490,
Ubuntu 24.04.4 LTS, ядро `7.0.11-6-qcom`, CAM3/J7, две линии CSI,
драйверы IMX519 и AK7375, rsetup 0.4.28, overlays 0.2.30.
Владелец указал Arducam autofocus-модуль с объективом 80°; точный SKU,
ревизия PCB и полная маркировка кабеля не зафиксированы.

Исходники, хеши и точные версии находятся в [пакете подключения](../../../target/sbc/radxa_dragon_q6a/README.md)
и его [provenance](../../../target/sbc/radxa_dragon_q6a/docs/PROVENANCE.md).
Там же описаны установка драйверов/overlay, частная libcamera, диагностика и
восстановление. ОС и загрузка принадлежат [репозиторию Q6A](https://github.com/pOmelchenko/radxa_dragon_q6a).

## Команды на рабочем компьютере

Из корня отдельного репозитория `camera_imx519`:

```sh
export IMX519_SSH_TARGET='radxa@<board-address>'
bash target/sbc/radxa_dragon_q6a/sync-to-radxa.sh
```

Комплект копируется в `~/camera-imx519` на плате. Синхронизация исходников
сохраняет существующие runtime и захваты; сборка и установка выполняются
отдельными командами из README подключения.

## Захват на уже настроенной плате

```sh
cd ~/camera-imx519
IMX519_RUNTIME="$PWD/runtime/preview" bash capture.sh raw 3
IMX519_RUNTIME="$PWD/runtime/preview" bash snapshot-af.sh auto
IMX519_RUNTIME="$PWD/runtime/preview" bash snapshot-af.sh continuous
IMX519_RUNTIME="$PWD/runtime/preview" bash stability.sh rgb 9000
```

Сохранённый `runtime/preview` — контрастный `imx519.af1` для штатного CAMSS.
Результат исходной проверки: RGB 1920×1080, 9000 кадров / 300 секунд,
около 30 fps без пропусков; RAW 1920×1080 и ручное изменение резкости также
проверены. [Журнал](../../../target/sbc/radxa_dragon_q6a/docs/WORKLOG.md) и
[компактные результаты](../../../target/sbc/radxa_dragon_q6a/docs/evidence/) сохраняют
исходные даты и границы проверки. Это перенесённые результаты, не новый запуск.

## Экспериментальный PDAF

`runtime/current` с `imx519.pdaf5` требует временного экспериментального CAMSS.
Короткие RAW/phase проверки пяти режимов и Auto/Continuous на одной освещённой
неподвижной сцене сохранены в [исследовании](../../../target/sbc/radxa_dragon_q6a/research/pdaf-bringup.md).
Длительная работа, перенаводка и recovery остаются в
[задаче 00214](../../development/00214-qualify-q6a-imx519-pdaf.md).
[Отложенная пауза PDAF](../../development/q6a-pdaf-deferred-pause.md) имеет открытое замечание.
Цветовая/оптическая калибровка, новый kernel ABI и Raspberry Pi/Jetson/MCU
этими проверками не квалифицированы.
