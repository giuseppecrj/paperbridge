#!/bin/sh
set -eu

: "${PAPERBRIDGE_MQTT_PASSWORD_BASE64:?PAPERBRIDGE_MQTT_PASSWORD_BASE64 is required}"
PAPERBRIDGE_MQTT_PASSWORD=$(printf '%s' "$PAPERBRIDGE_MQTT_PASSWORD_BASE64" | base64 --decode)
unset PAPERBRIDGE_MQTT_PASSWORD_BASE64
export PAPERBRIDGE_MQTT_PASSWORD
cd /opt/paperbridge/current/apps/api
exec /opt/paperbridge/current/.mise/installs/node/*/bin/node --import tsx "$@"
