# Q6A autofocus migration from lidar_viewer

Дата переноса: 2026-10-12. Источник — ветка
[`agent/imx519-q6a-autofocus`](https://github.com/pOmelchenko/lidar_viewer/tree/ab8420b705d62f583f82532dbcb98cb3a87710d4)
репозитория `pOmelchenko/lidar_viewer`, HEAD `ab8420b705d62f583f82532dbcb98cb3a87710d4`.
Назначение — отдельная ветка `agent/imx519-q6a-autofocus` в `pOmelchenko/camera_imx519`,
от `main` `9cf2e24bdec129c5840c47c085ef5c388325bb13`.

## Состав и история

Все 12 исходных коммитов представлены отдельными коммитами с исходными авторами,
author dates и subjects. `Source-Repository`, `Source-Commit`, `Source-Branch`
связывают каждый коммит с оригиналом; [карта коммитов](2026-10-12-q6a-commit-map.json)
позволяет проверить соответствие. Commit SHA изменились из-за другого родителя и путей.

| Исходный путь | Новый путь |
| --- | --- |
| `hardware/camera/imx519/q6a/` | `target/sbc/radxa_dragon_q6a/` |
| `hardware/camera/test-charts/` | `target/sbc/radxa_dragon_q6a/test-charts/` |
| `docs/wiki/internal/backlog/00214-qualify-q6a-imx519-pdaf.md` | `docs/development/00214-qualify-q6a-imx519-pdaf.md` |

Перенесено 125 файлов: 122 побитово идентичны; три поддерживаемых
Markdown-документа адаптированы к новому размещению. Драйверы, патчи, исполняемые
скрипты, original evidence, research snapshots, изображения и PDF не изменены.
[Манифест файлов](2026-10-12-q6a-files.json) записывает исходный blob, file mode,
старый и новый SHA-256 каждого перенесённого файла. Исторический WORKLOG сохраняет
прежний путь как запись своего времени; действующие команды используют отдельный repo.

Добавлены IMX519-разделы исторической записи короткого захвата из board package.
Ссылки внутри этого извлечения переведены на локальные camera paths; source URL,
полный source SHA-256 и датированные утверждения сохранены. Общие изменения
инвентаря платы, AR0234/IMX296, viewer/wiki indexes и product-level planning
остаются в исходном repository; самостоятельный комплект от них не зависит.
Базовые vendor documents нового repository сохранены без изменений.

## Текущее состояние

Подтверждённые RAW/RGB, ручной фокус, CDAF и короткий PDAF описаны в
[README подключения](../../../target/sbc/radxa_dragon_q6a/README.md) и
[проверенном рецепте](../../guides/sbc/radxa_dragon_q6a.md).
Квалификация PDAF [00214](../00214-qualify-q6a-imx519-pdaf.md) остаётся deferred P2;
[замечание об отложенной паузе](../q6a-pdaf-deferred-pause.md) перенесено как open.
Новых сборок kernel/libcamera, deployment и физических запусков при переносе нет.

Viewer `origin/main` уже подключает `hardware/camera/imx519` как git submodule
с pin `9cf2e24`. Этот перенос публикует отдельную рабочую ветку; интеграционное
обновление pin относится к принятию camera branch.

## Проверки переноса

Результаты локальных проверок фиксируются в
[validation.json](2026-10-12-q6a-validation.json): source/destination file hashes
и modes, все 12 commit mappings/authors, Bash/Python syntax, JSON artifacts,
девять driver/chart checksum bindings и локальные Markdown links.
Stored patches и исходные console captures сохраняют существующие whitespace
findings; новый migration/documentation delta проверяется отдельно.
