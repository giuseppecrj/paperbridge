#!/usr/bin/env bash
set -euo pipefail

mode=${1:?mode is required}
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
vm=${EXEDEV_VM:-paperbridge-prod}
target="$vm.exe.xyz"
ssh=(ssh -o BatchMode=yes -o ForwardAgent=no "$target")

[[ $vm =~ ^[a-z][a-z0-9-]*$ ]] || {
    echo "EXEDEV_VM must be a lowercase VM name" >&2
    exit 2
}

case "$mode" in
bootstrap | deploy)
    sha=${PAPERBRIDGE_SHA:?PAPERBRIDGE_SHA is required}
    [[ $sha =~ ^[0-9a-f]{40}$ ]] || {
        echo "PAPERBRIDGE_SHA must be a 40-character lowercase commit SHA" >&2
        exit 2
    }
    exec "${ssh[@]}" "sudo bash -s -- $mode $sha" <"$root/tools/exedev/remote.sh"
    ;;
configure)
    exec "${ssh[@]}" \
        'sudo install -d -m 0700 /etc/paperbridge && sudo install -m 0600 /dev/stdin /etc/paperbridge/paperbridge.env && sudo systemctl restart paperbridge'
    ;;
status)
    exec "${ssh[@]}" 'sudo systemctl status --no-pager paperbridge'
    ;;
logs)
    exec "${ssh[@]}" 'sudo journalctl --no-pager --unit=paperbridge --lines=100'
    ;;
verify)
    exec "${ssh[@]}" 'curl --fail --silent --show-error http://127.0.0.1:3000/health && curl --fail --silent --show-error http://127.0.0.1:3000/ready'
    ;;
probe)
    exec "${ssh[@]}" 'sudo systemd-run --wait --pipe --collect --quiet --property=User=paperbridge --property=Group=paperbridge --property=WorkingDirectory=/opt/paperbridge/current/apps/api --property=Environment=HOME=/var/empty --property=EnvironmentFile=/etc/paperbridge/paperbridge.env --property=NoNewPrivileges=yes --property=CapabilityBoundingSet= --property=AmbientCapabilities= --property=PrivateTmp=yes --property=PrivateDevices=yes --property=ProtectHome=true --property=ProtectSystem=strict --property=ProtectKernelTunables=yes --property=ProtectKernelModules=yes --property=ProtectControlGroups=yes --property=ProtectClock=yes --property=RestrictSUIDSGID=yes --property=LockPersonality=yes --property=RestrictAddressFamilies=AF_UNIX\ AF_INET\ AF_INET6 --property=SystemCallArchitectures=native /opt/paperbridge/current/deploy/exedev/run-node.sh src/main.ts'
    ;;
restart)
    exec "${ssh[@]}" 'sudo systemctl restart paperbridge'
    ;;
rollback)
    exec "${ssh[@]}" 'sudo bash -s -- rollback' <"$root/tools/exedev/remote.sh"
    ;;
reboot)
    exec ssh -o BatchMode=yes -o ForwardAgent=no exe.dev "restart $vm"
    ;;
*)
    echo "unsupported mode: $mode" >&2
    exit 2
    ;;
esac
