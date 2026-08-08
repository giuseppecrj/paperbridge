#!/usr/bin/env bash
set -euo pipefail

mode=${1:?mode is required}
value=${2:-}
secondary=${3:-}
prefix=${PAPERBRIDGE_EXEDEV_ROOT:-}
app_root="$prefix/opt/paperbridge-container"
repository="$app_root/repository"
builds="$app_root/builds"
state="$prefix/var/lib/paperbridge-container"
config_dir="$prefix/etc/paperbridge-container"
unit_path="$prefix/etc/systemd/system/paperbridge-container.service"
credential_store="$prefix/etc/credstore.encrypted"
systemd_creds=${PAPERBRIDGE_SYSTEMD_CREDS_BIN:-systemd-creds}
systemd_run=${PAPERBRIDGE_SYSTEMD_RUN_BIN:-systemd-run}

fail() {
    echo "$1" >&2
    exit 1
}

require_sha() {
    [[ $value =~ ^[0-9a-f]{40}$ ]] || fail "expected a 40-character lowercase commit SHA"
}

require_digest() {
    [[ $value =~ ^sha256:[0-9a-f]{64}$ ]] || fail "expected a sha256 image digest"
}

write_state() {
    local path=$1
    local content=$2
    local temporary
    temporary=$(mktemp "$path.XXXXXX")
    trap 'rm -f "$temporary"' EXIT
    printf '%s\n' "$content" >"$temporary"
    chmod 0600 "$temporary"
    mv "$temporary" "$path"
    trap - EXIT
}

read_current_digest() {
    local line
    [[ -f "$state/current-image.env" ]] || return 1
    line=$(cat "$state/current-image.env")
    [[ $line =~ ^PAPERBRIDGE_IMAGE=(sha256:[0-9a-f]{64})$ ]] ||
        fail "current image state is invalid"
    printf '%s\n' "${BASH_REMATCH[1]}"
}

validate_image() {
    local digest=$1
    local record
    record="$state/images/${digest#sha256:}.sha"
    [[ -f "$record" ]] || fail "image digest was not built by this workflow"
    release_sha=$(cat "$record")
    [[ $release_sha =~ ^[0-9a-f]{40}$ ]] || fail "image build record is invalid"
    release="$builds/$release_sha"
    [[ -d "$release" ]] || fail "image build checkout is missing"
    [[ $(git -C "$release" rev-parse HEAD) == "$release_sha" ]] ||
        fail "image build checkout no longer matches its record"
    docker image inspect "$digest" >/dev/null
}

install_release() {
    local digest=$1
    local vm host template temporary
    validate_image "$digest"
    [[ -f "$release/deploy/exedev/paperbridge-container.service" ]] ||
        fail "image release has no container systemd unit"
    template="$release/deploy/exedev/paperbridge-container.env.template"
    [[ -f "$template" ]] || fail "image release has no environment template"
    vm=$(sed -n 's/^vm=//p' "$state/bootstrap-complete")
    [[ $vm =~ ^[a-z][a-z0-9-]*$ ]] || fail "bootstrapped VM state is invalid"
    host="$vm.exe.xyz"

    install -d -m 0755 "$(dirname "$unit_path")"
    install -d -m 0700 "$config_dir"
    install -m 0644 "$release/deploy/exedev/paperbridge-container.service" "$unit_path"
    temporary=$(mktemp "$config_dir/api.env.XXXXXX")
    trap 'rm -f "$temporary"' EXIT
    sed "s/@EXEDEV_HOST@/$host/g" "$template" >"$temporary"
    [[ -s "$temporary" ]] || fail "rendered API environment is empty"
    ! grep -q '@EXEDEV_HOST@' "$temporary" || fail "API environment placeholder was not rendered"
    chmod 0644 "$temporary"
    mv "$temporary" "$config_dir/api.env"
    trap - EXIT
}

