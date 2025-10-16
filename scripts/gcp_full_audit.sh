#!/usr/bin/env bash
set -euo pipefail

# Infinity X One — GCP Full System Check (single-project)
# Project: infinity-x-one-swarm-system
# Output: ~/gcp_audit/YYYYMMDD_HHMMSS/<project>/... + SUMMARY.md
# Optional: export API keys for auth'd /health checks:
#   export SATELLITE_API_KEY="..."
#   export ORCHESTRATOR_API_KEY="..."
#   export GPT_GATEWAY_API_KEY="..."
#   export MEMORY_API_KEY="..."

PROJECT="infinity-x-one-swarm-system"
REGIONS=("us-east1" "us-west1")

command -v gcloud >/dev/null || { echo "gcloud not found"; exit 1; }
command -v jq >/dev/null || { echo "jq not found"; exit 1; }
command -v curl >/dev/null || { echo "curl not found"; exit 1; }

TS="$(date +%Y%m%d_%H%M%S)"
ROOT="${HOME}/gcp_audit/${TS}"
PJ_DIR="${ROOT}/${PROJECT}"
mkdir -p "${PJ_DIR}"

note(){ echo "[$(date +%H:%M:%S)] $*" >&2; }
curl_health() {
  local url="$1" name="$2"
  local keyvar=""
  case "$name" in
    memory-gateway) keyvar="MEMORY_API_KEY" ;;
    satellite-01|wallet-balance-sync) keyvar="SATELLITE_API_KEY" ;;
    orchestrator) keyvar="ORCHESTRATOR_API_KEY" ;;
    gpt-gateway) keyvar="GPT_GATEWAY_API_KEY" ;;
  esac
  local auth=()
  if [ -n "$keyvar" ] && [ -n "${!keyvar:-}" ]; then
    auth=(-H "Authorization: Bearer ${!keyvar}")
  fi
  local code
  code=$(curl -sS -m 8 -o /dev/null -w "%{http_code}" "${auth[@]}" "${url}/health" || true)
  [[ "$code" == "000" || "$code" == "404" ]] && code=$(curl -sS -m 8 -o /dev/null -w "%{http_code}" "${auth[@]}" "${url}" || true)
  echo "$code"
}

# Clean ADC quota noise
gcloud auth application-default set-quota-project "${PROJECT}" >/dev/null 2>&1 || true
gcloud config set project "${PROJECT}" >/dev/null

SUMMARY_MD="${ROOT}/SUMMARY.md"
{
  echo "# Infinity X One — Google Cloud System Check"
  echo "_Run: ${TS}_"
  echo
} > "$SUMMARY_MD"

note "APIs (enabled)"
gcloud services list --enabled --format=json > "${PJ_DIR}/services_enabled.json" || echo "[]" > "${PJ_DIR}/services_enabled.json"

note "IAM + Service Accounts"
gcloud projects get-iam-policy "${PROJECT}" --format=json > "${PJ_DIR}/iam_policy.json" || echo "{}" > "${PJ_DIR}/iam_policy.json"
gcloud iam service-accounts list --format=json > "${PJ_DIR}/service_accounts.json" || echo "[]" > "${PJ_DIR}/service_accounts.json"

note "Cloud Run (per region)"
: > "${PJ_DIR}/run_services.json"
: > "${PJ_DIR}/run_health.tsv"   # SERVICE  REGION  URL  READY  HTTP
for R in "${REGIONS[@]}"; do
  RS_FILE="${PJ_DIR}/run_services_${R}.json"
  gcloud run services list --platform=managed --region="${R}" --format=json > "${RS_FILE}" || echo "[]" > "${RS_FILE}"

  if [ -s "${PJ_DIR}/run_services.json" ]; then
    jq -s '.[0] + .[1]' "${PJ_DIR}/run_services.json" "${RS_FILE}" > "${PJ_DIR}/.tmp_rs.json" || echo "[]" > "${PJ_DIR}/.tmp_rs.json"
    mv "${PJ_DIR}/.tmp_rs.json" "${PJ_DIR}/run_services.json"
  else
    cp "${RS_FILE}" "${PJ_DIR}/run_services.json"
  fi

  jq -r '.[].metadata.name' "${RS_FILE}" | while read -r SVC; do
    [ -z "$SVC" ] && continue
    note "Describe: ${SVC} (${R})"
    DESC="${PJ_DIR}/run_${SVC}_${R}.json"
    gcloud run services describe "$SVC" --platform=managed --region="${R}" --format=json > "${DESC}" || { echo "{}" > "${DESC}"; }
    URL=$(jq -r '..|.status?.url? // empty' "${DESC}" | head -n1)
    READY=$(jq -r '..|.status?.conditions? // [] | map(select(.type=="Ready"))[0].status // "Unknown"' "${DESC}")
    CODE="n/a"; [ -n "${URL}" ] && CODE=$(curl_health "${URL}" "${SVC}")
    printf "%s\t%s\t%s\t%s\t%s\n" "$SVC" "$R" "${URL:-n/a}" "${READY:-n/a}" "$CODE" >> "${PJ_DIR}/run_health.tsv"
  done
done

note "Artifact Registry repos"
gcloud artifacts repositories list --format=json > "${PJ_DIR}/artifact_repos.json" || echo "[]" > "${PJ_DIR}/artifact_repos.json"

