# Deploy Webclaw, ERPClaw, and AutomotiveClaw on Railway

This is the web front end for ERPClaw's Automotive edition. The books live in
Railway Postgres. Uploaded title scans and deal paperwork live in a Railway
Bucket. The dashboard login lives in a small SQLite file on a volume, separate
from the books.

Nothing here is pointed at an existing production database. A first boot
creates schema with ERPClaw's own `initialize-database` and does **not** pass
`--force`. If company rows already exist, startup leaves them alone.

## Service layout

Three Railway services from this one repo, plus Postgres and a bucket:

| Service | Root directory | What it runs |
|---|---|---|
| `api` | repository root | FastAPI, ERPClaw, AutomotiveClaw. Listens on Railway's `PORT`. |
| `web` | `web` | Next.js production build. The public site. |
| `backup` | `deploy/backup` | Cron `pg_dump` into the bucket. |
| Postgres | Railway plugin | The books. |
| Bucket | Railway bucket | Scans and nightly dumps. |

`api` and `web` are split so the ERPClaw tree (Python, pinned to a git commit)
and the Next.js app build and restart on their own. The browser talks only to
`web`. `web` forwards `/api/v1/*` to the API service's private address when the
request arrives. That replaces the nginx `/api/v1` → port 8001 proxy. A
`next.config` rewrite would freeze the private URL into the image at build
time, and Railway assigns that URL after the service exists, so the forwarder
is a route handler instead.

The API image clones these forks at build time. The defaults are the commits
this layout was verified against:

| Build arg | Default |
|---|---|
| `ERPCLAW_REPO` | `https://github.com/cscruggs10/erpclaw.git` |
| `ERPCLAW_REF` | `aea97950a7d78615fc06d1d129c17c7775b38581` |
| `AUTOMOTIVE_REPO` | `https://github.com/cscruggs10/automotiveclaw.git` |
| `AUTOMOTIVE_REF` | `6123ef7575dde4f3b706c8fff5967717d4c587db` |

Change a ref in the Dockerfile `ARG` line, or pass the same name as a Docker
build arg, when you want a newer commit. Do not track a moving branch in
production.

ERPClaw's Postgres switch is `ERPCLAW_DB_DIALECT=postgresql` plus
`ERPCLAW_DB_URL`. Startup copies `DATABASE_URL` into both, and also into
`ERPCLAW_DB_PATH`, because AutomotiveClaw's `init_db.py` reads `ERPCLAW_DB_PATH`.
`postgres://` is rewritten to `postgresql://`. If `DATABASE_URL` is absent, the
books fall back to SQLite at `$ERPCLAW_HOME/data.sqlite` and the log says
`sqlite fallback`. Use that only with the `/data` volume attached. Postgres is
the setup to use for the real books.

Cross-skill calls (the chart-of-accounts step that sets default accounts, and
AutomotiveClaw creating a core customer) look up an `erpclaw` skill directory.
The image puts the ERPClaw checkout at `/opt/skills/erpclaw` and sets
`OPENCLAW_SKILLS_DIR=/opt/skills`, which is the override ERPClaw already
checks. `ERPCLAW_HOME=/data/erpclaw` is the install root (shared library
symlink and installed modules), not the database.

## What you do in Railway

Do this in a **new** project. Do not attach a database that already holds the
live books until you have a dump of those books stored somewhere else and you
have read the safety section below.

1. Create a project, for example `erpclaw`.
2. Add **Postgres**. Leave the default database name. You will reference its
   `DATABASE_URL`; you do not copy the password into a file.
3. Add a **Bucket** for scans and backups. Open the bucket credentials and
   keep that panel available for step 6.
4. Add a service named `api` from `https://github.com/cscruggs10/webclaw`.
   - Root directory: empty (the repository root).
   - Builder: Dockerfile. Railway reads `/railway.toml` and `/Dockerfile`.
   - Add a volume mounted at **`/data`**. The service config requires this
     path. One replica only; the volume cannot be shared, and the dashboard
     login database on that volume must not be written by two containers.
5. Add a service named `web` from the same repo.
   - Root directory: `web`.
   - Railway then uses `web/railway.toml` and `web/Dockerfile`.
   - Generate a public domain on **`web` only**. Leave `api` private.
6. Add a service named `backup` from the same repo.
   - Root directory: `deploy/backup`.
   - `deploy/backup/railway.toml` schedules it at 08:00 UTC. No public domain.
7. Set variables from the tables below, then deploy `api` first. Wait until
   its health check is green before opening the web domain. The first boot
   creates the schema, installs the automotive tables, and (only when the
   company table is empty and `COMPANY_NAME` is set) creates the company and
   the US GAAP chart. That chart step is what used to fail with
   `erpclaw is not installed` on a non-OpenClaw layout; if it fails now, the
   container exits and does not serve traffic.
