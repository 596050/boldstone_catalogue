#!/bin/bash

# Usage:
#   export WORKER_URL="https://<your-worker>.workers.dev"
#   export RELAY_AUTH_TOKEN="<AUTH_TOKEN>"
#   bash utils/external_processing_services/gliner_ml_extraction.sh
#
# Or call GLiNER directly:
#   export GLINER_EXTRACT_URL="http://127.0.0.1:8000/extract"
#   bash utils/external_processing_services/gliner_ml_extraction.sh

set -euo pipefail

WORKER_URL="${WORKER_URL:-}"
GLINER_EXTRACT_URL="${GLINER_EXTRACT_URL:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NER_CONFIG_PATH="${REPO_ROOT}/experiments/rag/rag_TMP_GUARDIAN_knowledge_graph_pipeline/rag_solr_knowledge_graph/stages/stage_0_ingestion/ner_config.json"
OUTPUT_PATH="${REPO_ROOT}/experiments/rag/rag_TMP_GUARDIAN_knowledge_graph_pipeline/data/guardian/gliner_ml_extraction_output.txt"
INPUT_DIR="${GLINER_INPUT_DIR:-${REPO_ROOT}/experiments/rag/rag_TMP_GUARDIAN_knowledge_graph_pipeline/data/guardian/standardized}"
OUTPUT_DIR="${GLINER_OUTPUT_DIR:-${REPO_ROOT}/experiments/rag/rag_TMP_GUARDIAN_knowledge_graph_pipeline/data/guardian/ner_output}"
LIMIT="${GLINER_INPUT_LIMIT:-}"
MODE="${GLINER_MODE:-batch}"

if [[ -z "$GLINER_EXTRACT_URL" ]]; then
  if [[ -n "$WORKER_URL" ]]; then
    GLINER_EXTRACT_URL="${WORKER_URL%/}/gliner/extract"
  else
    GLINER_EXTRACT_URL="http://127.0.0.1:8000/extract"
  fi
fi
export GLINER_EXTRACT_URL

echo "Using GLiNER extract endpoint: ${GLINER_EXTRACT_URL}"

GLINER_LABELS_MODE="${GLINER_LABELS_MODE:-schema}"
GLINER_LABEL_CHUNK_SIZE="${GLINER_LABEL_CHUNK_SIZE:-1}"
GLINER_HTTP_TIMEOUT="${GLINER_HTTP_TIMEOUT:-60}"
GLINER_MAX_RETRIES="${GLINER_MAX_RETRIES:-5}"
GLINER_RETRY_BACKOFF="${GLINER_RETRY_BACKOFF:-2}"
GLINER_SENTENCE_SPLIT="${GLINER_SENTENCE_SPLIT:-1}"
GLINER_THRESHOLD="${GLINER_THRESHOLD:-}"

if [[ "$MODE" == "single" ]]; then
  # 1. Create a temporary file for the JSON payload
  cat > payload.json <<EOF
{
    "text": "[Our Income Protection provides the ultimate cover for illness and injury.] Whether a client is employed or self-employed, it has all the options you need to tailor cover to their situation and budget.\\n\\nAnd with our own job rather than own occupation definition, your clients benefit from a greater certainty of payout.\\n\\nRead on to find out more.",
    "threshold": 0.7
}
EOF

  python3 utils/external_processing_services/gliner_ml_extraction.py \
    --payload-file payload.json \
    --ner-config "$NER_CONFIG_PATH" \
    --labels-source config \
    --output-path "$OUTPUT_PATH"
else
  ARGS=(
    --ner-config "$NER_CONFIG_PATH"
    --labels-source config
    --input-dir "$INPUT_DIR"
    --output-dir "$OUTPUT_DIR"
  )
  if [[ -n "$LIMIT" && "$LIMIT" != "0" ]]; then
    ARGS+=(--limit "$LIMIT")
  fi

  python3 utils/external_processing_services/gliner_ml_extraction.py "${ARGS[@]}"
fi
