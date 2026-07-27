#!/usr/bin/env bash
# Transactional-ish in-place deploy with pre-migration, readiness and rollback.
set -Eeuo pipefail

APP_ROOT=/opt/CreatorAppDuLich
PIPELINE_ROOT="$APP_ROOT/dulich-pipeline"
BRANCH=thanhthuduc99
SYSTEMD_ROOT=/etc/systemd/system
previous_commit=""
target_commit=""
services_stopped=0
rollback_dir=""
preflight_dir=""

cleanup() {
  if [[ -n "$preflight_dir" && -d "$preflight_dir" ]]; then
    rm -rf -- "$preflight_dir"
  fi
  if [[ -n "$rollback_dir" && -d "$rollback_dir" ]]; then
    rm -rf -- "$rollback_dir"
  fi
}

restore_unit() {
  local name="$1"
  if [[ -f "$rollback_dir/$name" ]]; then
    sudo cp "$rollback_dir/$name" "$SYSTEMD_ROOT/$name"
  else
    sudo rm -f -- "$SYSTEMD_ROOT/$name"
  fi
}

rollback() {
  local exit_code=$?
  trap - ERR
  if [[ "$services_stopped" -eq 1 && -n "$previous_commit" ]]; then
    echo "Deploy failed; rolling back to $previous_commit" >&2
    cd "$APP_ROOT"
    git reset --hard "$previous_commit"
    restore_unit dulich.service
    restore_unit dulich-worker.service
    restore_unit dulich-backup.service
    restore_unit dulich-backup.timer
    sudo systemctl daemon-reload
    sudo systemctl restart dulich
    if [[ -f "$SYSTEMD_ROOT/dulich-worker.service" ]]; then
      sudo systemctl restart dulich-worker
    fi
  fi
  cleanup
  exit "$exit_code"
}
trap rollback ERR
trap cleanup EXIT

cd "$APP_ROOT"
previous_commit="$(git rev-parse HEAD)"
git fetch origin "$BRANCH"
target_commit="$(git rev-parse FETCH_HEAD)"
git merge-base --is-ancestor "$previous_commit" "$target_commit"

dirty_tracked="$(
  git status --porcelain --untracked-files=no |
    grep -vE '^.. dulich-pipeline/(data/users\.json|output/)' || true
)"
if [[ -n "$dirty_tracked" ]]; then
  echo "Refusing deploy: production has unexpected tracked changes:" >&2
  echo "$dirty_tracked" >&2
  exit 1
fi

# Extract the target auth tools before checkout. This migrates legacy plaintext
# accounts while the old data/users.json is still available.
preflight_dir="$(mktemp -d /tmp/dulich-preflight.XXXXXX)"
git show "$target_commit:dulich-pipeline/tools/auth_store.py" \
  > "$preflight_dir/auth_store.py"
git show "$target_commit:dulich-pipeline/tools/migrate_auth.py" \
  > "$preflight_dir/migrate_auth.py"
sudo -u dulich env \
  AUTH_USERS_FILE="$PIPELINE_ROOT/data/users.json" \
  AUTH_DB_PATH="$PIPELINE_ROOT/data/auth.sqlite3" \
  PYTHONPATH="$preflight_dir" \
  "$PIPELINE_ROOT/.venv/bin/python" -X utf8 \
  "$preflight_dir/migrate_auth.py" --source json

rollback_dir="$(mktemp -d /tmp/dulich-rollback.XXXXXX)"
for unit in \
  dulich.service \
  dulich-worker.service \
  dulich-backup.service \
  dulich-backup.timer
do
  if [[ -f "$SYSTEMD_ROOT/$unit" ]]; then
    sudo cp "$SYSTEMD_ROOT/$unit" "$rollback_dir/$unit"
  fi
done

sudo systemctl stop dulich-worker 2>/dev/null || true
sudo systemctl stop dulich
services_stopped=1

git checkout "$BRANCH"
git merge --ff-only "$target_commit"
cd "$PIPELINE_ROOT"
.venv/bin/pip install -r requirements.txt --quiet
sudo -u dulich .venv/bin/python -X utf8 tools/migrate_auth.py --source auto
sudo -u dulich .venv/bin/python -X utf8 tools/migrate_pipeline.py
sudo -u dulich .venv/bin/python -X utf8 tools/backup_sqlite.py

sudo cp \
  deploy/dulich.service \
  deploy/dulich-worker.service \
  deploy/dulich-backup.service \
  deploy/dulich-backup.timer \
  "$SYSTEMD_ROOT/"
sudo systemctl daemon-reload
sudo systemctl enable --now dulich-backup.timer
sudo systemctl restart dulich dulich-worker

for _ in $(seq 1 20); do
  if sudo systemctl is-active --quiet dulich \
    && sudo systemctl is-active --quiet dulich-worker \
    && curl --fail --silent --show-error http://localhost:7788/health
  then
    echo " ✓ deploy OK: $target_commit"
    services_stopped=0
    exit 0
  fi
  sleep 2
done

echo "Readiness failed after 40 seconds." >&2
exit 1
