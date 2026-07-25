#!/usr/bin/env bash

set -euo pipefail

AZURE_LOCATION="${AZURE_LOCATION:-koreacentral}"
AZURE_RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-rg-school-lunch-production}"
AZURE_DEPLOYMENT="${AZURE_DEPLOYMENT:-true}"
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-production}"
FEDERATED_CREDENTIAL_NAME="${FEDERATED_CREDENTIAL_NAME:-github-production}"
REPOSITORY="${GITHUB_REPOSITORY:-}"
SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-}"
APP_NAME=""

usage() {
  cat <<'EOF'
Usage: scripts/setup-azure-deployment.sh [options]

Options:
  --repository OWNER/REPO       GitHub repository (default: current gh repository)
  --subscription-id ID          Azure subscription (default: current az subscription)
  --resource-group NAME         Azure resource group
  --location LOCATION           Azure location
  --app-name NAME               Microsoft Entra application display name
  --environment NAME            GitHub environment used by the workflow
  --help                        Show this help

Set NEIS_API_KEY in the environment or enter it at the secure prompt.
EOF
}

while (($# > 0)); do
  case "$1" in
    --repository)
      REPOSITORY="$2"
      shift 2
      ;;
    --subscription-id)
      SUBSCRIPTION_ID="$2"
      shift 2
      ;;
    --resource-group)
      AZURE_RESOURCE_GROUP="$2"
      shift 2
      ;;
    --location)
      AZURE_LOCATION="$2"
      shift 2
      ;;
    --app-name)
      APP_NAME="$2"
      shift 2
      ;;
    --environment)
      ENVIRONMENT_NAME="$2"
      shift 2
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

for command in az gh jq; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Required command not found: $command" >&2
    exit 1
  fi
done

if [[ -z "$REPOSITORY" ]]; then
  REPOSITORY="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
fi

if [[ "$REPOSITORY" != */* ]]; then
  echo "Repository must use the OWNER/REPO format." >&2
  exit 1
fi

if [[ -z "$SUBSCRIPTION_ID" ]]; then
  SUBSCRIPTION_ID="$(az account show --query id --output tsv)"
fi

az account set --subscription "$SUBSCRIPTION_ID"
TENANT_ID="$(az account show --query tenantId --output tsv)"

if [[ -z "$APP_NAME" ]]; then
  APP_NAME="${REPOSITORY//\//-}-github-actions"
fi

if [[ -z "${NEIS_API_KEY:-}" ]]; then
  read -r -s -p "NEIS API key: " NEIS_API_KEY
  echo
fi

if [[ -z "$NEIS_API_KEY" ]]; then
  echo "NEIS_API_KEY must not be empty." >&2
  exit 1
fi

app_count="$(az ad app list --display-name "$APP_NAME" --query 'length(@)' --output tsv)"
if ((app_count > 1)); then
  echo "Multiple Entra applications are named '$APP_NAME'; use --app-name with a unique name." >&2
  exit 1
fi

if ((app_count == 0)); then
  APP_ID="$(az ad app create --display-name "$APP_NAME" --query appId --output tsv)"
else
  APP_ID="$(az ad app list --display-name "$APP_NAME" --query '[0].appId' --output tsv)"
fi

SP_OBJECT_ID="$(az ad sp list --filter "appId eq '$APP_ID'" --query '[0].id' --output tsv)"
if [[ -z "$SP_OBJECT_ID" ]]; then
  SP_OBJECT_ID="$(az ad sp create --id "$APP_ID" --query id --output tsv)"
fi

az group create \
  --name "$AZURE_RESOURCE_GROUP" \
  --location "$AZURE_LOCATION" \
  --subscription "$SUBSCRIPTION_ID" \
  --output none

SCOPE="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$AZURE_RESOURCE_GROUP"
for role in Contributor "Role Based Access Control Administrator"; do
  role_count="$(az role assignment list \
    --assignee-object-id "$SP_OBJECT_ID" \
    --scope "$SCOPE" \
    --role "$role" \
    --query 'length(@)' \
    --output tsv)"

  if ((role_count == 0)); then
    az role assignment create \
      --assignee-object-id "$SP_OBJECT_ID" \
      --assignee-principal-type ServicePrincipal \
      --role "$role" \
      --scope "$SCOPE" \
      --output none
  fi
done

SUBJECT="repo:$REPOSITORY:environment:$ENVIRONMENT_NAME"
existing_subject="$(az ad app federated-credential list \
  --id "$APP_ID" \
  --query "[?name=='$FEDERATED_CREDENTIAL_NAME'].subject | [0]" \
  --output tsv)"

if [[ -n "$existing_subject" && "$existing_subject" != "$SUBJECT" ]]; then
  echo "Federated credential '$FEDERATED_CREDENTIAL_NAME' already uses '$existing_subject'." >&2
  exit 1
fi

if [[ -z "$existing_subject" ]]; then
  credential_json="$(jq -nc \
    --arg name "$FEDERATED_CREDENTIAL_NAME" \
    --arg subject "$SUBJECT" \
    '{
      name: $name,
      issuer: "https://token.actions.githubusercontent.com",
      subject: $subject,
      description: "GitHub Actions deployment",
      audiences: ["api://AzureADTokenExchange"]
    }')"

  az ad app federated-credential create \
    --id "$APP_ID" \
    --parameters "$credential_json" \
    --output none
fi

gh api \
  --method PUT \
  "repos/$REPOSITORY/environments/$ENVIRONMENT_NAME" \
  --silent

set_secret() {
  local name="$1"
  local value="$2"
  printf '%s' "$value" | gh secret set "$name" --repo "$REPOSITORY"
}

set_secret AZURE_CLIENT_ID "$APP_ID"
set_secret AZURE_TENANT_ID "$TENANT_ID"
set_secret AZURE_SUBSCRIPTION_ID "$SUBSCRIPTION_ID"
set_secret NEIS_API_KEY "$NEIS_API_KEY"

gh variable set AZURE_DEPLOYMENT --body "$AZURE_DEPLOYMENT" --repo "$REPOSITORY"
gh variable set AZURE_LOCATION --body "$AZURE_LOCATION" --repo "$REPOSITORY"
gh variable set AZURE_RESOURCE_GROUP --body "$AZURE_RESOURCE_GROUP" --repo "$REPOSITORY"

unset NEIS_API_KEY

echo "Azure deployment identity and GitHub Actions settings configured for $REPOSITORY."
echo "Entra application client ID: $APP_ID"
echo "Federated subject: $SUBJECT"
