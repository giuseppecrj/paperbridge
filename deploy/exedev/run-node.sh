#!/bin/sh
set -eu

: "${PAPERBRIDGE_MQTT_PASSWORD_BASE64:?PAPERBRIDGE_MQTT_PASSWORD_BASE64 is required}"
PAPERBRIDGE_MQTT_PASSWORD=$(printf '%s' "$PAPERBRIDGE_MQTT_PASSWORD_BASE64" | base64 --decode)
export PAPERBRIDGE_MQTT_PASSWORD
exec /usr/local/bin/mise exec -- node --import tsx "$@"
