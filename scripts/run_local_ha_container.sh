#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TEST_ROOT="${ADEMCO_TEST_ROOT:-${REPO_ROOT}/.tmp/ha-test}"
CONFIG_DIR="${TEST_ROOT}/config"
CONTAINER_NAME="${HA_CONTAINER_NAME:-ademco-ha-test}"
HA_IMAGE="${HA_IMAGE:-ghcr.io/home-assistant/home-assistant:stable}"
HA_PORT="${HA_PORT:-8129}"

mkdir -p "${CONFIG_DIR}/custom_components/ademco"
rm -rf "${CONFIG_DIR}/custom_components/ademco"
mkdir -p "${CONFIG_DIR}/custom_components/ademco"

(
    cd "${REPO_ROOT}"
    tar \
        --exclude=.git \
        --exclude=.tmp \
        --exclude=__pycache__ \
        --exclude=.DS_Store \
        --exclude=scripts \
        -cf - .
) | (
    cd "${CONFIG_DIR}/custom_components/ademco"
    tar -xf -
)

if [ ! -f "${CONFIG_DIR}/configuration.yaml" ]; then
    cp "${SCRIPT_DIR}/test-config/configuration.yaml" "${CONFIG_DIR}/configuration.yaml"
fi

docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

docker run \
    --detach \
    --name "${CONTAINER_NAME}" \
    --restart unless-stopped \
    --publish "${HA_PORT}:8123" \
    --volume "${CONFIG_DIR}:/config" \
    "${HA_IMAGE}"

echo "Home Assistant test container started."
echo "Container: ${CONTAINER_NAME}"
echo "URL: http://localhost:${HA_PORT}"
echo "Config: ${CONFIG_DIR}"
echo
echo "Useful follow-up commands:"
echo "  docker logs -f ${CONTAINER_NAME}"
echo "  docker exec -it ${CONTAINER_NAME} bash"
echo "  docker rm -f ${CONTAINER_NAME}"
