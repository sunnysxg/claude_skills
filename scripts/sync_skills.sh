#!/usr/bin/env bash
# Linux skill installer. The manifest is the only install list.
set -euo pipefail

command_name="sync"
dry_run=false
repair_links=false
manifest_path=""
local_config_path=""
declare -a requested_clients=()

usage() {
  cat <<'EOF'
Usage:
  bash scripts/sync_skills.sh [sync|doctor] [options]

Options:
  --client NAME[,NAME]  Select clients explicitly. May be repeated.
  --dry-run             Report changes without writing.
  --repair-links        Replace only existing symlinks that point elsewhere.
  --manifest PATH       Use a non-default manifest.
  --local-config PATH   Use a non-default machine-local override.
  -h, --help            Show this help.

Without --client, enabled clients come from skills.manifest.json plus
the untracked sync.local.json override.
EOF
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_value() {
  local option="$1"
  local value="${2:-}"
  [[ -n "$value" ]] || die "$option requires a value"
}

while (($#)); do
  case "$1" in
    sync|doctor)
      command_name="$1"
      shift
      ;;
    --client)
      require_value "$1" "${2:-}"
      IFS=',' read -r -a split_clients <<<"$2"
      requested_clients+=("${split_clients[@]}")
      shift 2
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    --repair-links)
      repair_links=true
      shift
      ;;
    --manifest)
      require_value "$1" "${2:-}"
      manifest_path="$2"
      shift 2
      ;;
    --local-config)
      require_value "$1" "${2:-}"
      local_config_path="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

[[ "$(uname -s)" == "Linux" ]] || die "this script is tested and supported on Linux only"
command -v jq >/dev/null 2>&1 || die "jq is required"
command -v realpath >/dev/null 2>&1 || die "realpath is required"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(realpath -m -- "$script_dir/..")"
manifest_path="${manifest_path:-$repo_root/skills.manifest.json}"
local_config_path="${local_config_path:-$repo_root/sync.local.json}"

[[ -f "$manifest_path" ]] || die "manifest not found: $manifest_path"
jq -e . "$manifest_path" >/dev/null || die "manifest is not valid JSON: $manifest_path"
[[ "$(jq -r '.version // empty' "$manifest_path")" == "1" ]] ||
  die "unsupported manifest version"
jq -e '.supported_platforms | index("linux") != null' "$manifest_path" >/dev/null ||
  die "manifest does not declare Linux support"

local_json="{}"
if [[ -f "$local_config_path" ]]; then
  jq -e . "$local_config_path" >/dev/null ||
    die "local config is not valid JSON: $local_config_path"
  local_json="$(<"$local_config_path")"
fi

