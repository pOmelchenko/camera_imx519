# Camera package

- Describe the current camera, available files and verified configurations.
  Keep chronology in Git history and dated source/validation records.
- Use `docs/reference/` for module specifications, pinout and driver contracts;
  `docs/vendor/` for original documents and provenance; `docs/development/`
  for development status/acceptance; `docs/guides/` for physically verified recipes.
- Keep one target route under `target/sbc/<board>/` or
  `target/mcu/<board>/`, with its commands, code, patches and results.
  Record the exact board, connector/cable, OS/kernel, driver/device tree,
  userspace and observed capture result.
  Source review, successful build and physical capture are separate statuses.
- Preserve original document bytes, URLs, versions, retrieval dates, licenses
  and hashes. Do not normalize source files under `docs/vendor/`.
- Keep camera-specific SBC/MCU integration here; link to the board repository for
  OS installation, boot firmware and generic board interfaces.
- Add tools/patches only for actual work, organized by target platform. Keep local
  dependency checkouts, builds, captures, caches and logs out of Git.
- Keep the repository useful on its own; do not depend on a parent checkout,
  viewer, recorder or other product source. Use external links for board docs.
