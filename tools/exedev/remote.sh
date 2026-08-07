#!/usr/bin/env bash
set -euo pipefail

mode=${1:?mode is required}
sha=${2:-}
root=/opt/paperbridge
repository="$root/repository"
releases="$root/releases"
current="$root/current"
state_dir=/var/lib/paperbridge
unit=/etc/systemd/system/paperbridge.service

require_sha() {
    [[ $sha =~ ^[0-9a-f]{40}$ ]] || {
        echo "expected a 40-character lowercase commit SHA" >&2
        exit 2
    }
}

as_paperbridge() {
    sudo -u paperbridge env HOME=/home/paperbridge "$@"
}

install_mise() {
    if command -v mise >/dev/null; then return; fi
    local installer
    installer=$(mktemp)
    curl --fail --silent --show-error --location https://mise.run --output "$installer"
    test -s "$installer"
    MISE_INSTALL_PATH=/usr/local/bin/mise sh "$installer"
    rm -f "$installer"
}

prepare_release() {
    local target=$1
    local release="$releases/$target"
    as_paperbridge git -C "$repository" fetch --quiet --depth=1 origin "$target" || return
    as_paperbridge git -C "$repository" cat-file -e "$target^{commit}" || return
    if [[ ! -d "$release" ]]; then
        as_paperbridge git -C "$repository" worktree add --detach "$release" "$target" >&2 || return
    fi
    as_paperbridge env MISE_DATA_DIR="$release/.mise" \
        /usr/local/bin/mise trust "$release/mise.toml" >&2 || return
    as_paperbridge env MISE_DATA_DIR="$release/.mise" \
        /usr/local/bin/mise -C "$release" install >&2 || return
    as_paperbridge env MISE_DATA_DIR="$release/.mise" \
        /usr/local/bin/mise -C "$release" exec -- bun install --frozen-lockfile >&2 || return
    printf '%s\n' "$release"
}

current_sha() {
    local target
    target=$(readlink -f "$current")
    basename "$target"
}

switch_release() {
    local release=$1
    ln -sfn "$release" "$current.next"
    mv -Tf "$current.next" "$current"
}

install_unit() {
    local release=$1
    install -m 0644 "$release/deploy/exedev/paperbridge.service" "$unit"
    systemctl daemon-reload
}

case "$mode" in
bootstrap)
    require_sha
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install --yes ca-certificates curl
    install_mise
    id paperbridge >/dev/null 2>&1 || useradd \
        --system --create-home --home-dir /home/paperbridge \
        --shell /usr/sbin/nologin paperbridge
    install -d -m 0755 "$root"
    install -d -o paperbridge -g paperbridge -m 0755 "$repository" "$releases"
    install -d -m 0700 /etc/paperbridge "$state_dir"
    if [[ ! -d "$repository/.git" ]]; then
        as_paperbridge git clone https://github.int.exe.xyz/giuseppecrj/paperbridge.git "$repository"
    fi
    release=$(prepare_release "$sha") || exit $?
    switch_release "$release"
    install_unit "$release"
    systemctl enable paperbridge
    printf 'bootstrapped_sha=%s\n' "$sha"
    ;;
deploy)
    require_sha
    systemctl is-active --quiet paperbridge
    previous=$(current_sha)
    [[ $previous =~ ^[0-9a-f]{40}$ ]] || {
        echo "current release SHA is invalid" >&2
        exit 2
    }
    release=$(prepare_release "$sha") || exit $?
    install_unit "$release"
    printf '%s\n' "$previous" | install -m 0600 /dev/stdin "$state_dir/previous-sha"
    switch_release "$release"
    systemctl restart paperbridge
    printf 'deployed_sha=%s rollback_sha=%s\n' "$sha" "$previous"
    ;;
rollback)
    previous=$(cat "$state_dir/previous-sha")
    [[ $previous =~ ^[0-9a-f]{40}$ ]] || {
        echo "stored rollback SHA is invalid" >&2
        exit 2
    }
    release="$releases/$previous"
    test -d "$release"
    current=$(current_sha)
    install_unit "$release"
    printf '%s\n' "$current" | install -m 0600 /dev/stdin "$state_dir/previous-sha"
    switch_release "$release"
    systemctl restart paperbridge
    printf 'rolled_back_sha=%s rollback_sha=%s\n' "$previous" "$current"
    ;;
*)
    echo "unsupported mode: $mode" >&2
    exit 2
    ;;
esac
