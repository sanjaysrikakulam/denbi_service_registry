#!/usr/bin/env bash
# =============================================================================
# run-tests.sh — Full test suite runner
# =============================================================================
# Runs pytest, linting, type checking, and security audit.
# Works identically locally and inside GitHub Actions.
#
# Usage:
#   ./run-tests.sh              # all checks
#   ./run-tests.sh --test-only  # pytest only
#   ./run-tests.sh --lint-only  # ruff only
#   ./run-tests.sh --no-docker  # run pytest directly (requires local Python env)
#
# Exit codes:
#   0  all checks passed
#   1  one or more checks failed
#
# Environment variables:
#   CI             set to "true" in GitHub Actions; changes output formatting
#   COVERAGE_XML   set to "true" to emit coverage.xml (for codecov etc.)
#   SKIP_AUDIT     set to "true" to skip pip-audit (e.g. in offline environments)
# =============================================================================

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
CI="${CI:-false}"
if [[ "${CI}" == "true" ]]; then
  RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; RESET=''
else
  RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
  CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
fi

log()     { echo -e "${CYAN}[$(date +%H:%M:%S)]${RESET} $*"; }
ok()      { echo -e "${GREEN}✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}⚠${RESET} $*"; }
fail_msg(){ echo -e "${RED}✗${RESET} $*"; }
step()    { echo -e "\n${BOLD}══ $* ══${RESET}"; }

# ── Parse flags ───────────────────────────────────────────────────────────────
TEST_ONLY=false
LINT_ONLY=false
NO_DOCKER=false
SKIP_AUDIT="${SKIP_AUDIT:-false}"
COVERAGE_XML="${COVERAGE_XML:-false}"

for arg in "$@"; do
  case "$arg" in
    --test-only) TEST_ONLY=true ;;
    --lint-only) LINT_ONLY=true ;;
    --no-docker) NO_DOCKER=true ;;
    --skip-audit) SKIP_AUDIT=true ;;
    --coverage) COVERAGE_XML=true ;;
    --help)
      grep '^#' "$0" | head -30 | sed 's/^# \{0,2\}//'
      exit 0
      ;;
  esac
done

# ── Locate project root ───────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script lives at deploy/ci/run-tests.sh; project root is two levels up
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [[ ! -f "${PROJECT_ROOT}/manage.py" ]]; then
  # Fallback: maybe script was copied next to manage.py
  PROJECT_ROOT="$(cd "${SCRIPT_DIR}" && pwd)"
fi
if [[ ! -f "${PROJECT_ROOT}/manage.py" ]]; then
  echo "ERROR: Could not locate manage.py. Run from the project root or deploy/ci/." >&2
  exit 1
fi

cd "${PROJECT_ROOT}"
log "Project root: ${PROJECT_ROOT}"

# ── Tracking ─────────────────────────────────────────────────────────────────
FAILED_CHECKS=()
START_TIME=$(date +%s)

run_check() {
  local name="$1"; shift
  step "${name}"
  if "$@"; then
    ok "${name} passed"
    return 0
  else
    fail_msg "${name} FAILED"
    FAILED_CHECKS+=("${name}")
    return 1
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
# ── Docker-based checks ───────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

if [[ "${NO_DOCKER}" == "false" ]]; then
  command -v docker &>/dev/null || { warn "docker not found — falling back to --no-docker mode"; NO_DOCKER=true; }
fi

if [[ "${NO_DOCKER}" == "false" ]]; then

  # Build test image once and reuse it for all checks
  step "Building test image"
  docker build --target runtime --tag denbi-registry:ci-test . || {
    fail_msg "Docker build failed — cannot run any checks"
    exit 1
  }
  ok "Test image built"

  DOCKER_ENV=(
    -e SECRET_KEY="ci-only-secret-key-not-for-production"
    -e DB_PASSWORD="ci"
    -e REDIS_PASSWORD="ci"
    -e DEBUG="true"
    -e CAPTCHA_ENABLED="false"
    -e CELERY_TASK_ALWAYS_EAGER="True"
  )

  run_docker() {
    docker run --rm "${DOCKER_ENV[@]}" -v "${PROJECT_ROOT}:/app" denbi-registry:ci-test "$@"
  }

  if [[ "${LINT_ONLY}" == "false" ]]; then
    # ── pytest ──────────────────────────────────────────────────────────────
    PYTEST_ARGS=("tests/" "-v" "--tb=short")
    if [[ "${COVERAGE_XML}" == "true" ]]; then
      PYTEST_ARGS+=("--cov=apps" "--cov-report=term-missing" "--cov-report=xml:coverage.xml")
    fi

    run_check "pytest" run_docker sh -c \
      "python manage.py migrate --run-syncdb -v 0 2>&1 | tail -3 && pytest ${PYTEST_ARGS[*]}"
  fi

  if [[ "${TEST_ONLY}" == "false" ]]; then
    # ── ruff linter ─────────────────────────────────────────────────────────
    run_check "ruff lint" run_docker ruff check apps/ config/ tests/

    # ── ruff formatter check ─────────────────────────────────────────────────
    run_check "ruff format" run_docker ruff format --check apps/ config/ tests/

    # ── pip-audit ────────────────────────────────────────────────────────────
    if [[ "${SKIP_AUDIT}" == "false" ]]; then
      run_check "pip-audit" run_docker pip-audit -r requirements/production.txt
    else
      warn "Skipping pip-audit (SKIP_AUDIT=true)"
    fi
  fi

  # Cleanup
  docker rmi denbi-registry:ci-test 2>/dev/null || true

# ─────────────────────────────────────────────────────────────────────────────
# ── No-docker: run directly in current Python environment ─────────────────────
# ─────────────────────────────────────────────────────────────────────────────
else
  warn "Running without Docker — using system Python environment"

  export SECRET_KEY="ci-only-secret-key-not-for-production"
  export DB_PASSWORD="ci"
  export REDIS_PASSWORD="ci"
  export DEBUG="true"
  export CAPTCHA_ENABLED="false"
  export CELERY_TASK_ALWAYS_EAGER="True"
  export DJANGO_SETTINGS_MODULE="config.settings"

  if [[ "${LINT_ONLY}" == "false" ]]; then
    PYTEST_ARGS="tests/ -v --tb=short"
    if [[ "${COVERAGE_XML}" == "true" ]]; then
      PYTEST_ARGS="${PYTEST_ARGS} --cov=apps --cov-report=term-missing --cov-report=xml:coverage.xml"
    fi
    run_check "pytest" sh -c "python manage.py migrate --run-syncdb -v 0 2>&1 | tail -3 && pytest ${PYTEST_ARGS}"
  fi

  if [[ "${TEST_ONLY}" == "false" ]]; then
    command -v ruff &>/dev/null && \
      run_check "ruff lint"   ruff check   apps/ config/ tests/ && \
      run_check "ruff format" ruff format  --check apps/ config/ tests/

    if [[ "${SKIP_AUDIT}" == "false" ]]; then
      command -v pip-audit &>/dev/null && \
        run_check "pip-audit" pip-audit -r requirements/production.txt
    fi
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo -e "${BOLD}══ Results ══${RESET}"
echo "Duration: ${ELAPSED}s"

if [[ ${#FAILED_CHECKS[@]} -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}All checks passed.${RESET}"
  exit 0
else
  echo -e "${RED}${BOLD}${#FAILED_CHECKS[@]} check(s) failed:${RESET}"
  for check in "${FAILED_CHECKS[@]}"; do
    echo -e "  ${RED}✗${RESET} ${check}"
  done
  exit 1
fi
