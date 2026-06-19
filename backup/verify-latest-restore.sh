#!/usr/bin/env bash
set -Eeuo pipefail

: "${DATABASE_URL:?DATABASE_URL is required for source identity checks}"
: "${RESTORE_ADMIN_URL:?RESTORE_ADMIN_URL is required and must target a separate restore server}"

BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_PREFIX="${BACKUP_PREFIX:-patradb-prod}"

latest_archive="$(
  find "${BACKUP_DIR}" -maxdepth 1 -type f -name "${BACKUP_PREFIX}-*.dump" -print \
    | sort \
    | tail -n 1
)"

if [[ -z "${latest_archive}" ]]; then
  echo "No backup archive found in ${BACKUP_DIR}" >&2
  exit 1
fi

checksum_file="${latest_archive}.sha256"
counts_file="${latest_archive}.counts.tsv"
verification_file="${latest_archive}.restore-verified.txt"

[[ -f "${checksum_file}" ]] || { echo "Missing checksum file" >&2; exit 1; }
[[ -f "${counts_file}" ]] || { echo "Missing count manifest" >&2; exit 1; }
sha256sum --check "${checksum_file}"
pg_restore --list "${latest_archive}" >/dev/null

source_db="$(
  psql --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 \
    "${DATABASE_URL}" --command='SELECT current_database()'
)"
restore_admin_db="$(
  psql --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 \
    "${RESTORE_ADMIN_URL}" --command='SELECT current_database()'
)"
source_server="$(
  psql --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 \
    "${DATABASE_URL}" \
    --command="SELECT coalesce(inet_server_addr()::text, 'local') || ':' || inet_server_port()"
)"
restore_server="$(
  psql --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 \
    "${RESTORE_ADMIN_URL}" \
    --command="SELECT coalesce(inet_server_addr()::text, 'local') || ':' || inet_server_port()"
)"

if [[ "${source_db}" != "patradb" ]]; then
  echo "Source safety check failed: expected production database name patradb" >&2
  exit 2
fi
if [[ "${restore_admin_db}" == "patradb" ]]; then
  echo "Restore safety check failed: RESTORE_ADMIN_URL points at production" >&2
  exit 2
fi
if [[ "${DATABASE_URL}" == "${RESTORE_ADMIN_URL}" ]]; then
  echo "Restore safety check failed: source and restore URLs are identical" >&2
  exit 2
fi
if [[ "${source_server}" == "${restore_server}" ]]; then
  echo "Restore safety check failed: source and restore connections reach the same PostgreSQL server" >&2
  exit 2
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
verify_db="patradb_restore_verify_${timestamp,,}_$$"

admin_base="${RESTORE_ADMIN_URL%%\?*}"
admin_query=""
if [[ "${RESTORE_ADMIN_URL}" == *"?"* ]]; then
  admin_query="?${RESTORE_ADMIN_URL#*\?}"
fi
restore_base="${admin_base%/*}"
verify_url="${restore_base}/${verify_db}${admin_query}"

cleanup() {
  dropdb --if-exists --force --maintenance-db="${RESTORE_ADMIN_URL}" "${verify_db}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

createdb --maintenance-db="${RESTORE_ADMIN_URL}" "${verify_db}"
pg_restore \
  --exit-on-error \
  --no-owner \
  --no-privileges \
  --dbname="${verify_url}" \
  "${latest_archive}"

actual_counts="$(mktemp)"
trap 'rm -f "${actual_counts}"; cleanup' EXIT
{
  printf 'table\trow_count\n'
  while IFS=$'\t' read -r table expected; do
    [[ "${table}" == "table" ]] && continue
    [[ "${expected}" == "unavailable" ]] && continue
    actual="$(
      psql --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 \
        "${verify_url}" --command="SELECT count(*) FROM public.${table}"
    )"
    printf '%s\t%s\n' "${table}" "${actual}"
    if [[ "${actual}" != "${expected}" ]]; then
      echo "Restore verification failed for ${table}: expected ${expected}, got ${actual}" >&2
      exit 1
    fi
  done < "${counts_file}"
} > "${actual_counts}"

model_cards="$(
  psql --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 \
    "${verify_url}" --command='SELECT count(*) FROM public.model_cards'
)"
datasheets="$(
  psql --no-psqlrc --tuples-only --no-align --set=ON_ERROR_STOP=1 \
    "${verify_url}" --command='SELECT count(*) FROM public.datasheets'
)"

if (( model_cards < 1 || datasheets < 1 )); then
  echo "Restore verification failed: catalog tables are unexpectedly empty" >&2
  exit 1
fi

{
  echo "verified_utc=${timestamp}"
  echo "archive=$(basename "${latest_archive}")"
  echo "restore_database=${verify_db}"
  echo "model_cards=${model_cards}"
  echo "datasheets=${datasheets}"
  cat "${actual_counts}"
} > "${verification_file}"

echo "Restore verification succeeded for $(basename "${latest_archive}")"
