# Self-hosting Cora

Cora is a local-first application. The default setup serves one user on one
machine. This guide covers remote access, TLS termination, and backups.

## Deployment profiles

| Profile | Use | Setup |
|---|---|---|
| Local (default) | One machine, one user | `docker compose up -d`. The app listens on `http://127.0.0.1:8000`. No login. |
| Remote | LAN or internet access | Same command. Set `CORA_BIND_ADDRESS=0.0.0.0`, `ENABLE_API_KEY_PROTECTION=true`, and `API_ACCESS_KEY` in `.env`. Put a TLS reverse proxy in front. |

Qdrant publishes no host port in either profile.

## Remote access

1. Generate an access key:

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. Set these values in `.env`:

   ```dotenv
   CORA_BIND_ADDRESS=0.0.0.0
   ENABLE_API_KEY_PROTECTION=true
   API_ACCESS_KEY=<generated key>
   ```

3. Start the stack: `docker compose up -d`.

How the protection works:

- Every request to `/v1`, `/api`, and `/query` needs a credential.
- These paths stay public: `/health`, `/live`, `/ready`, `/docs`, `/redoc`,
  `/openapi.json`, and `/api/auth`. The SPA shell and static files stay public
  too.
- The key must have 32 characters or more. `app` and `ingest-worker` refuse to
  start with a shorter key.
- A browser logs in once on a login page. The server sets a `cora_session`
  cookie: HttpOnly, `SameSite=Strict`, `Secure`, valid for 7 days.
- Sign out ends the session on the server. A saved copy of the cookie no
  longer works.
- Cookie-authenticated requests with a method other than GET, HEAD, or OPTIONS
  and a cross-site `Sec-Fetch-Site` header get a 403.
- Scripts and API clients send `X-API-Key: <key>` instead of the cookie.
- The key is env-only. To rotate it, change `.env` and restart the stack. The
  restart also logs out every browser session.

Two credential systems exist:

- The `cora_session` cookie and the `X-API-Key` header are the instance
  credentials. The middleware checks them on every protected path.
- `/v1/memory/*` and `/v1/auth/verify` also require a Bearer JWT in the
  `Authorization` header. With protection on, a caller needs the instance
  credential first and the JWT second. The browser login never issues a JWT,
  so the SPA cannot call the memory endpoints. Scripts get a JWT from
  `POST /v1/auth/token`, which only exists when
  `ENABLE_INSECURE_TOKEN_ENDPOINT=true` and `ENABLE_API_KEY_PROTECTION=true`.

Cookie caveats:

- Safari does not store `Secure` cookies on `http://localhost`. No browser
  stores them on a plain-HTTP LAN IP. Use HTTPS, or set
  `AUTH_COOKIE_SECURE=false` only for plain-HTTP testing.
- Cookie auth is same-origin only. Cross-origin browser clients cannot call
  the API when protection is on.

**Where chats are saved.** Cora saves chats on the server, in the SQLite
database. They sync across your devices. Signing out leaves no chats in the
browser. One person uses each instance. Do not share the access key.

## Reverse proxy

The remote profile needs HTTPS. The session cookie is `Secure`, and browsers
drop it over plain HTTP on remote addresses.

Requirements:

- Terminate TLS at the proxy.
- Forward to `127.0.0.1:8000` when the proxy runs on the same host. When the
  proxy runs on another host, set `CORA_BIND_ADDRESS=0.0.0.0` and forward to
  the host IP.
- Streaming answers use Server-Sent Events on `POST /api/cora-query-stream`.
  Turn off response buffering. Set a read timeout above 45 seconds
  (`RAG_TIMEOUT_MS`).

Caddy gets TLS automatically and flushes `text/event-stream` responses:

```caddyfile
cora.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

The nginx equivalent:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_buffering off;
    proxy_read_timeout 120s;
}
```

Cora has no user accounts, SSO, or roles. Organizations that need them put
Cora behind their existing identity-aware proxy.

## Backup and restore

Run these commands from the directory that contains `docker-compose.yml`.
Create the backup directory first: `mkdir -p backups`.

### SQLite

Back up while the stack runs. `sqlite3.Connection.backup` is safe under WAL.
Never copy a live `cora.db` file and its `-wal` file directly.

