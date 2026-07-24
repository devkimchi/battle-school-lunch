$ErrorActionPreference = "Stop"

if (-not [string]::IsNullOrWhiteSpace($env:NEIS_API_KEY)) {
    exit 0
}

$storedKey = azd env get-value NEIS_API_KEY 2>$null
if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($storedKey)) {
    exit 0
}

$secureKey = Read-Host "NEIS API key" -AsSecureString
$key = [System.Net.NetworkCredential]::new("", $secureKey).Password

if ([string]::IsNullOrWhiteSpace($key)) {
    [Console]::Error.WriteLine("ERROR: NEIS API key cannot be empty.")
    exit 1
}

azd env set NEIS_API_KEY $key
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine("ERROR: Failed to save NEIS_API_KEY in the azd environment.")
    exit $LASTEXITCODE
}

$key = $null
