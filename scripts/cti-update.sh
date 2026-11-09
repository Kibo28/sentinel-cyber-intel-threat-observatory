#!/bin/sh
# Run on the NAS. The container can queue an update to the configured GitHub branch.
set -eu
umask 077

if [ "$#" -ne 2 ] || [ "$(id -u)" -ne 0 ]; then
    echo "Usage: sudo sh cti-update.sh {init|run} PROJECT_DIRECTORY" >&2
    exit 2
fi

project=$(cd "$2" && pwd -P)
control="$project/.cti-update"
request="$control/requests/pending"
status_file="$control/status/status.json"
service=cyber-intel-observatory
repo=Kibo28/sentinel-cyber-intel-threat-observatory
docker=$(command -v docker || printf '%s' /var/packages/ContainerManager/target/usr/bin/docker)
lock=/var/run/cti-observatory-update.lock

write_status() {
    printf '{"state":"%s","revision":"%s"}\n' "$1" "$2" > "$status_file.tmp" &&
        chmod 644 "$status_file.tmp" && mv -f "$status_file.tmp" "$status_file"
}

if [ "$1" = init ]; then
    working_dir=$("$docker" inspect --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$service")
    if [ "$working_dir" != "$project" ]; then
        echo "Start the Compose project from $project before setting up updates." >&2
        exit 1
    fi
    "$docker" compose up --help | grep -q -- '--wait-timeout' || {
        echo 'Docker Compose must support up --wait-timeout.' >&2
        exit 1
    }
    project_name=$("$docker" inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$service")
    uid=$("$docker" exec "$service" id -u)
    gid=$("$docker" exec "$service" id -g)
    case "$uid" in ''|*[!0-9]*) exit 1 ;; esac
    case "$gid" in ''|*[!0-9]*) exit 1 ;; esac
    mkdir -p "$control/requests" "$control/status" "$control/releases"
    chown root:root "$control" "$control/status" "$control/releases"
    chmod 700 "$control" "$control/requests" "$control/releases"
    chmod 755 "$control/status"
    chown "$uid:$gid" "$control/requests"
    printf '%s\n' "$project_name" > "$control/project-name"
    touch "$control/empty.env"
    [ -f "$status_file" ] || write_status idle ''
    exit 0
fi

if [ "$1" != run ]; then
    echo 'Use init or run.' >&2
    exit 2
fi

[ -f "$status_file" ] && [ -d "$request" ] && [ ! -L "$request" ] || exit 0
mkdir "$lock" 2>/dev/null || exit 0
if [ ! -d "$request" ] || [ -L "$request" ]; then
    rmdir "$lock"
    exit 0
fi

active=''
stage=''
failure=failed
cleanup() {
    result=$?
    trap - EXIT
    if [ "$result" -ne 0 ]; then
        rmdir "$request" 2>/dev/null || :
        write_status "$failure" "$active" || :
    fi
    if [ -n "$stage" ]; then
        rm -rf -- "$stage"
    fi
    rmdir "$lock"
    exit "$result"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

valid_revision() {
    [ "${#1}" -eq 40 ] || return 1
    case "$1" in *[!0-9a-f]*) return 1 ;; esac
}

if [ -f "$control/active" ]; then
    active=$(cat "$control/active")
    valid_revision "$active"
fi
write_status running "$active"

project_name=$(cat "$control/project-name")
env_file="$project/.env"
[ -f "$env_file" ] || env_file="$control/empty.env"

deploy() {
    if [ -f "$project/docker-compose.override.yml" ]; then
        set -- -f "$1" -f "$project/docker-compose.override.yml" -f "$2"
    else
        set -- -f "$1" -f "$2"
    fi
    "$docker" compose --project-directory "$project" --env-file "$env_file" \
        -p "$project_name" "$@" up -d --no-build --wait --wait-timeout 180 "$service"
}

revision=$(curl -fsS --max-time 30 -H 'Accept: application/vnd.github.sha' \
    "https://api.github.com/repos/$repo/commits/main")
if ! valid_revision "$revision"; then
    echo 'GitHub did not return a valid commit SHA.' >&2
    exit 1
fi
running_image=$("$docker" inspect --format '{{.Config.Image}}' "$service")
if [ "$revision" = "$active" ] && [ "$running_image" = "cti-observatory-update:$revision" ] &&
        [ "$("$docker" inspect --format '{{.State.Status}}' "$service")" = running ]; then
    rmdir "$request"
    write_status current "$revision"
    exit 0
fi

release="$control/releases/$revision"
if [ ! -d "$release" ]; then
    stage=$(mktemp -d "$control/download.XXXXXX")
    curl -fsSL --proto '=https' --proto-redir '=https' --max-time 120 \
        "https://codeload.github.com/$repo/tar.gz/$revision" -o "$stage/source.tar.gz"
    mkdir "$stage/source"
    tar -xzf "$stage/source.tar.gz" -C "$stage/source" --strip-components=1
    if [ ! -f "$stage/source/Dockerfile" ] || [ ! -f "$stage/source/docker-compose.yml" ] || [ ! -f "$stage/source/app/updates.py" ]; then
        echo 'The GitHub revision does not contain a compatible dashboard update.' >&2
        exit 1
    fi
    mv "$stage/source" "$release"
fi

image="cti-observatory-update:$revision"
printf 'services:\n  %s:\n    image: %s\n' "$service" "$image" > "$release/update-image.yml"
"$docker" build --tag "$image" "$release"

previous_image=$("$docker" inspect --format '{{.Image}}' "$service")
"$docker" image tag "$previous_image" cti-observatory-update:rollback
printf 'services:\n  %s:\n    image: cti-observatory-update:rollback\n' "$service" > "$control/rollback-image.yml"
previous_config="$project/docker-compose.yml"
if [ -n "$active" ] && { [ "$running_image" = "cti-observatory-update:$active" ] || [ "$running_image" = cti-observatory-update:rollback ]; }; then
    previous_config="$control/releases/$active/docker-compose.yml"
fi

if ! deploy "$release/docker-compose.yml" "$release/update-image.yml"; then
    if deploy "$previous_config" "$control/rollback-image.yml"; then
        failure=rolled_back
    else
        failure=rollback_failed
    fi
    exit 1
fi

printf '%s\n' "$revision" > "$control/active.tmp"
mv -f "$control/active.tmp" "$control/active"
active=$revision
rmdir "$request"
write_status updated "$revision"
