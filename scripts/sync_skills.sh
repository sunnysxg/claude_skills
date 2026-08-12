#!/usr/bin/env bash
# Linux skill installer. The manifest is the only install list.
set -euo pipefail

command_name="sync"
dry_run=false
repair_links=false
scope="all"
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
  --scope all|skills|rules
                        Manage both kinds, only skill links, or only rules.
  --manifest PATH       Use a non-default manifest.
  --local-config PATH   Use a non-default machine-local override.
  -h, --help            Show this help.

Without --client, enabled clients come from skills.manifest.json plus
the untracked sync.local.json override. The same override can disable a
canonical skill with skills.<name>.enabled=false.
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
    --scope)
      require_value "$1" "${2:-}"
      scope="$2"
      shift 2
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

case "$scope" in
  all|skills|rules) ;;
  *) die "--scope must be one of: all, skills, rules" ;;
esac

manage_skills=false
manage_rules=false
[[ "$scope" == "all" || "$scope" == "skills" ]] && manage_skills=true
[[ "$scope" == "all" || "$scope" == "rules" ]] && manage_rules=true

[[ "$(uname -s)" == "Linux" ]] || die "this script is tested and supported on Linux only"
platform_name="linux"
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

managed_begin_marker() {
  printf '<!-- BEGIN claude_skills:%s -->' "$1"
}

managed_end_marker() {
  printf '<!-- END claude_skills:%s -->' "$1"
}

count_marker_lines() {
  local path="$1"
  local marker="$2"
  awk -v marker="$marker" '
    {
      sub(/\r$/, "")
      if ($0 == marker) count += 1
    }
    END { print count + 0 }
  ' "$path"
}

normalize_text_file() {
  local input_path="$1"
  local output_path="$2"
  awk '
    {
      sub(/\r$/, "")
      lines[NR] = $0
    }
    END {
      last = NR
      while (last > 0 && lines[last] == "") last -= 1
      for (line_no = 1; line_no <= last; line_no += 1) print lines[line_no]
    }
  ' "$input_path" >"$output_path"
}

preferred_newline_name() {
  local path="$1"
  if [[ -f "$path" ]] && LC_ALL=C grep -q $'\r$' "$path"; then
    printf 'crlf\n'
  else
    printf 'lf\n'
  fi
}

render_managed_block() {
  local name="$1"
  local source_path="$2"
  local newline_name="$3"
  local output_path="$4"
  local newline=$'\n'
  [[ "$newline_name" == "crlf" ]] && newline=$'\r\n'

  : >"$output_path"
  printf '%s%s' "$(managed_begin_marker "$name")" "$newline" >>"$output_path"
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    printf '%s%s' "$line" "$newline" >>"$output_path"
  done <"$source_path"
  printf '%s' "$(managed_end_marker "$name")" >>"$output_path"
}

render_cursor_rule() {
  local name="$1"
  local source_path="$2"
  local newline_name="$3"
  local output_path="$4"
  local block_path="$5"
  local newline=$'\n'
  [[ "$newline_name" == "crlf" ]] && newline=$'\r\n'

  render_managed_block "$name" "$source_path" "$newline_name" "$block_path"
  {
    printf '%s' "---${newline}"
    printf '%s' "description: Global rules generated from claude_skills/global/COMMON.md${newline}"
    printf '%s' "alwaysApply: true${newline}"
    printf '%s' "---${newline}"
    cat -- "$block_path"
    printf '%s' "$newline"
  } >"$output_path"
}

