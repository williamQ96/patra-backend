# Patra production database backup and restore verification

Production backups run in a dedicated pod and write to the separate
`patradbbackups` Tapis volume. The Patra application must never use the backup
or restore-verification database as its `DATABASE_URL`.

## Safety invariants

- The production database is read with `pg_dump`; backup scripts never issue
  `DROP`, `TRUNCATE`, `DELETE`, schema migrations, or seed commands against it.
- Every archive has a timestamped name and is written atomically. Existing
  archives are never overwritten.
- Each archive includes a SHA-256 checksum, `pg_restore --list` output, and key
  table counts.
- Restore verification requires a separate PostgreSQL server. It refuses to
  run if the restore admin connection reports the production database name or
  if both connections report the same PostgreSQL server address and port.
- The verifier creates only a temporary database named
  `patradb_restore_verify_*`, compares restored counts, and removes that
  temporary database when finished.

## Build

```bash
docker build \
  -f backup/Dockerfile \
  -t plalelab/patra-backend:<immutable-db-backup-release-tag> \
  .
docker push plalelab/patra-backend:<immutable-db-backup-release-tag>
```

Never deploy the mutable `latest` tag for backup infrastructure.

## Configure hourly backups

Start from `backup/pod-config.backup.example.json`.

- Supply `DATABASE_URL` through the Tapis secret/config mechanism. Prefer a
  PostgreSQL role with only the privileges required by `pg_dump`.
- When the backup pod reaches the database through the public pod hostname,
  use external TLS port `443` with `sslmode=require`; internal application
  port `5432` may not be reachable from a separate pod.
- Mount a dedicated Tapis volume at `/backups`.
- Keep `BACKUP_INTERVAL_SECONDS=3600`.
- Keep a finite `PGCONNECT_TIMEOUT` (the deployment default is 30 seconds) so
  a networking regression fails the current attempt instead of blocking the
  hourly loop indefinitely.
- The default retention is 14 days. Retention removes only expired files from
  the backup volume; it never touches the live database.

The pod performs one backup immediately at startup, then repeats hourly.

## Required pre-deployment restore gate

Before changing the production backend, frontend, pod configuration, or
database schema:

1. Run the backup image once with argument `once`.
2. Record the `.dump`, `.sha256`, `.counts.tsv`, and `.list` files.
3. Start a separate PostgreSQL restore-verification server with its own volume.
   A different database on the production PostgreSQL server is not sufficient.
4. Run `verify-latest-restore.sh` with:
   - `DATABASE_URL` pointing to production using a read-only backup role;
   - `RESTORE_ADMIN_URL` pointing to the isolated restore server.
5. Require a generated `.restore-verified.txt` file containing non-zero
   `model_cards` and `datasheets` counts before deployment proceeds.

Do not substitute `pg_restore --list` for an actual restore verification.

## Recovery

Recovery must first target a new database or new PostgreSQL pod. Validate key
counts and application reads there before changing any application
`DATABASE_URL`. Never restore directly over `patradb`.