read_previous_digest() {
    local line
    [[ -f "$state/previous-image" ]] || return 1
    line=$(cat "$state/previous-image")
    [[ $line =~ ^sha256:[0-9a-f]{64}$ ]] || fail "previous image state is invalid"
    printf '%s\n' "$line"
}

restore_activation() {
    local old_current=$1
    local old_previous=$2
    if [[ -n $old_current ]]; then
        write_state "$state/current-image.env" "PAPERBRIDGE_IMAGE=$old_current"
        if [[ -n $old_previous ]]; then
            write_state "$state/previous-image" "$old_previous"
        else
            rm -f "$state/previous-image"
        fi
        install_release "$old_current"
        systemctl daemon-reload || true
        systemctl restart paperbridge-container.service || true
    else
        systemctl disable --now paperbridge-container.service || true
        rm -f "$state/current-image.env" "$state/previous-image"
        rm -f "$unit_path" "$config_dir/api.env"
        systemctl daemon-reload || true
    fi
}

activate_image() {
    local target=$1
    local old_current=$2
    local old_previous=$3
    local rollback=$4
    local failure=$5
    install_release "$target"
    if [[ -n $rollback ]]; then
        write_state "$state/previous-image" "$rollback"
    else
        rm -f "$state/previous-image"
    fi
    write_state "$state/current-image.env" "PAPERBRIDGE_IMAGE=$target"
    if ! systemctl daemon-reload ||
        ! systemctl enable paperbridge-container.service ||
        ! systemctl restart paperbridge-container.service; then
        restore_activation "$old_current" "$old_previous"
        fail "$failure; previous image restored"
    fi
}

prune_release_images() {
    local current=$1
    local previous=$2
    local record digest
    shopt -s nullglob
    for record in "$state/images/"*.sha; do
        digest="sha256:$(basename "$record" .sha)"
        if [[ $digest != "$current" && $digest != "$previous" ]]; then
            docker image rm "$digest"
            rm -f "$record"
        fi
    done
    shopt -u nullglob
}

record_image() {
    local digest=$1
    local sha=$2
    local record temporary
    record="$state/images/${digest#sha256:}.sha"
    temporary=$(mktemp "$record.XXXXXX")
    trap 'rm -f "$temporary"' EXIT
    printf '%s\n' "$sha" >"$temporary"
    chmod 0600 "$temporary"
    mv "$temporary" "$record"
    trap - EXIT
}

install_credential() {
    local action=$1
    local credential temporary backup=
    credential="$credential_store/paperbridge-mqtt-password"
    [[ -f "$state/bootstrap-complete" ]] || fail "container VM is not bootstrapped"
    check_encrypted_credentials

    if [[ $action == credential ]]; then
        [[ ! -e "$credential" ]] || fail "credential already exists; use rotate"
    else
        [[ -f "$credential" ]] || fail "credential is not provisioned"
        backup=$(mktemp "$credential_store/paperbridge-mqtt-password.previous.XXXXXX")
        cp "$credential" "$backup"
        chmod 0600 "$backup"
    fi

    temporary=$(mktemp "$credential_store/paperbridge-mqtt-password.XXXXXX")
    trap 'rm -f "$temporary" "$backup"' EXIT
    "$systemd_creds" encrypt --name=mqtt-password - "$temporary" >/dev/null 2>&1 ||
        fail "MQTT credential encryption failed"
    [[ -s "$temporary" ]] || fail "MQTT credential encryption failed"
    "$systemd_run" \
        --wait \
        --pipe \
        --collect \
        --quiet \
        --unit="paperbridge-mqtt-credential-check-$$" \
        --property="LoadCredentialEncrypted=mqtt-password:$temporary" \
        /bin/sh -c 'test -s "$CREDENTIALS_DIRECTORY/mqtt-password"' \
        >/dev/null 2>&1 ||
        fail "MQTT credential validation failed"
    chmod 0600 "$temporary"
    mv "$temporary" "$credential"

    if [[ $action == rotate ]]; then
        if ! systemctl restart paperbridge-container.service; then
            mv "$backup" "$credential"
            systemctl restart paperbridge-container.service || true
            fail "credential rotation failed; previous credential restored"
        fi
        rm -f "$backup"
        printf 'credential_rotated=true\n'
    else
        printf 'credential_provisioned=true\n'
    fi
    trap - EXIT
}

