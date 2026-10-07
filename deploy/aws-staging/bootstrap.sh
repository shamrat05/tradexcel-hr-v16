#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if [ "${EUID}" -ne 0 ]; then
  echo "Run this script as root, for example: sudo bash deploy/aws-staging/bootstrap.sh"
  exit 1
fi

if [ "$(uname -m)" != "x86_64" ]; then
  echo "This staging recipe targets x86_64 because the current frappe_docker compose pins linux/amd64."
  echo "Use an AWS t3/t3a x86_64 instance, not t4g/Graviton, for this recipe."
  exit 1
fi

SITE_NAME="${SITE_NAME:-hrms-staging.localhost}"
PROJECT_NAME="${PROJECT_NAME:-tradexcel}"
HTTP_PORT="${HTTP_PORT:-8080}"
WORKDIR="${WORKDIR:-/opt/tradexcel-frappe}"
FRAPPE_DOCKER_SHA="e08b50ca057139c6e8c9117838ee3f5c5ee64a37"
FRAPPE_VERSION="v16.34.0"
ERPNEXT_VERSION="v16.35.0"
HRMS_VERSION="v16.19.0"
CUSTOM_APP_BRANCH="deploy/aws-free-staging"
IMAGE_NAME="tradexcel-hr"
IMAGE_TAG="16.34.0-aws-staging"

echo "Installing host prerequisites..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git jq openssl

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required but was not found."
  exit 1
fi

# A small swap file makes the one-time custom image build much less likely to OOM.
if ! swapon --show=NAME --noheadings | grep -qx '/swapfile'; then
  if [ ! -f /swapfile ]; then
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
  fi
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

mkdir -p "${WORKDIR}"
chmod 700 "${WORKDIR}"

FRAPPE_DOCKER_DIR="${WORKDIR}/frappe_docker"
if [ ! -d "${FRAPPE_DOCKER_DIR}/.git" ]; then
  git clone https://github.com/frappe/frappe_docker.git "${FRAPPE_DOCKER_DIR}"
fi
cd "${FRAPPE_DOCKER_DIR}"
git fetch --all --tags --prune
git checkout --detach "${FRAPPE_DOCKER_SHA}"

echo
read -r -s -p "GitHub token with read access to shamrat05/tradexcel-hr-v16: " GITHUB_TOKEN
echo
if [ -z "${GITHUB_TOKEN}" ]; then
  echo "A read-only GitHub token is required because the app repository is private."
  exit 1
fi

APPS_JSON="$(mktemp)"
trap 'rm -f "${APPS_JSON}"; unset GITHUB_TOKEN' EXIT

cat > "${APPS_JSON}" <<EOF
[
  {
    "url": "https://github.com/frappe/erpnext",
    "branch": "${ERPNEXT_VERSION}"
  },
  {
    "url": "https://github.com/frappe/hrms",
    "branch": "${HRMS_VERSION}"
  },
  {
    "url": "https://x-access-token:${GITHUB_TOKEN}@github.com/shamrat05/tradexcel-hr-v16.git",
    "branch": "${CUSTOM_APP_BRANCH}"
  }
]
EOF

echo "Building the pinned Frappe v16 staging image..."
DOCKER_BUILDKIT=1 docker build \
  --no-cache \
  --build-arg="PYTHON_VERSION=3.14.4" \
  --build-arg="NODE_VERSION=24.15.0" \
  --build-arg="FRAPPE_PATH=https://github.com/frappe/frappe" \
  --build-arg="FRAPPE_BRANCH=${FRAPPE_VERSION}" \
  --secret="id=apps_json,src=${APPS_JSON}" \
  --tag="${IMAGE_NAME}:${IMAGE_TAG}" \
  --file=images/custom/Containerfile .

rm -f "${APPS_JSON}"
unset GITHUB_TOKEN
trap - EXIT

SECRETS_FILE="${WORKDIR}/staging.secrets"
if [ -f "${SECRETS_FILE}" ]; then
  # shellcheck disable=SC1090
  source "${SECRETS_FILE}"
