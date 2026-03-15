# Ademco Integration TODO

## Migration

- Verify entity and device registry migration stays stable for existing installs during upgrades.
- Decide whether to keep or remove the boot warning for users who still have an `ademco:` block in `configuration.yaml`.

## Config Flow

- Replace the JSON text fields in `config_flow.py` with a friendlier Home Assistant UI flow.
- Add validation that catches malformed zone and garage door definitions before entry creation.
- Consider options flow support if reconfigure is not enough for future editing needs.

## Runtime and Lifecycle

- Reduce or eliminate the blocking import warning shown during startup.
- Continue hardening the panel lifecycle and reconnect behavior.
- Review shutdown and task cleanup so the integration does not delay Home Assistant stop/restart.

## Entity and Device UX

- Replace the serial-device-path entry title and panel device name with a friendlier default name.
- Revisit device metadata and naming so the panel device and attached entities present cleanly in the UI.
- Confirm garage door state transitions are as good as they can be with a single open/closed sensor.

## Dashboard and UI

- Export or document any desired Lovelace dashboard changes separately from the integration repo.
- Keep the "Doors and Windows" dashboard behavior aligned with entity state semantics used by the integration.
