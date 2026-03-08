# Ademco RS232 Alarm Panel

Custom Home Assistant integration for Ademco alarm panels over RS232.

## HACS Installation

This repository is structured for HACS custom repository installation.

1. In HACS, open the menu and choose `Custom repositories`.
2. Add `https://github.com/joshkurtzman/ademco` as type `Integration`.
3. Search for `Ademco RS232 Alarm Panel` in HACS and install it.
4. Restart Home Assistant.
5. Add the integration from `Settings -> Devices & services`.

## Development Layout

This repo uses HACS `content_in_root`, so the integration files live at the repository root instead of under `custom_components/ademco/`.

## Notes

- The integration currently targets local serial communication.
- If you are testing a feature branch in HACS, HACS will use the repository default branch or published versions. Merge or release branch changes before expecting normal HACS installs to pick them up.