else
  DB_PASSWORD="$(openssl rand -hex 24)"
  ADMIN_PASSWORD="$(openssl rand -hex 18)"
  cat > "${SECRETS_FILE}" <<EOF
DB_PASSWORD=${DB_PASSWORD}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
EOF
  chmod 600 "${SECRETS_FILE}"
fi

ENV_FILE="${WORKDIR}/staging.env"
cat > "${ENV_FILE}" <<EOF
CUSTOM_IMAGE=${IMAGE_NAME}
CUSTOM_TAG=${IMAGE_TAG}
PULL_POLICY=missing
DB_PASSWORD=${DB_PASSWORD}
FRAPPE_SITE_NAME_HEADER=${SITE_NAME}
HTTP_PUBLISH_PORT=${HTTP_PORT}
GUNICORN_THREADS=2
GUNICORN_WORKERS=2
EOF
chmod 600 "${ENV_FILE}"

COMPOSE_FILE="${WORKDIR}/compose.custom.yaml"
docker compose --env-file "${ENV_FILE}" \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.noproxy.yaml \
  config > "${COMPOSE_FILE}"
chmod 600 "${COMPOSE_FILE}"

dc() {
  docker compose -p "${PROJECT_NAME}" -f "${COMPOSE_FILE}" "$@"
}

echo "Starting MariaDB, Redis, Frappe workers, websocket and frontend..."
dc up -d

echo "Waiting for the backend container..."
for _ in $(seq 1 60); do
  if dc exec -T backend true >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

NEW_SITE=0
if ! dc exec -T backend test -d "/home/frappe/frappe-bench/sites/${SITE_NAME}" >/dev/null 2>&1; then
  NEW_SITE=1
  dc exec -T backend bench new-site "${SITE_NAME}" \
    --db-root-password "${DB_PASSWORD}" \
    --admin-password "${ADMIN_PASSWORD}" \
    --mariadb-user-host-login-scope='172.%.%.%'

  dc exec -T backend bench --site "${SITE_NAME}" install-app erpnext
  dc exec -T backend bench --site "${SITE_NAME}" install-app hrms
  dc exec -T backend bench --site "${SITE_NAME}" install-app tradex_hr
fi

dc exec -T backend bench --site "${SITE_NAME}" migrate
dc exec -T backend bench --site "${SITE_NAME}" enable-scheduler
dc exec -T backend bench --site "${SITE_NAME}" clear-cache

echo "Waiting for HTTP..."
HTTP_OK=0
for _ in $(seq 1 90); do
  if curl -fsS "http://127.0.0.1:${HTTP_PORT}/" >/dev/null 2>&1; then
    HTTP_OK=1
    break
  fi
  sleep 2
done

echo
dc ps
echo
echo "Installed apps:"
dc exec -T backend bench --site "${SITE_NAME}" list-apps || true

PUBLIC_IPV4=""
IMDS_TOKEN="$(curl -fsS -X PUT -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' \
  http://169.254.169.254/latest/api/token 2>/dev/null || true)"
if [ -n "${IMDS_TOKEN}" ]; then
  PUBLIC_IPV4="$(curl -fsS -H "X-aws-ec2-metadata-token: ${IMDS_TOKEN}" \
    http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)"
fi

echo
if [ "${HTTP_OK}" -eq 1 ]; then
  echo "Frappe staging HTTP check: PASS"
else
  echo "Frappe staging HTTP check: NOT READY - inspect with: cd ${FRAPPE_DOCKER_DIR} && docker compose -p ${PROJECT_NAME} -f ${COMPOSE_FILE} logs"
fi

if [ -n "${PUBLIC_IPV4}" ]; then
  echo "Open: http://${PUBLIC_IPV4}:${HTTP_PORT}"
else
  echo "Open port ${HTTP_PORT} on the instance address shown in the AWS console."
fi

echo "Site: ${SITE_NAME}"
echo "Administrator password: ${ADMIN_PASSWORD}"
echo "Server-only secrets file: ${SECRETS_FILE}"
if [ "${NEW_SITE}" -eq 1 ]; then
  echo "A fresh neutral staging site was created. No production data was restored."
else
  echo "Existing site detected; migrations/cache refresh were applied."
fi