inspect_managed_rule() {
  local name="$1"
  local mode="$2"
  local target_path="$3"
  local source_path="$4"
  local legacy_exact="$5"
  local begin_marker end_marker begin_count end_count begin_line end_line
  local scratch_dir expected_path expected_block normalized_existing normalized_expected

  begin_marker="$(managed_begin_marker "$name")"
  end_marker="$(managed_end_marker "$name")"
  [[ "$(count_marker_lines "$source_path" "$begin_marker")" == "0" ]] ||
    die "managed rule source contains its own begin marker: $name"
  [[ "$(count_marker_lines "$source_path" "$end_marker")" == "0" ]] ||
    die "managed rule source contains its own end marker: $name"

  if [[ ! -e "$target_path" && ! -L "$target_path" ]]; then
    printf 'MissingFile\n'
    return
  fi
  if [[ -L "$target_path" || -d "$target_path" || ! -f "$target_path" ]]; then
    printf 'UnsafeTarget\n'
    return
  fi

  begin_count="$(count_marker_lines "$target_path" "$begin_marker")"
  end_count="$(count_marker_lines "$target_path" "$end_marker")"

  if [[ "$mode" == "cursor_mdc" ]]; then
    scratch_dir="$(mktemp -d)"
    expected_path="$scratch_dir/expected"
    expected_block="$scratch_dir/block"
    normalized_existing="$scratch_dir/existing.norm"
    normalized_expected="$scratch_dir/expected.norm"
    render_cursor_rule "$name" "$source_path" "$(preferred_newline_name "$target_path")" \
      "$expected_path" "$expected_block"
    normalize_text_file "$target_path" "$normalized_existing"
    normalize_text_file "$expected_path" "$normalized_expected"
    if cmp -s -- "$normalized_existing" "$normalized_expected"; then
      rm -rf -- "$scratch_dir"
      printf 'Current\n'
      return
    fi
    rm -rf -- "$scratch_dir"
    if [[ "$begin_count" == "1" && "$end_count" == "1" ]]; then
      begin_line="$(LC_ALL=C grep -nFx -- "$begin_marker" <(sed 's/\r$//' "$target_path") | cut -d: -f1)"
      end_line="$(LC_ALL=C grep -nFx -- "$end_marker" <(sed 's/\r$//' "$target_path") | cut -d: -f1)"
      if [[ -n "$begin_line" && -n "$end_line" && "$begin_line" -lt "$end_line" ]]; then
        printf 'Stale\n'
      else
        printf 'Malformed\n'
      fi
    elif [[ "$begin_count" == "0" && "$end_count" == "0" ]]; then
      printf 'UnmanagedFile\n'
    else
      printf 'Malformed\n'
    fi
    return
  fi

  [[ "$mode" == "managed_block" ]] || die "unsupported managed rule mode: $mode"
  if [[ -n "$legacy_exact" ]]; then
    local legacy_actual
    legacy_actual="$(sed 's/\r$//' "$target_path")"
    if [[ "$legacy_actual" == "$legacy_exact" ]]; then
      printf 'Legacy\n'
      return
    fi
  fi

  if [[ "$begin_count" == "0" && "$end_count" == "0" ]]; then
    printf 'Unmanaged\n'
    return
  fi
  if [[ "$begin_count" != "1" || "$end_count" != "1" ]]; then
    printf 'Malformed\n'
    return
  fi

  begin_line="$(LC_ALL=C grep -nFx -- "$begin_marker" <(sed 's/\r$//' "$target_path") | cut -d: -f1)"
  end_line="$(LC_ALL=C grep -nFx -- "$end_marker" <(sed 's/\r$//' "$target_path") | cut -d: -f1)"
  if [[ -z "$begin_line" || -z "$end_line" || "$begin_line" -ge "$end_line" ]]; then
    printf 'Malformed\n'
    return
  fi

  scratch_dir="$(mktemp -d)"
  expected_block="$scratch_dir/expected.block"
  normalized_existing="$scratch_dir/existing.norm"
  normalized_expected="$scratch_dir/expected.norm"
  render_managed_block "$name" "$source_path" "$(preferred_newline_name "$target_path")" \
    "$expected_block"
  sed -n "${begin_line},${end_line}p" "$target_path" >"$scratch_dir/current.block"
  normalize_text_file "$scratch_dir/current.block" "$normalized_existing"
  normalize_text_file "$expected_block" "$normalized_expected"
  if cmp -s -- "$normalized_existing" "$normalized_expected"; then
    rm -rf -- "$scratch_dir"
    printf 'Current\n'
  else
    rm -rf -- "$scratch_dir"
    printf 'Stale\n'
  fi
}

