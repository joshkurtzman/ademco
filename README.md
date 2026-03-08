# Ademco RS232 Alarm Panel

Custom Home Assistant integration for Ademco alarm panels over RS232.

## HACS Installation

This repository is structured for HACS custom repository installation.

1. In HACS, open the menu and choose `Custom repositories`.
2. Add `https://github.com/joshkurtzman/ademco` as type `Integration`.
3. Search for `Ademco RS232 Alarm Panel` in HACS and install it.
4. Restart Home Assistant.
5. Add the integration from `Settings -> Devices & services`.

## Configuration

This integration is configured from the Home Assistant UI only.

- Add it from `Settings -> Devices & services`.
- Reconfigure it later from the integration card.
- Remove any legacy `ademco:` block from `configuration.yaml`.

## Development Layout

This repo uses HACS `content_in_root`, so the integration files live at the repository root instead of under `custom_components/ademco/`.

## Local Container Test

If you want to test this branch on a laptop with Docker without touching your live Home Assistant instance:

1. Check out this repository on your laptop.
2. Run `./scripts/run_local_ha_container.sh`.
3. Open `http://localhost:8129`.
4. Inspect the generated config under `.tmp/ha-test/config`.

The script copies the current branch into a temporary Home Assistant config as `custom_components/ademco` and starts a disposable Home Assistant container.

To compare registry changes before and after a migration:

```bash
python3 ./scripts/compare_registry.py \
  before/core.entity_registry \
  after/core.entity_registry \
  --before-device-registry before/core.device_registry \
  --after-device-registry after/core.device_registry
```

## Notes

- The integration currently targets local serial communication.
- If you are testing a feature branch in HACS, HACS will use the repository default branch or published versions. Merge or release branch changes before expecting normal HACS installs to pick them up.
- Remaining migration and cleanup tasks are tracked in [TODO.md](TODO.md).
