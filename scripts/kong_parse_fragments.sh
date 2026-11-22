#!/usr/bin/env sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
image=$(sed -n 's/^KONG_IMAGE=//p' "$repo_root/.env.example" | head -n 1)
if [ -z "$image" ]; then
  echo "KONG_IMAGE is not defined in .env.example" >&2
  exit 1
fi

temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/kong-fragments.XXXXXX")
trap 'rm -rf "$temp_dir"' EXIT HUP INT TERM

write_merged_config() {
  output=$1
  fragment=$2
  cat > "$output" <<'YAML'
_format_version: "3.0"
services:
  - name: mock-upstream
    url: http://mock-upstream:8080
    routes:
      - name: mock-route
        paths:
          - /mock
        strip_path: true
consumers:
  - username: fintech-free
  - username: fintech-premium
plugins:
YAML
  if ! grep -q '^plugins:$' "$fragment"; then
    echo "Expected a top-level plugins: list in $fragment" >&2
    exit 1
  fi
  sed -n '/^plugins:$/,$p' "$fragment" | sed '1d' >> "$output"
}

write_merged_config "$temp_dir/ratelimit.yml" "$repo_root/kong/fragments/20-ratelimit.yml"
write_merged_config "$temp_dir/transform.yml" "$repo_root/kong/fragments/30-transform.yml"

for filename in ratelimit.yml transform.yml; do
  echo "Parsing $filename with $image"
  docker run --rm -v "$temp_dir:/c:ro" "$image" kong config parse "/c/$filename"
done