render_managed_rule_target() {
  local name="$1"
  local mode="$2"
  local state="$3"
  local target_path="$4"
  local source_path="$5"
  local output_path="$6"
  local scratch_dir block_path newline_name begin_marker end_marker

  newline_name="$(preferred_newline_name "$target_path")"
  scratch_dir="$(dirname -- "$output_path")"
  block_path="$scratch_dir/.managed-block.$$"
  begin_marker="$(managed_begin_marker "$name")"
  end_marker="$(managed_end_marker "$name")"

  if [[ "$mode" == "cursor_mdc" ]]; then
    render_cursor_rule "$name" "$source_path" "$newline_name" "$output_path" "$block_path"
    rm -f -- "$block_path"
    return
  fi

  render_managed_block "$name" "$source_path" "$newline_name" "$block_path"
  case "$state" in
    MissingFile|Legacy)
      cat -- "$block_path" >"$output_path"
      printf '\n' >>"$output_path"
      ;;
    Unmanaged)
      cat -- "$target_path" >"$output_path"
      if [[ -s "$target_path" ]]; then
        last_byte="$(tail -c 1 -- "$target_path" | od -An -t u1 | tr -d '[:space:]')"
        if [[ "$last_byte" == "10" ]]; then
          printf '\n' >>"$output_path"
        else
          printf '\n\n' >>"$output_path"
        fi
      fi
      cat -- "$block_path" >>"$output_path"
      printf '\n' >>"$output_path"
      ;;
    Stale)
      awk -v begin="$begin_marker" -v end="$end_marker" -v block="$block_path" '
        {
          comparable = $0
          sub(/\r$/, "", comparable)
        }
        comparable == begin {
          while ((getline replacement < block) > 0) print replacement
          close(block)
          replacing = 1
          next
        }
        replacing && comparable == end {
          replacing = 0
          next
        }
        !replacing { print }
      ' "$target_path" >"$output_path"
      ;;
    *)
      die "cannot render managed rule state: $state"
      ;;
  esac
  rm -f -- "$block_path"
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
done

declare -a op_clients=()
declare -a op_roots=()
declare -a op_names=()
declare -a op_sources=()
declare -a op_targets=()

if $manage_skills; then
for client in "${selected_clients[@]}"; do
  [[ "$(jq -r --arg client "$client" '.clients[$client].unix_link_type' "$manifest_path")" == "symlink" ]] ||
    die "client does not declare unix_link_type=symlink: $client"
done

declare -a entry_names=()
declare -a entry_sources=()
declare -a entry_targets=()
declare -a entry_kinds=()
declare -A seen_names=()
declare -A canonical_skill_names=()

while IFS=$'\t' read -r name source targets platforms kind override_key; do
  [[ "$name" =~ ^[a-z0-9][a-z0-9-]{0,63}$ ]] || die "invalid skill or alias name: $name"
  [[ -z "${seen_names[$name]+x}" ]] || die "duplicate skill or alias name: $name"
  seen_names["$name"]=1
  if [[ "$kind" == "skill" ]]; then
    canonical_skill_names["$name"]=1
  else
    [[ -n "$override_key" ]] || die "alias must declare canonical: $name"
    [[ -n "${canonical_skill_names[$override_key]+x}" ]] ||
      die "alias canonical skill is not declared: $name -> $override_key"
  fi

  source_path="$(expand_path "$source" "$source_root")"
  [[ "$source_path" == "$source_root" || "$source_path" == "$source_root/"* ]] ||
    die "skill source escapes repository: $name -> $source_path"
  [[ -f "$source_path/SKILL.md" ]] ||
    die "skill source is missing SKILL.md: $name -> $source_path"

  [[ -n "$platforms" ]] || die "entry must declare at least one platform: $name"
  platform_selected=false
  IFS=',' read -r -a platform_values <<<"$platforms"
  for platform in "${platform_values[@]}"; do
    jq -e --arg platform "$platform" \
      '.supported_platforms | index($platform) != null' "$manifest_path" >/dev/null ||
      die "entry declares an unsupported platform: $name -> $platform"
    [[ "$platform" == "$platform_name" ]] && platform_selected=true
  done
  $platform_selected || continue

  enabled="$(
    jq -r \
      --arg skill "$override_key" \
      --argjson local "$local_json" \
      'if $local.skills[$skill].enabled == null
       then true
       else $local.skills[$skill].enabled
       end' \
      "$manifest_path"
  )"
  [[ "$enabled" == "true" ]] || continue

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
        platforms: .platforms,
        kind: "skill",
        override_key: .name
      }] +
      [(.aliases // [])[] | {
        name: .name,
        source: .source,
        targets: .targets,
        platforms: .platforms,
        kind: "alias",
        override_key: .canonical
      }]
    )[] |
    [.name, .source, (.targets | join(",")), (.platforms | join(",")), .kind, .override_key] |
    @tsv
  ' "$manifest_path"
)

