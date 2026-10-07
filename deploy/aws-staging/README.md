# AWS $100-credit staging deployment

This directory is intentionally **staging-only**. The repository's own release notes still say production is not approved because business, device, staff/UAT and other release gates remain open. Do not use this recipe as evidence of production readiness.

## Why this shape

The current app was release-tested against:

- Frappe `v16.34.0`
- ERPNext `v16.35.0`
- HRMS `v16.19.0`
- Python `3.14.4`
- Node `24.15.0`

The bootstrap script pins those versions and builds the private `tradex_hr` app into the container image, rather than installing source into a running container.

The current upstream `frappe_docker` compose file pins `linux/amd64`, so this recipe deliberately targets an **x86_64 EC2 instance**. A `t3a.medium` or `t3.medium` class instance (2 vCPU / 4 GiB RAM) is a practical staging baseline. A 2 GiB instance may boot with swap but is not recommended for the image build plus the full Frappe/MariaDB/Redis worker set.

## AWS Free Plan fit

New AWS accounts can receive $100 in credits and the Free account plan is time/credit-limited. This deployment is designed to consume those credits cheaply by keeping everything on one EC2 VM:

- one EC2 instance
- one root gp3 EBS volume
- MariaDB in Docker on the same host
- Redis in Docker on the same host
- no RDS
- no NAT Gateway
- no load balancer

It is not a forever-free hosting design. Preserve backups before the Free plan or credits expire.

## EC2 launch settings

Use Ubuntu 24.04 LTS, **x86_64**, and preferably `t3a.medium` (fallback `t3.medium`). Start with a 30 GiB gp3 root volume.

For the security group, initially allow only:

- TCP 22 from your own public IP
- TCP 8080 from your own public IP

Do not open MariaDB or Redis ports to the internet.

## Deploy

SSH to the instance, clone this branch, then run:

```bash
git clone --branch deploy/aws-free-staging https://github.com/shamrat05/tradexcel-hr-v16.git
cd tradexcel-hr-v16
sudo bash deploy/aws-staging/bootstrap.sh
```

Because this repository is private, Git may ask for authentication for the initial clone. The bootstrap then asks once for a GitHub token that has **read-only Contents access** to `shamrat05/tradexcel-hr-v16`. It passes the app definition as a Docker BuildKit secret and removes the temporary token file after the image build.

At completion, the script prints the staging URL and a generated Administrator password. The generated database/admin passwords are stored only on the EC2 host at:

```text
/opt/tradexcel-frappe/staging.secrets
```

## What the script does

1. installs Docker/Compose prerequisites;
2. creates a 4 GiB swap file for the one-time build;
3. pins `frappe_docker` to commit `e08b50ca057139c6e8c9117838ee3f5c5ee64a37`;
4. builds Frappe/ERPNext/HRMS/Tradexcel at the tested v16 versions;
5. runs MariaDB, Redis, backend, websocket, scheduler, queues and frontend with Docker Compose;
6. creates a fresh neutral site named `hrms-staging.localhost`;
7. installs `erpnext`, `hrms` and `tradex_hr`;
8. runs migrate, enables the scheduler, clears cache and performs an HTTP check.

No real employee/payroll backup is restored by this recipe.

## Operations

Show status:

```bash
cd /opt/tradexcel-frappe/frappe_docker
docker compose -p tradexcel -f /opt/tradexcel-frappe/compose.custom.yaml ps
```

Follow logs:

```bash
docker compose -p tradexcel -f /opt/tradexcel-frappe/compose.custom.yaml logs -f --tail=200
```

Stop without deleting persistent data:

```bash
docker compose -p tradexcel -f /opt/tradexcel-frappe/compose.custom.yaml down
```

Start again:

```bash
docker compose -p tradexcel -f /opt/tradexcel-frappe/compose.custom.yaml up -d
```

Do **not** add `-v` to `docker compose down` unless you intentionally want to delete the site/database volumes.

## Before any real data

Keep this instance as staging until the repository's release blockers are resolved. If a real backup is ever introduced, take and verify a fresh backup first and follow the repository's `BACKUPS.md` and release-readiness rules.
