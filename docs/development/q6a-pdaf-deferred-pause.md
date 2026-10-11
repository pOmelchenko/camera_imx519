---
type: development-task
status: open
updated: 2026-10-12
---

# Honor deferred pause after Continuous PDAF focus

Перенесённое открытое [замечание PR 54](https://github.com/pOmelchenko/lidar_viewer/pull/54#discussion_r4177522405),
приоритет P2. [Исходный PDAF-патч](../../target/sbc/radxa_dragon_q6a/libcamera/pdaf-simple.patch)
перенесён без изменения поведения.

Во время фазового сканирования `AfPauseDeferred` устанавливает `pauseDeferred_`.
При фазовом успехе алгоритм переходит в `Stage::Monitor`, но не выставляет
`paused_`, в отличие от контрастного `finishStep()`. Метаданные остаются
`AfPauseStatePausing`, а мониторинг и повторное наведение могут продолжаться.

Исправление должно выполнять отложенную паузу в терминальном focused-состоянии
фазового AF. Проверить PauseDeferred во время Phase, переход в Paused после
успеха, отсутствие нового движения линзы до Resume, Immediate/Resume и
контрастный fallback. Отдельно проверить сборку закреплённой частной libcamera.
Физические проверки и длительные режимы остаются в
[задаче 00214](00214-qualify-q6a-imx519-pdaf.md).

Этот перенос не исправляет дефект и не утверждает новый build или аппаратный PASS.