note "Artifact Registry images (Docker repos)"
if [ -s "${PJ_DIR}/artifact_repos.json" ]; then
  jq -r '.[] | "\(.name) \(.format)"' "${PJ_DIR}/artifact_repos.json" | while read -r NAME FORMAT; do
    [ -z "${NAME}" ] && continue
    [[ "${FORMAT}" =~ ^(DOCKER|docker)$ ]] || continue
    LOC=$(echo "$NAME" | awk -F'/locations/' '{print $2}' | cut -d'/' -f1)
    REPO=$(echo "$NAME" | awk -F'/repositories/' '{print $2}')
    PROJ=$(echo "$NAME" | awk -F'/projects/' '{print $2}' | cut -d'/' -f1)
    HOST="${LOC}-docker.pkg.dev/${PROJ}/${REPO}"
    note "Images: ${HOST}"
    gcloud artifacts docker images list "${HOST}" --include-tags --format=json > "${PJ_DIR}/images_${LOC}_${REPO}.json" || echo "[]" > "${PJ_DIR}/images_${LOC}_${REPO}.json"
  done
fi

note "Pub/Sub"
gcloud pubsub topics list --format=json > "${PJ_DIR}/pubsub_topics.json" || echo "[]" > "${PJ_DIR}/pubsub_topics.json"
gcloud pubsub subscriptions list --format=json > "${PJ_DIR}/pubsub_subscriptions.json" || echo "[]" > "${PJ_DIR}/pubsub_subscriptions.json"

note "Cloud Scheduler"
for R in "${REGIONS[@]}"; do
  gcloud scheduler jobs list --location "${R}" --format=json > "${PJ_DIR}/scheduler_${R}.json" || echo "[]" > "${PJ_DIR}/scheduler_${R}.json"
done

note "Cloud Build (recent 50)"
gcloud builds list --format=json --limit=50 > "${PJ_DIR}/cloud_builds_recent.json" || echo "[]" > "${PJ_DIR}/cloud_builds_recent.json"

note "Firestore"
gcloud firestore databases describe --format=json > "${PJ_DIR}/firestore_database.json" || echo "{}" > "${PJ_DIR}/firestore_database.json"
gcloud firestore indexes composite list --format=json > "${PJ_DIR}/firestore_indexes.json" || echo "[]" > "${PJ_DIR}/firestore_indexes.json"

note "GCS buckets"
gsutil ls -p "${PROJECT}" > "${PJ_DIR}/buckets.txt" || true

note "Secret Manager"
gcloud secrets list --format=json > "${PJ_DIR}/secrets.json" || echo "[]" > "${PJ_DIR}/secrets.json"

note "VPC Access"
for R in "${REGIONS[@]}"; do
  gcloud compute networks vpc-access connectors list --region "${R}" --format=json > "${PJ_DIR}/vpc_connectors_${R}.json" || echo "[]" > "${PJ_DIR}/vpc_connectors_${R}.json"
done

note "Logs (24h ERROR+) per Cloud Run service"
LOG_DIR="${PJ_DIR}/logs_24h"; mkdir -p "${LOG_DIR}"
awk -F'\t' 'NR>1{print $1}' "${PJ_DIR}/run_health.tsv" 2>/dev/null | sort -u | while read -r SVC; do
  [ -z "$SVC" ] && continue
  gcloud logging read \
    "resource.type=cloud_run_revision AND resource.labels.service_name=\"${SVC}\" AND severity>=ERROR AND timestamp>=\"$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)\"" \
    --format=json --limit=200 > "${LOG_DIR}/${SVC}_errors.json" || echo "[]" > "${LOG_DIR}/${SVC}_errors.json"
done

TOTAL_SVCS=$(jq 'length' "${PJ_DIR}/run_services.json" 2>/dev/null || echo 0)
READY_OK=$(awk -F'\t' 'toupper($4)=="TRUE"{c++} END{print c+0}' "${PJ_DIR}/run_health.tsv" 2>/dev/null || echo 0)
HEALTH_2XX=$(awk -F'\t' '{print $5}' "${PJ_DIR}/run_health.tsv" 2>/dev/null | grep -E '^(200|201|204)$' | wc -l | tr -d ' ')

{
  echo "## Project: ${PROJECT}"
  echo
  echo "- Cloud Run services (total): **${TOTAL_SVCS}**"
  echo "- Ready TRUE: **${READY_OK}**"
  echo "- HTTP health 2xx: **${HEALTH_2XX}**"
  echo "- Buckets: $(wc -l < "${PJ_DIR}/buckets.txt" 2>/dev/null || echo 0)"
  echo "- Pub/Sub: topics $(jq 'length' "${PJ_DIR}/pubsub_topics.json"), subs $(jq 'length' "${PJ_DIR}/pubsub_subscriptions.json")"
  echo "- Scheduler (us-east1 / us-west1): $(jq 'length' "${PJ_DIR}/scheduler_us-east1.json" 2>/dev/null || echo 0) / $(jq 'length' "${PJ_DIR}/scheduler_us-west1.json" 2>/dev/null || echo 0)"
  echo "- Secrets: $(jq 'length' "${PJ_DIR}/secrets.json" 2>/dev/null || echo 0)"
  echo "- Artifact repos: $(jq 'length' "${PJ_DIR}/artifact_repos.json" 2>/dev/null || echo 0)"
  echo
} >> "${SUMMARY_MD}"

{
  echo
  echo "### Output directory"
  echo "\`${ROOT}\`"
  echo
  echo "**Key files:** run_services*.json, run_*_<region>._*_*_