8. Open `https://<web-domain>/login` and sign in with `ADMIN_EMAIL` and
   `ADMIN_PASSWORD`.

Railway variable references, typed exactly:

- On `api` and `backup`: `DATABASE_URL=${{Postgres.DATABASE_URL}}`
  (use the Postgres service's real name if you did not call it `Postgres`).
- On `web`: `API_INTERNAL_URL=http://${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}`
- On `web`: `API_URL` set to the same value. The UI loader uses it when a
  skill's `UI.yaml` is not in the web image.

Bucket credentials go on `api` and `backup`. Railway shows them as an
endpoint, bucket name, access key, and secret. Map them to the `AWS_*` or
`S3_*` names in the table. Either prefix works.

## Environment variables

### `api`

| Variable | Required | Value |
|---|---|---|
| `DATABASE_URL` | Yes | `${{Postgres.DATABASE_URL}}` |
| `ERPCLAW_DB_URL` | No | Leave unset. Filled from `DATABASE_URL`. Set it only to override. |
| `ERPCLAW_DB_DIALECT` | No | Leave unset. Becomes `postgresql` when a URL is present. |
| `ERPCLAW_DB_PATH` | No | Leave unset. Set to the same URL so AutomotiveClaw's init can see it. Do not point this at a file path while `DATABASE_URL` is set. |
| `ERPCLAW_HOME` | No | `/data/erpclaw` (image default). Library symlink and modules. |
| `SKILLS_DIR` | No | `/opt/skills` (image default). |
| `OPENCLAW_SKILLS_DIR` | No | `/opt/skills` (image default). This is what fixes cross-skill calls. |
| `ERPCLAW_DIR` | No | `/opt/skills/erpclaw` |
| `AUTOMOTIVE_DIR` | No | `/opt/skills/automotiveclaw` |
| `WEBCLAW_DB_PATH` | No | `/data/webclaw/webclaw.sqlite`. Dashboard users and sessions. Not the books. |
| `WEBCLAW_JWT_SECRET` | Yes | `openssl rand -hex 32`. At least 32 characters. Never commit it. |
| `ADMIN_EMAIL` | Yes | Your login email. |
| `ADMIN_PASSWORD` | Yes | First-boot password. At least 8 characters with upper, lower, and a digit. Stored as a hash. **Not changed on restart.** |
| `ADMIN_NAME` | No | Display name. Defaults to the email's local part. |
| `COMPANY_NAME` | For a new empty database | Legal name, for example the wholesale business name. Ignored when any company already exists. |
| `COMPANY_ABBR` | No | Short code. ERPClaw derives one from the name when this is empty. |
| `COMPANY_CURRENCY` | No | `USD` |
| `COMPANY_COUNTRY` | No | `United States` |
| `COMPANY_FISCAL_MONTH` | No | `1` for January. |
| `CHART_TEMPLATE` | No | `us_gaap` |
| `WEBCLAW_ENV` | No | `production` |
| `WEBCLAW_HTTPS` | Yes on Railway | `true`. Marks the refresh cookie `Secure` behind Railway's TLS. |
| `WEBCLAW_CORS_ORIGIN` | No | `https://<web-domain>`. Matters only if a browser calls the API host directly. The normal UI is same-origin through `web`. |
| `PORT` | Set by Railway | Do not hard-code. |
| `UPLOAD_DIR` | No | `/data/uploads` when the bucket is not configured. |
| `STORAGE_BACKEND` | No | `s3` or `volume`. Unset means `s3` when bucket credentials exist, otherwise the volume. |
| `S3_BUCKET` or `AWS_S3_BUCKET_NAME` or `BUCKET` | For scans | Bucket name from the credentials panel. |
| `S3_ACCESS_KEY_ID` or `AWS_ACCESS_KEY_ID` or `ACCESS_KEY_ID` | For scans | Access key. |
| `S3_SECRET_ACCESS_KEY` or `AWS_SECRET_ACCESS_KEY` or `SECRET_ACCESS_KEY` | For scans | Secret key. |
| `S3_ENDPOINT` or `AWS_ENDPOINT_URL` or `AWS_S3_ENDPOINT` or `ENDPOINT` | For Railway buckets | The S3 endpoint, not the AWS public one. |
| `S3_REGION` or `AWS_DEFAULT_REGION` or `REGION` | No | `us-east-1`. The value `auto` is treated as `us-east-1`. |
| `S3_PREFIX` | No | `uploads` |
| `WEBCLAW_COMPANY_SKILLS` | No | `automotiveclaw`. Skills that should receive the default company id. |
| `WEBCLAW_SHARED_DB_SKILLS` | No | `automotiveclaw`. Skills that read the shared books. |

### `web`

| Variable | Required | Value |
|---|---|---|
| `API_INTERNAL_URL` | Yes | `http://${{api.RAILWAY_PRIVATE_DOMAIN}}:${{api.PORT}}` |
| `API_URL` | Yes | Same as `API_INTERNAL_URL`. |
| `PORT` | Set by Railway | Do not hard-code. |
| `NEXT_PUBLIC_OCUI_TITLE` | No | Shown on the login screen. Example: `ERPClaw`. |

### `backup`

| Variable | Required | Value |
|---|---|---|
| `DATABASE_URL` | Yes | `${{Postgres.DATABASE_URL}}` |
| Bucket variables | Yes | Same names as on `api`. |
| `BACKUP_PREFIX` | No | `backups` |
| `BACKUP_REQUIRE_S3` | No | `1`. The job fails if the bucket is not configured, instead of leaving a dump on ephemeral disk. |

Build args are Docker build-time only. They are not runtime secrets.

## First login

1. Wait until `api` logs `erpclaw schema initialized`, `automotive schema initialized`, and either `created company from COMPANY_NAME` or `company row(s) already present`.
2. Open the `web` domain `/login`.
3. Sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
4. ERPClaw and AutomotiveClaw appear as skills. A file stored from the API
   (`POST /api/v1/files/upload`, bearer token, multipart field `file`) returns
   a `/api/v1/files/<key>` URL you can put in a vehicle photo or deal note.
   Those URLs require the same login. The bucket is not public.

Changing `ADMIN_PASSWORD` later in the Railway variables does **not** change
the password of a user that already exists. Use the in-app change-password
screen, or set a new password from a one-off shell against the dashboard
database. Rotating `WEBCLAW_JWT_SECRET` signs everyone out, which is what you
want, and does not touch the books.

## Nightly backups

`backup` runs `pg_dump --format=custom` and writes
`backups/erpclaw-<timestamp>.dump` to the bucket. Railway cron uses UTC.
`0 8 * * *` is 08:00 UTC. Edit `cronSchedule` in `deploy/backup/railway.toml`
to move it. The job does not delete older dumps. Add a bucket lifecycle rule
yourself if you want a retention window; this repo will not delete a dump on
its own.

Restore is a manual act, on a database you can afford to replace:

```bash
pg_restore --no-owner --no-acl --dbname "$DATABASE_URL" erpclaw.dump
```

Take a fresh dump before you restore. If `pg_dump` reports that the server is
newer than the client, bump the `postgres:` tag in `deploy/backup/Dockerfile`
to at least that major version and redeploy the cron service.

## Safety

- `initialize-database` is ERPClaw's normal idempotent schema setup
  (`CREATE TABLE IF NOT EXISTS`). This image never passes `--force`.
- Startup creates a company only when `COMPANY_NAME` is set **and** the
  company table is empty. An existing company, chart, customer, or vehicle is
  not updated.
- The dashboard password is written only when there are zero users.
- Logs are passed through a redactor for `postgresql://` URLs and password
  assignments. Do not add debug flags that print the environment.
- Keep `api` off the public internet. The web service is the door.
- The `/data` volume holds the dashboard SQLite file, the ERPClaw library
  symlink, and volume-mode uploads. Losing the volume loses logins and any
  file that was not in the bucket. It does not drop the Postgres books.
- Do not scale `api` past one replica while the dashboard database is SQLite.
- SQLite for the books is the fallback when `DATABASE_URL` is missing. Do not
  use it for the live wholesale books.

Importing an existing set of books is a separate step from this deploy. Boot
this project against the new empty Postgres first and confirm login, a
customer, and a vehicle. Only then plan a restore, with a dump taken first,
and with `COMPANY_NAME` left unset if that dump already contains the company.

## Local check

```bash
docker compose up --build
```

The compose file uses a throwaway Postgres password and `Local-Test-1` as the
dashboard password. Those exist so the stack can boot on a laptop. Do not
reuse them on Railway.

```bash
sh deploy/smoke.sh
docker compose restart api
sh deploy/smoke-after-restart.sh
```

The first script logs in, checks that both modules are listed, adds a
customer through AutomotiveClaw (that path calls back into ERPClaw), adds a
Ford F-150, uploads a file, and rotates the password. The second script
restarts the API and checks the rotated password still works, which is how
you know boot did not write `ADMIN_PASSWORD` back over the hash.
