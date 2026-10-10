# Workforce Suite staging performance and traffic setup

This directory contains reproducible edge configuration for a native Ubuntu
Bench. It is staging infrastructure, not a production approval or a promise
of millisecond end-to-end browser latency.

## Native host proxy

Use `nginx-native.conf.template` when Gunicorn listens on `127.0.0.1:8000`
and Frappe Socket.IO listens on `127.0.0.1:9000`. Replace `BENCH_ROOT` and
`SITE_NAME`, validate with `nginx -t`, then reload Nginx. The template fixes the
failure modes seen on staging:

- content-addressed assets are served directly with one-year immutable caching;
- JavaScript/CSS/JSON are gzip-compressed;
- the Socket.IO proxy preserves the public host and matching origin required by
  Frappe v16;
- API and Desk responses remain uncached;
- WebSocket and upstream timeouts are explicit.

Use native Bench/systemd workers and Redis queue/cache endpoints; do not put
Redis or MariaDB on a public listener.

## Optional ALB

`alb.yaml` is an optional CloudFormation template for an internet-facing HTTP
Application Load Balancer with one EC2 target. It requires two public subnets,
the existing instance ID and its security-group ID. It forwards port 80 to the
host's Frappe proxy port 8080 and health-checks `/api/method/frappe.ping`.

Do not deploy this template merely to make one instance faster. An ALB adds
recurring AWS cost and a network hop; it becomes useful for TLS termination,
health-based replacement, or multiple application instances. For real use,
add an ACM certificate and HTTPS listener, redirect HTTP to HTTPS, restrict the
instance security group to the ALB security group, and keep SSH separately
restricted. Never expose MariaDB, Redis, Gunicorn, or Socket.IO's private port.

## Performance boundary

Compression and immutable asset caching reduce transfer and first-load time.
They cannot guarantee millisecond browser interaction: network RTT, JavaScript
parse/execute time, native Frappe metadata, and device CPU are separate costs.
Measure server response time, asset transfer, browser scripting, and real device
UX independently. A first-use Import/Print dialog may lazily load native Frappe
bundles; subsequent uses should be cached.

Validate every deployment with:

```bash
nginx -t
curl -fsS http://127.0.0.1:8080/api/method/frappe.ping
curl -fsSI -H 'Accept-Encoding: gzip' http://127.0.0.1:8080/assets/frappe/dist/js/desk.bundle.*.js
```

The last response should include `Content-Encoding: gzip` and an immutable
cache policy. Browser verification must still check console errors, Socket.IO,
mobile menu actions, Import, Print, and a read-only Desk journey.
