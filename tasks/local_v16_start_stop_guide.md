# Local v16 site: start, check, stop

Use `/home/sanchita/frappe-bench-v16` for the bench and site
`hrms-v16.localhost`. The intended MariaDB data directory is
`/home/sanchita/mariadb-v16` on `127.0.0.1:3307`; do not substitute the
separate system MariaDB on port 3306 or edit site credentials.

## Start

In terminal 1, first check whether port 3307 is already listening:

```sh
ss -ltnp | grep ':3307'
```

If it is not, start the existing v16 data directory and leave this terminal
open:

```sh
mariadbd --no-defaults \
  --datadir=/home/sanchita/mariadb-v16 \
  --socket=/home/sanchita/mariadb-v16/mysql.sock \
  --pid-file=/home/sanchita/mariadb-v16/mariadb.pid \
  --port=3307 --bind-address=127.0.0.1 --user=sanchita \
  --log-error=/home/sanchita/mariadb-v16/mariadb.log
```

In terminal 2, from the bench directory, create a temporary Procfile with one
Redis process. The checked-in Procfile starts two Redis servers on port 6380,
so `bench start` with it exits. Keep this temporary process file outside the
repository:

```sh
cd /home/sanchita/frappe-bench-v16
cat > /tmp/workforce-hr-v16-Procfile <<'EOF'
redis_cache: redis-server config/redis_cache.conf
web: bench serve --port 8001
socketio: bench socketio
watch: bench watch
schedule: bench schedule
worker: bench worker 1>> logs/worker.log 2>> logs/worker.error.log
EOF
PATH=/home/sanchita/.nvm/versions/node/v24.15.0/bin:$PATH \
  bench start -p /tmp/workforce-hr-v16-Procfile
```

Node 24 is required by the asset watcher; the system Node 20 makes `watch`
exit and causes the whole bench process group to stop. The command above uses
the installed Node 24 without changing the global Node version. Leave terminal
2 open while using the site.

## Check

In a third terminal:

```sh
cd /home/sanchita/frappe-bench-v16
bench --site hrms-v16.localhost list-apps
curl -fsS -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:8001
```

The site should report HTTP 200. Bench web is at `http://127.0.0.1:8001` and
Socket.IO at port 9001.

## Stop

Press **Ctrl-C once in terminal 2** and wait for bench to stop its web,
Socket.IO, watcher, scheduler, worker and Redis processes. Then press **Ctrl-C
in terminal 1** to stop the standalone v16 MariaDB cleanly. Do not kill the
system MariaDB service or remove database files. If either service was already
running before this session, leave it running.

## Verified on 2026-09-25

The v16 database answered through the site's configured connection,
`list-apps` reported Frappe 16.34 / ERPNext 16.35 / HRMS 16.19 / `workforce_suite`,
the full local bench processes started with the commands above, and the site
returned HTTP 200. The Redis config emits a Linux memory-overcommit warning;
it did not prevent startup. No sysctl or site configuration was changed.

## Separate local web process (2026-09-26 verified)

When starting web outside `bench start`, use `DEV_SERVER=1 bench --site
hrms-v16.localhost serve --port 8001` from the v16 bench. The flag tells the
Desk client to use Socket.IO port 9001 instead of expecting a reverse proxy
on port 8001. Use `http://127.0.0.1:8001` when the WSL resolver has no entry
for `hrms-v16.localhost`; the configured default site remains the v16 site.
No site/DB credentials or system MariaDB settings need changing.
