#!/usr/bin/env sh
set -eu
if [ ! -f compose.yaml ]; then echo 'Run this from the siteforge folder'; exit 1; fi
printf '\n1. Compose frontend container and port:\n'
docker compose ps frontend
printf '\n2. Built frontend image ID:\n'
docker compose images frontend
printf '\n3. Running frontend bundled CSS marker:\n'
docker compose exec -T frontend sh -c 'grep -R -l "zb-theme-release" /usr/share/nginx/html/assets/*.css || true'
printf '\n4. Running frontend JS release marker:\n'
docker compose exec -T frontend sh -c 'grep -R -l "Daylight UI" /usr/share/nginx/html/assets/*.js || true'
printf '\nIf both are blank, the running frontend is not this build.\n'
printf 'If both exist but browser shows old theme, check the website hostname/reverse proxy, service workers and browser cache.\n'