check_encrypted_credentials() {
    command -v "$systemd_creds" >/dev/null 2>&1 ||
        fail "encrypted systemd credentials are unavailable"
    command -v "$systemd_run" >/dev/null 2>&1 ||
        fail "encrypted systemd credentials are unavailable"

    install -d -m 0700 "$credential_store"
    "$systemd_creds" setup >/dev/null 2>&1 ||
        fail "encrypted systemd credentials are unavailable"

    local probe
    probe=$(mktemp "$credential_store/paperbridge-check.XXXXXX")
    trap 'rm -f "$probe"' EXIT
    printf 'paperbridge-credential-check' |
        "$systemd_creds" encrypt --name=paperbridge-check - "$probe" >/dev/null 2>&1 ||
        fail "encrypted systemd credentials are unavailable"
    "$systemd_run" \
        --wait \
        --pipe \
        --collect \
        --quiet \
        --unit="paperbridge-credential-check-$$" \
        --property="LoadCredentialEncrypted=paperbridge-check:$probe" \
        /bin/sh -c 'test -s "$CREDENTIALS_DIRECTORY/paperbridge-check"' \
        >/dev/null 2>&1 ||
        fail "encrypted systemd credentials are unavailable"
    rm -f "$probe"
    trap - EXIT
}

case "$mode" in
credential-check)
    check_encrypted_credentials
    ;;
bootstrap)
    require_sha
    [[ $secondary =~ ^[a-z][a-z0-9-]*$ ]] || fail "expected an explicit lowercase VM name"
    [[ -d "$prefix/exe.dev" ]] || fail "target is not a fresh exeuntu VM"
    [[ ! -e "$prefix/opt/paperbridge/current" ]] || fail "legacy production deployment detected"
    [[ ! -e "$prefix/etc/systemd/system/paperbridge.service" ]] || fail "legacy production deployment detected"
    [[ ! -e "$state/bootstrap-complete" ]] || fail "container VM is already bootstrapped"

    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install --yes ca-certificates curl git docker.io
    systemctl enable --now docker.service
    docker info >/dev/null
    check_encrypted_credentials

    install -d -m 0755 "$app_root" "$builds"
    install -d -m 0700 "$state" "$state/images" "$prefix/etc/paperbridge-container"
    if [[ ! -d "$repository/.git" ]]; then
        git clone https://github.int.exe.xyz/giuseppecrj/paperbridge.git "$repository"
    fi
    git -C "$repository" fetch --quiet --depth=1 origin "$value"
    git -C "$repository" cat-file -e "$value^{commit}"
    marker=$(mktemp "$state/bootstrap-complete.XXXXXX")
    trap 'rm -f "$marker"' EXIT
    printf 'vm=%s\nbootstrap_sha=%s\n' "$secondary" "$value" >"$marker"
    chmod 0600 "$marker"
    mv "$marker" "$state/bootstrap-complete"
    trap - EXIT
    printf 'bootstrapped_vm=%s bootstrap_sha=%s\n' "$secondary" "$value"
    ;;
credential | rotate)
    install_credential "$mode"
    ;;
deploy)
    require_digest
    [[ -f "$state/bootstrap-complete" ]] || fail "container VM is not bootstrapped"
    [[ -f "$credential_store/paperbridge-mqtt-password" ]] ||
        fail "credential is not provisioned"
    current=$(read_current_digest || true)
    [[ $current != "$value" ]] || fail "image digest is already deployed"
    if [[ -n $current ]]; then
        [[ -f "$state/images/${current#sha256:}.sha" ]] ||
            fail "current image is not retained for rollback"
        validate_image "$current"
    fi
    old_previous=$(read_previous_digest || true)
    activate_image "$value" "$current" "$old_previous" "$current" "deployment failed"
    prune_release_images "$value" "$current"
    printf 'deployed_digest=%s rollback_digest=%s\n' "$value" "${current:-none}"
    ;;