expand_path() {
  local value="$1"
  local base="$2"
  case "$value" in
    "~")
      value="$HOME"
      ;;
    "~/"*)
      value="$HOME/${value:2}"
      ;;
    /*)
      ;;
    *)
      value="$base/$value"
      ;;
  esac
  realpath -m -- "$value"
}

assert_safe_client_root() {
  local client_root="$1"
  local source_root="$2"
  [[ "$client_root" != "/" ]] || die "refusing filesystem root as client root"
  [[ "$client_root" != "$(realpath -m -- "$HOME")" ]] ||
    die "refusing HOME itself as client root"
  [[ "$client_root" != "$source_root" && "$client_root" != "$source_root/"* ]] ||
    die "refusing client root inside source repository: $client_root"
}

normalize_link_target() {
  local link_path="$1"
  local raw_target
  raw_target="$(readlink -- "$link_path")"
  if [[ "$raw_target" == /* ]]; then
    realpath -m -- "$raw_target"
  else
    realpath -m -- "$(dirname -- "$link_path")/$raw_target"
  fi
}

normalize_machine_id() {
  local raw="$1"
  local normalized
  normalized="$(
    printf '%s' "$raw" |
      tr '[:upper:]' '[:lower:]' |
      sed -E 's/[^a-z0-9._-]+/-/g; s/^[-._]+//; s/[-._]+$//'
  )"
  [[ -n "$normalized" ]] || die "machine_id is empty after normalization"
  ((${#normalized} <= 64)) || die "machine_id must be 64 characters or fewer"
  printf '%s\n' "$normalized"
}

source_root_value="$(jq -r '.source_root // "."' "$manifest_path")"
source_root="$(expand_path "$source_root_value" "$repo_root")"
machine_id_raw="$(
  jq -r --arg host "$(hostname -s)" '.machine_id // $host' <<<"$local_json"
)"
machine_id="$(normalize_machine_id "$machine_id_raw")"

mapfile -t manifest_clients < <(jq -r '.clients | keys[]' "$manifest_path")
declare -a selected_clients=()

if ((${#requested_clients[@]})); then
  for client in "${requested_clients[@]}"; do
    [[ -n "$client" ]] || continue
    selected_clients+=("$client")
  done
else
  for client in "${manifest_clients[@]}"; do
    enabled="$(
      jq -r \
        --arg client "$client" \
        --argjson local "$local_json" \
        'if $local.clients[$client].enabled != null
         then $local.clients[$client].enabled
         else .clients[$client].enabled_by_default
         end' \
        "$manifest_path"
    )"
    [[ "$enabled" == "true" ]] && selected_clients+=("$client")
  done
fi

((${#selected_clients[@]})) || die "no clients are enabled or selected"

for client in "${selected_clients[@]}"; do
  printf '%s\n' "${manifest_clients[@]}" | grep -Fxq -- "$client" ||
    die "client is not declared in manifest: $client"
  [[ "$(jq -r --arg client "$client" '.clients[$client].unix_link_type' "$manifest_path")" == "symlink" ]] ||
    die "client does not declare unix_link_type=symlink: $client"
done

declare -a entry_names=()
declare -a entry_sources=()
declare -a entry_targets=()
declare -a entry_kinds=()
declare -A seen_names=()

while IFS=$'\t' read -r name source targets kind; do
  [[ "$name" =~ ^[a-z0-9][a-z0-9-]{0,63}$ ]] || die "invalid skill or alias name: $name"
  [[ -z "${seen_names[$name]+x}" ]] || die "duplicate skill or alias name: $name"
  seen_names["$name"]=1

  source_path="$(expand_path "$source" "$source_root")"
  [[ "$source_path" == "$source_root" || "$source_path" == "$source_root/"* ]] ||
    die "skill source escapes repository: $name -> $source_path"
  [[ -f "$source_path/SKILL.md" ]] ||
    die "skill source is missing SKILL.md: $name -> $source_path"

  entry_names+=("$name")
  entry_sources+=("$source_path")
  entry_targets+=("$targets")
  entry_kinds+=("$kind")
done < <(
  jq -r '
    (
      [.skills[] | {
        name: .name,
        source: .source,
        targets: .targets,
        kind: "skill"
      }] +
      [(.aliases // [])[] | {
        name: .name,
        source: .source,
        targets: .targets,
        kind: "alias"
      }]
    )[] |
    [.name, .source, (.targets | join(",")), .kind] |
    @tsv
  ' "$manifest_path"
)

declare -a op_clients=()
declare -a op_roots=()
declare -a op_names=()
declare -a op_sources=()
declare -a op_targets=()

for client in "${selected_clients[@]}"; do
  root_value="$(
    jq -r \
      --arg client "$client" \
      --argjson local "$local_json" \
      'if ($local.clients[$client].root // "") != ""
       then $local.clients[$client].root
       else .clients[$client].root
       end' \
      "$manifest_path"
  )"
  client_root="$(expand_path "$root_value" "$repo_root")"
  assert_safe_client_root "$client_root" "$source_root"

  for index in "${!entry_names[@]}"; do
    IFS=',' read -r -a targets <<<"${entry_targets[$index]}"
    selected=false
    for target_client in "${targets[@]}"; do
      if [[ "$target_client" == "$client" ]]; then
        selected=true
        break
      fi
    done
    $selected || continue

    op_clients+=("$client")
    op_roots+=("$client_root")
    op_names+=("${entry_names[$index]}")
    op_sources+=("${entry_sources[$index]}")
    op_targets+=("$client_root/${entry_names[$index]}")
  done
done

echo "machine_id: $machine_id"
echo "command: $command_name"
echo "clients: ${selected_clients[*]}"
echo "manifest: $manifest_path"
if [[ -f "$local_config_path" ]]; then
  echo "local override: $local_config_path"
else
  echo "local override: not configured (using hostname and manifest defaults)"
fi
echo "---"

created=0
ok=0
conflicts=0
missing=0

for index in "${!op_names[@]}"; do
  number=$((index + 1))
  prefix="[$number/${#op_names[@]}] [${op_clients[$index]}] ${op_names[$index]}"
  client_root="${op_roots[$index]}"
  source_path="${op_sources[$index]}"
  target_path="${op_targets[$index]}"

  if [[ ! -e "$target_path" && ! -L "$target_path" ]]; then
    if [[ "$command_name" == "doctor" ]]; then
      echo "$prefix MISSING -> $source_path"
      missing=$((missing + 1))
      continue
    fi
    if $dry_run; then
      echo "$prefix would create symlink -> $source_path"
    else
      mkdir -p -- "$client_root"
      ln -s -- "$source_path" "$target_path"
      echo "$prefix created symlink -> $source_path"
    fi
    created=$((created + 1))
    continue
  fi

  if [[ -L "$target_path" ]]; then
    link_target="$(normalize_link_target "$target_path")"
    if [[ "$link_target" == "$source_path" ]]; then
      echo "$prefix OK -> $link_target"
      ok=$((ok + 1))
      continue
    fi

    if [[ "$command_name" == "sync" ]] && $repair_links; then
      if $dry_run; then
        echo "$prefix would repair symlink: $link_target -> $source_path"
      else
        unlink -- "$target_path"
        ln -s -- "$source_path" "$target_path"
        echo "$prefix repaired symlink -> $source_path"
      fi
      created=$((created + 1))
      continue
    fi

    echo "$prefix CONFLICT: existing symlink points to $link_target; use --repair-links to replace it" >&2
    conflicts=$((conflicts + 1))
    continue
  fi

  echo "$prefix CONFLICT: target is a regular file or real directory; it will not be overwritten" >&2
  conflicts=$((conflicts + 1))
done

echo "---"
echo "OK: $ok, create/repair: $created, missing: $missing, conflicts: $conflicts"

if ((conflicts > 0)) || [[ "$command_name" == "doctor" && "$missing" -gt 0 ]]; then
  exit 1
fi
