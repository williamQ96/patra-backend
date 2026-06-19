#!/usr/bin/env bash
set -Eeuo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"

BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-3600}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
BACKUP_PREFIX="${BACKUP_PREFIX:-patradb-prod}"

case "${BACKUP_INTERVAL_SECONDS}" in
  ''|*[!0-9]*) echo "BACKUP_INTERVAL_SECONDS must be a positive integer" >&2; exit 2 ;;
esac
case "${BACKUP_RETENTION_DAYS}" in
  ''|*[!0-9]*) echo "BACKUP_RETENTION_DAYS must be a non-negative integer" >&2; exit 2 ;;
esac

mkdir -p "${BACKUP_DIR}"
umask 077

backup_once() {
  local timestamp stem temporary archive list_file counts_file checksum_file
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  stem="${BACKUP_PREFIX}-${timestamp}"
  temporary="${BACKUP_DIR}/.${stem}.dump.partial"
  archive="${BACKUP_DIR}/${stem}.dump"
  list_file="${archive}.list"
  counts_file="${archive}.counts.tsv"
  checksum_file="${archive}.sha256"

  if [[ -e "${archive}" ]]; then
    echo "Refusing to overwrite existing backup ${archive}" >&2
    return 1
  fi

  trap 'rm -f "${temporary}" "${list_file}.partial" "${counts_file}.partial" "${checksum_file}.partial"' RETURN

  echo "[$(date -u +%FT%TZ)] Starting PostgreSQL backup ${stem}"
  PGAPPNAME=patra-hourly-backup pg_dump \
    --format=custom \
    --compress=9 \
    --no-owner \
    --no-privileges \
    --file="${temporary}" \
    "${DATABASE_URL}"

  pg_restore --list "${temporary}" > "${list_file}.partial"

  {
    printf 'table\trow_count\n'
    for table in model_cards datasheets experiments events power_summary; do
      count="$(
        PGAPPNAME=patra-hourly-backup-counts psql \
          --no-psqlrc \
          --tuples-only \
          --no-align \
          --set=ON_ERROR_STOP=1 \
          "${DATABASE_URL}" \
          --command="SELECT count(*) FROM public.${table}" 2>/dev/null \
          || printf 'unavailable'
      )"
      printf '%s\t%s\n' "${table}" "${count}"
    done
  } > "${counts_file}.partial"

  mv "${temporary}" "${archive}"
  mv "${list_file}.partial" "${list_file}"
  mv "${counts_file}.partial" "${counts_file}"
  sha256sum "${archive}" > "${checksum_file}.partial"
  mv "${checksum_file}.partial" "${checksum_file}"

  echo "[$(date -u +%FT%TZ)] Backup completed: ${archive}"

  if (( BACKUP_RETENTION_DAYS > 0 )); then
    find "${BACKUP_DIR}" -maxdepth 1 -type f \
      -name "${BACKUP_PREFIX}-*.dump*" \
      -mtime "+${BACKUP_RETENTION_DAYS}" \
      -delete
  fi
}

if [[ "${1:-}" == "once" ]]; then
  backup_once
  exit
fi

while true; do
  if ! backup_once; then
    echo "[$(date -u +%FT%TZ)] Backup failed; existing backups were left untouched" >&2
  fi
  sleep "${BACKUP_INTERVAL_SECONDS}"
done