while IFS= read -r local_skill; do
  [[ -z "$local_skill" ]] && continue
  [[ -n "${canonical_skill_names[$local_skill]+x}" ]] ||
    die "local config references an undeclared skill: $local_skill"
done < <(jq -r '(.skills // {}) | keys[]' <<<"$local_json")

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
fi

declare -a rule_names=()
declare -a rule_clients=()
declare -a rule_modes=()
declare -a rule_sources=()
declare -a rule_targets=()
declare -a rule_legacy=()
declare -a rule_states=()
declare -A seen_rule_targets=()

if $manage_rules; then
  while IFS=$'\t' read -r rule_name rule_source rule_platforms target_client target_value rule_mode legacy_exact; do
    [[ -n "$rule_name" ]] || continue
    [[ "$rule_name" =~ ^[a-z0-9][a-z0-9-]{0,63}$ ]] ||
      die "invalid managed rule name: $rule_name"
    printf '%s\n' "${manifest_clients[@]}" | grep -Fxq -- "$target_client" ||
      die "managed rule target client is not declared: $rule_name -> $target_client"

    client_selected=false
    for selected_client in "${selected_clients[@]}"; do
      [[ "$selected_client" == "$target_client" ]] && client_selected=true
    done
    $client_selected || continue

    [[ -n "$rule_platforms" ]] || die "managed rule must declare at least one platform: $rule_name"
    platform_selected=false
    IFS=',' read -r -a rule_platform_values <<<"$rule_platforms"
    for platform in "${rule_platform_values[@]}"; do
      jq -e --arg platform "$platform" \
        '.supported_platforms | index($platform) != null' "$manifest_path" >/dev/null ||
        die "managed rule declares an unsupported platform: $rule_name -> $platform"
      [[ "$platform" == "$platform_name" ]] && platform_selected=true
    done
    $platform_selected || continue

    [[ "$rule_mode" == "managed_block" || "$rule_mode" == "cursor_mdc" ]] ||
      die "unsupported managed rule mode: $rule_name -> $rule_mode"
    rule_source_path="$(expand_path "$rule_source" "$source_root")"
    [[ "$rule_source_path" == "$source_root/"* ]] ||
      die "managed rule source escapes repository: $rule_name -> $rule_source_path"
    [[ -f "$rule_source_path" ]] ||
      die "managed rule source not found: $rule_name -> $rule_source_path"

    rule_target_path="$(expand_path "$target_value" "$repo_root")"
    [[ "$rule_target_path" != "$source_root" && "$rule_target_path" != "$source_root/"* ]] ||
      die "refusing to manage a rule file inside the source repository: $rule_target_path"
    [[ -z "${seen_rule_targets[$rule_target_path]+x}" ]] ||
      die "duplicate managed rule target path: $rule_target_path"
    seen_rule_targets["$rule_target_path"]=1
    rule_state="$(inspect_managed_rule "$rule_name" "$rule_mode" "$rule_target_path" \
      "$rule_source_path" "$legacy_exact")"

    rule_names+=("$rule_name")
    rule_clients+=("$target_client")
    rule_modes+=("$rule_mode")
    rule_sources+=("$rule_source_path")
    rule_targets+=("$rule_target_path")
    rule_legacy+=("$legacy_exact")
    rule_states+=("$rule_state")
  done < <(
    jq -r '
      (.managed_rules // [])[] as $rule |
      $rule.targets[] |
      [
        $rule.name,
        $rule.source,
        ($rule.platforms | join(",")),
        .client,
        .path,
        .mode,
        (.legacy_exact_content // "")
      ] |
      @tsv
    ' "$manifest_path"
  )
fi

echo "machine_id: $machine_id"
echo "platform: $platform_name"
echo "command: $command_name"
echo "scope: $scope"
echo "clients: ${selected_clients[*]}"
echo "manifest: $manifest_path"
if [[ -f "$local_config_path" ]]; then
  echo "local override: $local_config_path"
else
  echo "local override: not configured (using hostname and manifest defaults)"
fi
echo "---"

rule_changes=0
rule_ok=0
rule_conflicts=0
rule_missing_or_stale=0
preflight_rule_conflicts=0
for state in "${rule_states[@]}"; do
  case "$state" in
    UnmanagedFile|Malformed|UnsafeTarget)
      preflight_rule_conflicts=$((preflight_rule_conflicts + 1))
      ;;
  esac
done
block_rule_writes=false
if [[ "$command_name" == "sync" ]] && ! $dry_run && ((preflight_rule_conflicts > 0)); then
  block_rule_writes=true
fi

for index in "${!rule_names[@]}"; do
  number=$((index + 1))
  prefix="[$number/${#rule_names[@]}] [rule:${rule_clients[$index]}] ${rule_names[$index]}"
  state="${rule_states[$index]}"
  target_path="${rule_targets[$index]}"

  case "$state" in
    Current)
      echo "$prefix OK -> $target_path"
      rule_ok=$((rule_ok + 1))
      ;;
    MissingFile|Unmanaged|Legacy|Stale)
      if [[ "$command_name" == "doctor" ]]; then
        echo "$prefix ${state^^} -> $target_path"
        rule_missing_or_stale=$((rule_missing_or_stale + 1))
      elif $dry_run; then
        echo "$prefix would create/update -> $target_path"
        rule_changes=$((rule_changes + 1))
      elif $block_rule_writes; then
        echo "$prefix not updated because managed-rule preflight found a conflict"
      else
        target_parent="$(dirname -- "$target_path")"
        mkdir -p -- "$target_parent"
        temp_path="$(mktemp "$target_parent/.managed-rule.XXXXXX")"
        render_managed_rule_target \
          "${rule_names[$index]}" \
          "${rule_modes[$index]}" \
          "$state" \
          "$target_path" \
          "${rule_sources[$index]}" \
          "$temp_path"
        if [[ -f "$target_path" ]]; then
          chmod --reference="$target_path" "$temp_path"
        fi
        mv -f -- "$temp_path" "$target_path"
        echo "$prefix created/updated -> $target_path"
        rule_changes=$((rule_changes + 1))
      fi
      ;;
    *)
      echo "$prefix CONFLICT: $state -> $target_path" >&2
      rule_conflicts=$((rule_conflicts + 1))
      ;;
  esac
done

if [[ "$command_name" == "sync" && "$rule_conflicts" -gt 0 ]]; then
  echo "---"
  echo "Skills: not processed because managed-rule preflight failed"
  echo "Rules: OK $rule_ok, create/update $rule_changes, missing/stale $rule_missing_or_stale, conflicts $rule_conflicts"
  exit 1
fi

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
echo "Skills: OK $ok, create/repair $created, missing $missing, conflicts $conflicts"
echo "Rules: OK $rule_ok, create/update $rule_changes, missing/stale $rule_missing_or_stale, conflicts $rule_conflicts"

if ((conflicts > 0 || rule_conflicts > 0)) ||
  [[ "$command_name" == "doctor" && ($missing -gt 0 || $rule_missing_or_stale -gt 0) ]]; then
  exit 1
fi