```bash
docker compose exec app python -c "import sqlite3; s=sqlite3.connect('/app/db/cora.db'); d=sqlite3.connect('/app/db/cora-backup.db'); s.backup(d); d.close(); s.close()"
docker compose exec app python -c "import sqlite3; d=sqlite3.connect('/app/db/cora-backup.db'); d.execute('DELETE FROM app_settings WHERE key LIKE ?', ('%api_key',)); d.execute('UPDATE app_settings SET value = json_set(value, ?, NULL) WHERE key LIKE ?', ('$.api_key', 'llm_profile_%')); d.commit(); d.execute('VACUUM'); d.close()"
docker compose cp app:/app/db/cora-backup.db ./backups/cora.db
docker compose exec app rm /app/db/cora-backup.db
```

The second command strips provider API keys from the backup copy. It deletes
the `*api_key` rows in `app_settings` and clears the `api_key` field inside
saved LLM profiles. The live database is untouched. Keys set in `.env` are
never in the database. `secret_key` stays in the backup, so memory user-ID
anonymization keeps the same hashes after a restore. The backup also contains
your chats. Skip the second line if you want the keys in the backup. Encrypt
the backup in that case.

### Qdrant

List the collections:

```bash
docker compose exec app curl -s http://qdrant:6333/collections
```

Take a snapshot for `cora_dense_only`, or for your `QDRANT_COLLECTION_NAME`
value if you changed it. Take one for `cora_memories` only if that collection
exists.

```bash
docker compose exec app curl -s -X POST http://qdrant:6333/collections/cora_dense_only/snapshots
# The response contains a "name". Use it in the commands below.
docker compose exec app curl -s -o /tmp/cora_dense_only.snapshot http://qdrant:6333/collections/cora_dense_only/snapshots/<name>
docker compose cp app:/tmp/cora_dense_only.snapshot ./backups/
docker compose exec app rm /tmp/cora_dense_only.snapshot
docker compose exec app curl -s -X DELETE http://qdrant:6333/collections/cora_dense_only/snapshots/<name>
```

### Documents

Copy `./data/documents/` (originals, converted, and metadata). Other content
under `./data`, such as `.cache`, is regenerable and needs no backup.

### Restore

Start on a fresh or wiped stack. `docker compose down -v` removes the
volumes.

1. Copy your saved `./data/documents/` back.
2. Create the containers without starting them:

   ```bash
   docker compose up -d --no-start
   ```

3. Copy the database into the stopped container:

   ```bash
   docker compose cp ./backups/cora.db app:/app/db/cora.db
   ```

4. Fix the file owner. `docker compose cp` writes the file as root, and the
   app runs as UID 1000:

   ```bash
   docker compose run --rm --no-deps --user root app chown 1000:1000 /app/db/cora.db
   ```

5. Start the stack and wait for readiness:

   ```bash
   docker compose up -d
   curl http://127.0.0.1:8000/ready
   ```

   Wait until `/ready` returns 200. If you stripped an LLM key that was saved
   in Settings, `/ready` returns 503 with `setup_required` instead. Step 7
   fixes that.

6. Restore the Qdrant snapshot:

   ```bash
   docker compose cp ./backups/cora_dense_only.snapshot app:/tmp/
   docker compose exec app curl -s -X POST 'http://qdrant:6333/collections/cora_dense_only/snapshots/upload?priority=snapshot' -F 'snapshot=@/tmp/cora_dense_only.snapshot'
   docker compose exec --user root app rm /tmp/cora_dense_only.snapshot
   ```

   The copied file is root-owned, so remove it with `--user root`. The upload
   creates the collection if it does not exist. Repeat for `cora_memories`
   if you backed it up.

7. Re-enter API keys in Settings if you stripped them from the backup. Keys
   that exist only in `.env` work again with no action. When the LLM provider
   was configured in Settings, queries fail until you re-enter the LLM key.
   The saved provider config takes precedence over `.env`.
8. Verify the restore. `/ready` returns 200, the Documents page lists your
   documents, and a question about a document returns a cited answer.

> **Backups can contain secrets.** The database backup keeps the instance
> `secret_key`, the key behind memory user-ID anonymization. Keep backups
> private and encrypted. If you skipped the strip line above, the backup also
> holds provider API keys in plain text in the `app_settings` table.

## Limitations

- Single tenant. One shared corpus for everyone on the instance.
- One host. SQLite and one app instance. No horizontal scaling.
- No user accounts, roles, or SSO.
- No application-level rate limiting, including on login. A random key of 32
  characters or more makes guessing infeasible. Add rate limiting at the
  proxy if you want it.
- `/docs`, `/openapi.json`, and the health endpoints are public by design.
- Two instances on one host share the session cookie. Cookies ignore the
  port, so the second login overwrites the first session. Use one hostname
  per instance.
- Values in `.env` are visible to anyone with Docker daemon access
  (`docker inspect`).
