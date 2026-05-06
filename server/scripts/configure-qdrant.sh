#!/bin/bash
set -e

: "${API_HOST:?API_HOST is required}"
: "${QDRANT_HOST:?QDRANT_HOST is required}"
: "${QDRANT_PORT:?QDRANT_PORT is required}"
: "${QDRANT_COLLECTION_NAME:?QDRANT_COLLECTION_NAME is required}"
: "${ADMIN_API_KEY:?ADMIN_API_KEY is required}"

echo "Waiting for mem0 API to be ready..."
until curl -sf "http://${API_HOST}:8000/" > /dev/null 2>&1; do
  echo "API not ready, retrying in 5s..."
  sleep 5
done
echo "API is ready."

curl -sf -X POST "http://${API_HOST}:8000/configure" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${ADMIN_API_KEY}" \
  -d "{
    \"vector_store\": {
      \"provider\": \"qdrant\",
      \"config\": {
        \"host\": \"${QDRANT_HOST}\",
        \"port\": ${QDRANT_PORT},
        \"collection_name\": \"${QDRANT_COLLECTION_NAME}\"
      }
    }
  }"

echo "Qdrant configuration applied successfully."
