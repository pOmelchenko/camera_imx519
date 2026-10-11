# Оригинальные материалы IMX519

Каталог хранит исходные документы Arducam, Raspberry Pi и материалы
продавца с происхождением и SHA-256. Байты оригиналов сохранены.
Текущее состояние камеры: [README](../../README.md).

## Материалы продавца

Переданы владельцем 23 сентября 2026 года для autofocus-камеры 80°.
[Товар/SKU](https://aliexpress.ru/item/1005007908489775.html?sku_id=12000042797436463):
`1005007908489775` / `12000042797436463`.
Точный артикул Arducam и состав комплекта по каталогу не подтверждены.

| Файл | Содержание |
| --- | --- |
| [Описание](aliexpress-description.md) | Переданный текст: Jetson rates и FAQ; таблицы после Specifications во входе нет |
| [Введение, вариант 80°](product-introduction.png) | PDAF/CDAF, 80° и корпус |
| [Модуль с двух сторон](module-front-and-back.png) | UC-875 Rev.B, ArduCam, 16MP autofocus, разъём |
| [Пример Jetson](jetson-connection-example.png) | Иллюстрация соединения с платой и штативом |
| [Пример Raspberry Pi](raspberry-pi-connection-example.png) | Иллюстрация соединения с платой и штативом |
| [Объектив и шлейф](module-and-cable-details.png) | Модуль, объектив, кабель и детали Pi connection |

Это рекламные изображения; они не фиксируют рабочую установку владельца.
[sources.json](sources.json) сохраняет имена вложений, размеры и хеши.

## PDF Arducam

| Оригинал | Версия и содержание |
| --- | --- |
| [Product Brief](arducam-product-brief.pdf), 6 страниц | Cover September 2021; без явной ревизии; стр. 3 — параметры, стр. 4 — чертёж PCB |
| [Getting Started](arducam-start-guide.pdf), 7 страниц | Cover September 2021; metadata B0371/B0371C, modification 2023-03-21; стр. 2–4 — сборка/кабель, стр. 5 — платформенные ссылки |

Получены 23 сентября 2026 года. URL, redirects, metadata, размеры и хеши
сохранены в [sources.json](sources.json). Это документы модуля Arducam;
полного Sony register datasheet в пакете нет.

## Справочники разъёмов

Получены 11 октября 2026 года:

| Оригинал | Область применения |
| --- | --- |
| [Arducam CSI pinout HTML](arducam-csi-pinout-2026-10-11.html) | Стандартные сигналы 15/22, шаг и derived upper-contact connector |
| [Arducam IMX519 HTML](arducam-imx519-guide-2026-10-11.html) | Две линии CSI, autofocus stack и противоречивые B0371 `22pin/Top` / `15/Bottom` |
| [Arducam connection HTML](arducam-csi-connection-guide-2026-10-11.html) | Соприкосновение металла кабеля и разъёма; внешние рисунки не включены |
| [Raspberry Pi AsciiDoc](raspberry-pi-camera-advanced-2026-10-11.adoc) | Стандартный хост 15/22; commit `62ba0a0c2dd5030fe9b19458fa9bd174a451f79b`, Raspberry Pi Ltd, CC BY-SA 4.0 |

HTML сохраняет response-body; внешние изображения, JS и CSS не включены.
У HTML Arducam нет явно указанной версии, поэтому используется дата снимка.
[pinout-sources.json](pinout-sources.json) содержит URL, даты, версии,
размеры, scope, хеши и ссылку на лицензию Raspberry Pi.
Разбор: [распиновка](../reference/pinout.md).

## Онлайн-ссылки

В [sources.json](sources.json) также сохранена область просмотра страниц
B0371/B0500, Jetson IMX519 и Orin Nano/NX. Локального HTML этих страниц нет.
[B0371](https://www.arducam.com/blog/product/imx519-autofocus-camera-module-for-raspberry-pi-arducam-b0371/)
и [B0500](https://www.arducam.com/arducam-imx519-pdaf-cdaf-autofocus-camera-module-for-raspberry-pi-nvidiar-jetson-orin-series.html)
описывают разные варианты;
[различия характеристик](../reference/module.md) и
[применимость драйверов](../reference/drivers.md) сохранены в справочнике.

## Проверка оригиналов

Из этого каталога:

```sh
# macOS
shasum -a 256 -c SHA256SUMS
# Linux
sha256sum -c SHA256SUMS
```

[SHA256SUMS](SHA256SUMS) покрывает 12 оригиналов. Манифесты сохраняют свои
первоначальные даты и поля; исходные уведомления и права остаются у авторов.
