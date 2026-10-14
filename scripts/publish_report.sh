#!/usr/bin/env bash
# Publish the CI report where it can be read without access to the Actions
# logs or artifacts:
#   1. as a comment on the pull request (one comment, updated at each run);
#   2. as files committed on the `rapports` branch:
#        reports/<date>_<event>_<run id>.md and .json  (history)
#        latest.md / latest.json                       (last run, any branch)
#        by-branch/<branch>.md                         (last run of each branch)
#        latest-files/                                 (optional attachments of the last run)
#
# Usage: scripts/publish_report.sh <report.md> <report.json> [attachments_dir]
# Environment: GH_TOKEN, GITHUB_REPOSITORY, GITHUB_RUN_ID, GITHUB_EVENT_NAME,
#              REPORT_BRANCH_NAME, PR_NUMBER (only for pull requests).
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "usage: $0 <report.md> <report.json> [attachments_dir]" >&2
  exit 2
fi
report_md=$(realpath "$1")
report_json=$(realpath "$2")
attachments=${3:-}
: "${GH_TOKEN:?}" "${GITHUB_REPOSITORY:?}" "${GITHUB_RUN_ID:?}" "${GITHUB_EVENT_NAME:?}"
status=0

# 1. Pull request comment, updated in place (found by its hidden marker).
if [[ -n "${PR_NUMBER:-}" ]]; then
  marker='<!-- toulouse-demain:graph-report -->'
  comment_id=$(gh api --paginate "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments" \
    --jq ".[] | select(.user.login == \"github-actions[bot]\" and (.body | startswith(\"${marker}\"))) | .id" \
    | tail -n 1)
  if [[ -n "$comment_id" ]]; then
    gh api -X PATCH "repos/${GITHUB_REPOSITORY}/issues/comments/${comment_id}" -F "body=@${report_md}" >/dev/null || status=1
  else
    gh api -X POST "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments" -F "body=@${report_md}" >/dev/null || status=1
  fi
  echo "PR comment published (status ${status})"
fi

# 2. Commit on the `rapports` branch. The token is passed through git's
#    environment configuration, so it never appears on a command line.
export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0="http.https://github.com/.extraheader"
GIT_CONFIG_VALUE_0="AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GH_TOKEN" | base64 -w0)"
export GIT_CONFIG_VALUE_0
remote="https://github.com/${GITHUB_REPOSITORY}.git"
workdir=$(mktemp -d)
trap 'rm -rf "$workdir"' EXIT

if git ls-remote --exit-code --heads "$remote" rapports >/dev/null 2>&1; then
  git clone --quiet --depth 1 --branch rapports "$remote" "$workdir"
else
  git init --quiet -b rapports "$workdir"
  git -C "$workdir" remote add origin "$remote"
  printf '%s\n' "# Rapports de construction du graphe" "" \
    "Branche écrite uniquement par GitHub Actions (workflow build-graph.yml)." \
    "Dernier rapport : [latest.md](latest.md). Historique : dossier reports/." > "$workdir/README.md"
fi

stamp=$(date -u +%Y-%m-%dT%H%MZ)
name="${stamp}_${GITHUB_EVENT_NAME}_${GITHUB_RUN_ID}"
branch_file=$(printf '%s' "${REPORT_BRANCH_NAME:-unknown}" | tr -c 'A-Za-z0-9._-' '_')
mkdir -p "$workdir/reports" "$workdir/by-branch"
cp "$report_md" "$workdir/reports/${name}.md"
cp "$report_json" "$workdir/reports/${name}.json"
cp "$report_md" "$workdir/latest.md"
cp "$report_json" "$workdir/latest.json"
cp "$report_md" "$workdir/by-branch/${branch_file}.md"
# Attachments (for example the OSM extraction of the future stations).
rm -rf "$workdir/latest-files"
if [[ -n "$attachments" && -d "$attachments" ]]; then
  mkdir -p "$workdir/latest-files"
  cp -R "$attachments"/. "$workdir/latest-files/"
fi

git -C "$workdir" add -A
git -C "$workdir" -c user.name="github-actions[bot]" \
  -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
  commit --quiet -m "Rapport de construction du graphe ${name}"

pushed=false
for attempt in 1 2 3; do
  if git -C "$workdir" push --quiet origin rapports; then
    pushed=true
    break
  fi
  echo "push failed (attempt ${attempt}), rebasing on the remote branch"
  sleep $((attempt * 5))
  git -C "$workdir" pull --quiet --rebase origin rapports || true
done
if [[ "$pushed" != true ]]; then
  status=1
fi
echo "Report committed on branch rapports: reports/${name}.md (pushed=${pushed})"
exit "$status"
