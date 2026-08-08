#!/usr/bin/env bash
set -euo pipefail

mode=${1:?mode is required}
vm=${EXEDEV_VM:-}
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
remote=/usr/local/libexec/paperbridge-container-remote
remote_source="$root/tools/exedev/container-remote.sh"

[[ -n $vm ]] || {
    echo "EXEDEV_VM is required" >&2
    exit 2
}
[[ $vm =~ ^[a-z][a-z0-9-]*$ ]] || {
    echo "EXEDEV_VM must be a lowercase VM name" >&2
    exit 2
}
[[ $vm != paperbridge-prod ]] || {
    echo "the existing production VM is forbidden" >&2
    exit 2
}

target="$vm.exe.xyz"
ssh=(ssh -o BatchMode=yes -o ForwardAgent=no "$target")
control_ssh=(ssh -o BatchMode=yes -o ForwardAgent=no exe.dev)

render() {
    printf 'DRY RUN:'
    printf ' %q' "$@"
    printf '\n'
}

invoke() {
    if [[ ${PAPERBRIDGE_EXEDEV_DRY_RUN:-0} == 1 ]]; then
        render "$@"
        return
    fi
    "$@"
}

require_confirmation() {
    [[ ${EXEDEV_CONFIRM_VM:-} == "$vm" ]] || {
        echo "EXEDEV_CONFIRM_VM must match EXEDEV_VM" >&2
        exit 2
    }
}

require_sha() {
    sha=${PAPERBRIDGE_SHA:-}
    [[ $sha =~ ^[0-9a-f]{40}$ ]] || {
        echo "PAPERBRIDGE_SHA must be a 40-character lowercase commit SHA" >&2
        exit 2
    }
}

require_digest() {
    digest=${PAPERBRIDGE_IMAGE_DIGEST:-}
    [[ $digest =~ ^sha256:[0-9a-f]{64}$ ]] || {
        echo "PAPERBRIDGE_IMAGE_DIGEST must be a sha256 image digest" >&2
        exit 2
    }
}

case "$mode" in
bootstrap)
    require_confirmation
    require_sha
    invoke "${ssh[@]}" \
        'test -d /exe.dev && test ! -e /opt/paperbridge/current && test ! -e /etc/systemd/system/paperbridge.service && test ! -e /var/lib/paperbridge-container/bootstrap-complete'
    if [[ ${PAPERBRIDGE_EXEDEV_DRY_RUN:-0} == 1 ]]; then
        render "${ssh[@]}" "sudo install -d -m 0755 /usr/local/libexec && sudo install -m 0700 /dev/stdin $remote" "<" "$remote_source"
    else
        "${ssh[@]}" \
            "sudo install -d -m 0755 /usr/local/libexec && sudo install -m 0700 /dev/stdin $remote" \
            <"$remote_source"
    fi
    invoke "${ssh[@]}" sudo "$remote" bootstrap "$sha" "$vm"
    ;;
build)
    require_confirmation
    require_sha
    invoke "${ssh[@]}" sudo "$remote" build "$sha"
    ;;
deploy)
    require_confirmation
    require_digest
    invoke "${ssh[@]}" sudo "$remote" deploy "$digest"
    ;;
credential | rotate)
    require_confirmation
    password=${PAPERBRIDGE_MQTT_PASSWORD:-}
    [[ -n $password ]] || {
        echo "PAPERBRIDGE_MQTT_PASSWORD is required" >&2
        exit 2
    }
    unset PAPERBRIDGE_MQTT_PASSWORD
    if [[ ${PAPERBRIDGE_EXEDEV_DRY_RUN:-0} == 1 ]]; then
        render "${ssh[@]}" sudo "$remote" "$mode"
        printf 'DRY RUN: [credential bytes via SSH stdin]\n'
    else
        printf '%s' "$password" | "${ssh[@]}" sudo "$remote" "$mode"
    fi
    ;;
status | logs | verify)
    invoke "${ssh[@]}" sudo "$remote" "$mode"
    ;;
probe | restart | rollback)
    require_confirmation
    invoke "${ssh[@]}" sudo "$remote" "$mode"
    ;;
reboot)
    require_confirmation
    invoke "${control_ssh[@]}" restart "$vm"
    ;;
*)
    echo "unsupported mode: $mode" >&2
    exit 2
    ;;
esac
