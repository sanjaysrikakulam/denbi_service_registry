#!/usr/bin/env bash
# =============================================================================
# ci-build-push.sh — Local CI: fetch → build → push to private registry
# =============================================================================
# Fetches the latest commits from a GitHub repository, builds the required
# Docker images, tags them with both the short git SHA and a semver/latest
# tag, and pushes them to your private container registry.
#
# Prerequisites:
#   - docker (with buildx)
#   - git
#   - jq  (optional, for prettier output)
#
# Environment variables (set in your shell or .env.ci):
#   REGISTRY_HOST       registry.example.org        (required)
#   REGISTRY_USERNAME   your-username               (required)
#   REGISTRY_PASSWORD   your-token-or-password      (required)
#   GITHUB_REPO         git@github.com:org/repo.git (required)
#   IMAGE_NAME          denbi-registry              (default: denbi-registry)
#   IMAGE_AUTHOR        Your Name                   (default: Your Name <your.email@example.com>)
#   GIT_BRANCH          main                        (default: main)
#   IMAGE_TAG           latest                      (default: latest; use semver for releases)
#   BUILD_PLATFORM      linux/amd64                 (default; use linux/amd64,linux/arm64 for multi)
#   SKIP_TESTS          0                           (set to 1 to skip the test stage)
#   LOCAL_CLONE_DIR     /tmp/denbi-registry-ci      (default; where to clone/pull the repo)
#
# Usage:
#   # Normal run — pulls latest main, builds, tests, pushes :latest + :<sha>
#   ./ci-build-push.sh
#
#   # Release — tag with a version
#   IMAGE_TAG=v1.4.2 ./ci-build-push.sh
#
#   # Skip tests (not recommended for production pushes)
#   SKIP_TESTS=1 ./ci-build-push.sh
#
#   # Multi-arch build
#   BUILD_PLATFORM=linux/amd64,linux/arm64 ./ci-build-push.sh
# =============================================================================

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[$(date +%H:%M:%S)]${RESET} $*"; }
ok()   { echo -e "${GREEN}✓${RESET} $*"; }
warn() { echo -e "${YELLOW}⚠${RESET} $*"; }
fail() { echo -e "${RED}✗ FATAL:${RESET} $*" >&2; exit 1; }
step() { echo -e "\n${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"; \
         echo -e "${BOLD}  $*${RESET}"; \
         echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"; }

# ── Configuration (from env or defaults) ─────────────────────────────────────
REGISTRY_HOST="${REGISTRY_HOST:?REGISTRY_HOST is required}"
REGISTRY_USERNAME="${REGISTRY_USERNAME:?REGISTRY_USERNAME is required}"
REGISTRY_PASSWORD="${REGISTRY_PASSWORD:?REGISTRY_PASSWORD is required}"
GITHUB_REPO="${GITHUB_REPO:?GITHUB_REPO is required (e.g. git@github.com:org/repo.git)}"
IMAGE_NAME="${IMAGE_NAME:-denbi-registry}"
GIT_BRANCH="${GIT_BRANCH:-main}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
BUILD_PLATFORM="${BUILD_PLATFORM:-linux/amd64}"
SKIP_TESTS="${SKIP_TESTS:-0}"
LOCAL_CLONE_DIR="${LOCAL_CLONE_DIR:-/tmp/denbi-registry-ci}"

FULL_IMAGE="${REGISTRY_HOST}/${IMAGE_NAME}"

# ── Pre-flight checks ─────────────────────────────────────────────────────────
step "Pre-flight checks"

command -v docker &>/dev/null || fail "docker not found in PATH"
command -v git    &>/dev/null || fail "git not found in PATH"

docker info &>/dev/null || fail "Docker daemon is not running"
ok "Docker daemon reachable"

# Ensure buildx builder exists
if ! docker buildx inspect ci-builder &>/dev/null; then
  log "Creating docker buildx builder 'ci-builder'..."
  docker buildx create --name ci-builder --driver docker-container --bootstrap
fi
docker buildx use ci-builder
ok "Buildx builder: ci-builder"

# ── Clone or update repository ────────────────────────────────────────────────
# step "Fetching repository"

# if [[ -d "${LOCAL_CLONE_DIR}/.git" ]]; then
#   log "Updating existing clone at ${LOCAL_CLONE_DIR}..."
#   git -C "${LOCAL_CLONE_DIR}" fetch --prune origin
#   git -C "${LOCAL_CLONE_DIR}" checkout "${GIT_BRANCH}"
#   git -C "${LOCAL_CLONE_DIR}" reset --hard "origin/${GIT_BRANCH}"
#   ok "Updated to latest ${GIT_BRANCH}"
# else
#   log "Cloning ${GITHUB_REPO} (branch: ${GIT_BRANCH}) into ${LOCAL_CLONE_DIR}..."
#   git clone --branch "${GIT_BRANCH}" --depth 50 "${GITHUB_REPO}" "${LOCAL_CLONE_DIR}"
#   ok "Cloned successfully"
# fi

# cd "${LOCAL_CLONE_DIR}"

# GIT_SHA=$(git rev-parse --short HEAD)
# GIT_SHA_FULL=$(git rev-parse HEAD)
# GIT_COMMIT_MSG=$(git log -1 --pretty=%s)
# GIT_AUTHOR=$(git log -1 --pretty=%an)
# BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# log "Branch : ${GIT_BRANCH}"
# log "Commit : ${GIT_SHA} — ${GIT_COMMIT_MSG} (${GIT_AUTHOR})"
# log "Date   : ${BUILD_DATE}"

# ── Run tests ─────────────────────────────────────────────────────────────────
if [[ "${SKIP_TESTS}" == "1" ]]; then
  warn "SKIP_TESTS=1 — skipping test stage (not recommended for production)"
else
  step "Running test suite"
  log "Building test image..."
  docker buildx build \
    --platform linux/amd64 \
    --target runtime \
    --load \
    --tag "${IMAGE_NAME}:ci-test-${GIT_SHA}" \
    .

  log "Running pytest inside container..."
  docker run --rm \
    --name "ci-test-${GIT_SHA}" \
    -e SECRET_KEY="ci-only-secret-key-not-for-production" \
    -e DB_PASSWORD="ci" \
    -e REDIS_PASSWORD="ci" \
    -e DEBUG="true" \
    -e CAPTCHA_ENABLED="false" \
    -e CELERY_TASK_ALWAYS_EAGER="True" \
    "${IMAGE_NAME}:ci-test-${GIT_SHA}" \
    sh -c "python manage.py migrate --run-syncdb 2>&1 && pytest tests/ -v --tb=short"

  docker rmi "${IMAGE_NAME}:ci-test-${GIT_SHA}" 2>/dev/null || true
  ok "All tests passed"
fi

# ── Log in to registry ────────────────────────────────────────────────────────
step "Authenticating to registry"
echo "${REGISTRY_PASSWORD}" | docker login "${REGISTRY_HOST}" \
  --username "${REGISTRY_USERNAME}" \
  --password-stdin
ok "Logged in to ${REGISTRY_HOST}"

# ── Build and push ────────────────────────────────────────────────────────────
step "Building and pushing image"

# Tags to apply:
#   :latest (or $IMAGE_TAG for releases)  — human-friendly, mutable
#   :<sha>                                — immutable, references exact commit
# SHA_TAG="${FULL_IMAGE}:${GIT_SHA}"
NAMED_TAG="${FULL_IMAGE}:${IMAGE_TAG}"

log "Building for platform(s): ${BUILD_PLATFORM}"
log "Tags:"
# log "  ${SHA_TAG}"
log "  ${NAMED_TAG}"

docker buildx build \
  --platform "${BUILD_PLATFORM}" \
  --target runtime \
  --push \
  --tag "${NAMED_TAG}" \
  --label "org.opencontainers.image.created=${BUILD_DATE}" \
  --label "org.opencontainers.image.version=${IMAGE_TAG}" \
  --label "org.opencontainers.image.title=${IMAGE_NAME}" \
  --label "org.opencontainers.image.authors=${IMAGE_AUTHOR}" \
  --cache-from "type=registry,ref=${FULL_IMAGE}:buildcache" \
  --cache-to   "type=registry,ref=${FULL_IMAGE}:buildcache,mode=max" \
  .

ok "Image pushed:"
# ok "  ${SHA_TAG}"
ok "  ${NAMED_TAG}"

# ── Log out ───────────────────────────────────────────────────────────────────
docker logout "${REGISTRY_HOST}" &>/dev/null || true

# ── Summary ───────────────────────────────────────────────────────────────────
step "CI complete"
echo -e "${GREEN}${BOLD}"
# echo "  Repository : ${GITHUB_REPO}"
# echo "  Branch     : ${GIT_BRANCH}"
# echo "  Commit     : ${GIT_SHA} — ${GIT_COMMIT_MSG}"
# echo "  Image SHA  : ${SHA_TAG}"
echo "  Image tag  : ${NAMED_TAG}"
echo "  Platform   : ${BUILD_PLATFORM}"
echo -e "${RESET}"
# echo "To deploy this exact image:"
# echo "  IMAGE_TAG=${GIT_SHA} ansible-playbook -i inventory/hosts.ini playbooks/site.yml --ask-vault-pass --tags deploy"