rollback)
    [[ -f "$state/bootstrap-complete" ]] || fail "container VM is not bootstrapped"
    current=$(read_current_digest)
    previous=$(read_previous_digest) || fail "no previous image digest is recorded"
    [[ $previous != "$current" ]] || fail "previous image digest matches current"
    activate_image "$previous" "$current" "$previous" "$current" "rollback failed"
    prune_release_images "$previous" "$current"
    printf 'rolled_back_digest=%s rollback_digest=%s\n' "$previous" "$current"
    ;;
status)
    [[ -f "$state/bootstrap-complete" ]] || fail "container VM is not bootstrapped"
    current=$(read_current_digest || printf 'none\n')
    if [[ -f "$state/previous-image" ]]; then
        previous=$(cat "$state/previous-image")
        [[ $previous =~ ^sha256:[0-9a-f]{64}$ ]] || fail "previous image state is invalid"
    else
        previous=none
    fi
    printf 'current_digest=%s previous_digest=%s\n' "$current" "$previous"
    systemctl status --no-pager paperbridge-container.service
    ;;
logs)
    [[ -f "$state/bootstrap-complete" ]] || fail "container VM is not bootstrapped"
    journalctl --no-pager --unit=paperbridge-container.service --lines=100
    ;;
verify)
    [[ -f "$state/bootstrap-complete" ]] || fail "container VM is not bootstrapped"
    curl --fail --silent --show-error --retry 15 --retry-delay 1 --retry-connrefused \
        http://127.0.0.1:3000/health
    curl --fail --silent --show-error --retry 15 --retry-delay 1 --retry-connrefused \
        http://127.0.0.1:3000/ready
    ;;
probe)
    [[ -f "$state/bootstrap-complete" ]] || fail "container VM is not bootstrapped"
    systemctl is-active --quiet paperbridge-container.service
    docker exec paperbridge-api node dist/main.js
    ;;
restart)
    [[ -f "$state/bootstrap-complete" ]] || fail "container VM is not bootstrapped"
    systemctl restart paperbridge-container.service
    ;;
build)
    require_sha
    [[ -f "$state/bootstrap-complete" ]] || fail "container VM is not bootstrapped"
    git -C "$repository" fetch --quiet --depth=1 origin "$value"
    release="$builds/$value"
    if [[ ! -d "$release" ]]; then
        git -C "$repository" worktree add --detach "$release" "$value"
    fi
    [[ $(git -C "$release" rev-parse HEAD) == "$value" ]] ||
        fail "build checkout does not match requested commit"
    [[ -f "$release/apps/api/Dockerfile" ]] || fail "reviewed commit has no API Dockerfile"

    tag="paperbridge-api:sha-$value"
    docker build \
        --file "$release/apps/api/Dockerfile" \
        --label "org.opencontainers.image.revision=$value" \
        --tag "$tag" \
        "$release"
    digest=$(docker image inspect --format '{{.Id}}' "$tag")
    [[ $digest =~ ^sha256:[0-9a-f]{64}$ ]] || fail "Docker returned an invalid image digest"
    revision=$(docker image inspect \
        --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' \
        "$digest")
    [[ $revision == "$value" ]] || fail "image revision label does not match requested commit"
    architecture=$(docker image inspect --format '{{.Architecture}}' "$digest")
    [[ $architecture =~ ^[a-z0-9_-]+$ ]] || fail "Docker returned an invalid architecture"
    record_image "$digest" "$value"
    printf 'built_sha=%s image_digest=%s architecture=%s\n' \
        "$value" "$digest" "$architecture"
    ;;
*)
    echo "unsupported mode: $mode" >&2
    exit 2
    ;;
esac
