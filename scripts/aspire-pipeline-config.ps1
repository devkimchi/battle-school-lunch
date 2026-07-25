#Requires -Version 7.0

[CmdletBinding()]
param(
    [string]$Repository = $env:GITHUB_REPOSITORY,
    [string]$SubscriptionId = $env:AZURE_SUBSCRIPTION_ID,
    [string]$ResourceGroup = $(if ($env:AZURE_RESOURCE_GROUP) { $env:AZURE_RESOURCE_GROUP } else { "rg-school-lunch-production" }),
    [string]$Location = $(if ($env:AZURE_LOCATION) { $env:AZURE_LOCATION } else { "koreacentral" }),
    [string]$AppName,
    [string]$EnvironmentName = "production",
    [string]$FederatedCredentialName = "github-production",
    [switch]$EnableDeployment
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-NativeText {
    param(
        [Parameter(Mandatory)]
        [string]$FilePath,

        [Parameter(Mandatory)]
        [string[]]$Arguments
    )

    $output = & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$FilePath failed with exit code $LASTEXITCODE."
    }

    return (($output | Out-String).Trim())
}

function Set-GitHubSecret {
    param(
        [Parameter(Mandatory)]
        [string]$Name,

        [Parameter(Mandatory)]
        [string]$Value,

        [Parameter(Mandatory)]
        [string]$TargetRepository
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = "gh"
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.UseShellExecute = $false
    $startInfo.ArgumentList.Add("secret")
    $startInfo.ArgumentList.Add("set")
    $startInfo.ArgumentList.Add($Name)
    $startInfo.ArgumentList.Add("--repo")
    $startInfo.ArgumentList.Add($TargetRepository)

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $null = $process.Start()
    $process.StandardInput.Write($Value)
    $process.StandardInput.Close()
    $process.WaitForExit()

    if ($process.ExitCode -ne 0) {
        $errorOutput = $process.StandardError.ReadToEnd()
        throw "Unable to set GitHub secret '$Name': $errorOutput"
    }
}

foreach ($command in @("az", "gh")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $command"
    }
}

if ([string]::IsNullOrWhiteSpace($Repository)) {
    $Repository = Invoke-NativeText gh @("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
}

if ($Repository -notmatch "^[^/]+/[^/]+$") {
    throw "Repository must use the OWNER/REPO format."
}

if ([string]::IsNullOrWhiteSpace($SubscriptionId)) {
    $SubscriptionId = Invoke-NativeText az @("account", "show", "--query", "id", "--output", "tsv")
}

$null = Invoke-NativeText az @("account", "set", "--subscription", $SubscriptionId)
$TenantId = Invoke-NativeText az @("account", "show", "--query", "tenantId", "--output", "tsv")

if ([string]::IsNullOrWhiteSpace($AppName)) {
    $AppName = "$($Repository.Replace('/', '-'))-github-actions"
}

if ([string]::IsNullOrWhiteSpace($env:NEIS_API_KEY)) {
    $secureApiKey = Read-Host "NEIS API key" -AsSecureString
    $NeisApiKey = [System.Net.NetworkCredential]::new("", $secureApiKey).Password
} else {
    $NeisApiKey = $env:NEIS_API_KEY
}

if ([string]::IsNullOrWhiteSpace($NeisApiKey)) {
    throw "NEIS_API_KEY must not be empty."
}

$appCount = [int](Invoke-NativeText az @(
    "ad", "app", "list",
    "--display-name", $AppName,
    "--query", "length(@)",
    "--output", "tsv"
))

if ($appCount -gt 1) {
    throw "Multiple Entra applications are named '$AppName'; use -AppName with a unique name."
}

if ($appCount -eq 0) {
    $AppId = Invoke-NativeText az @(
        "ad", "app", "create",
        "--display-name", $AppName,
        "--query", "appId",
        "--output", "tsv"
    )
} else {
    $AppId = Invoke-NativeText az @(
        "ad", "app", "list",
        "--display-name", $AppName,
        "--query", "[0].appId",
        "--output", "tsv"
    )
}

$SpObjectId = Invoke-NativeText az @(
    "ad", "sp", "list",
    "--filter", "appId eq '$AppId'",
    "--query", "[0].id",
    "--output", "tsv"
)

if ([string]::IsNullOrWhiteSpace($SpObjectId)) {
    $SpObjectId = Invoke-NativeText az @(
        "ad", "sp", "create",
        "--id", $AppId,
        "--query", "id",
        "--output", "tsv"
    )
}

$null = Invoke-NativeText az @(
    "group", "create",
    "--name", $ResourceGroup,
    "--location", $Location,
    "--subscription", $SubscriptionId,
    "--output", "none"
)

$scope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup"
foreach ($role in @("Contributor", "Role Based Access Control Administrator")) {
    $roleCount = [int](Invoke-NativeText az @(
        "role", "assignment", "list",
        "--assignee-object-id", $SpObjectId,
        "--scope", $scope,
        "--role", $role,
        "--query", "length(@)",
        "--output", "tsv"
    ))

    if ($roleCount -eq 0) {
        $null = Invoke-NativeText az @(
            "role", "assignment", "create",
            "--assignee-object-id", $SpObjectId,
            "--assignee-principal-type", "ServicePrincipal",
            "--role", $role,
            "--scope", $scope,
            "--output", "none"
        )
    }
}

$subject = "repo:$($Repository):environment:$EnvironmentName"
$existingSubject = Invoke-NativeText az @(
    "ad", "app", "federated-credential", "list",
    "--id", $AppId,
    "--query", "[?name=='$FederatedCredentialName'].subject | [0]",
    "--output", "tsv"
)

if (
    -not [string]::IsNullOrWhiteSpace($existingSubject) -and
    $existingSubject -ne $subject
) {
    throw "Federated credential '$FederatedCredentialName' already uses '$existingSubject'."
}

if ([string]::IsNullOrWhiteSpace($existingSubject)) {
    $credential = @{
        name        = $FederatedCredentialName
        issuer      = "https://token.actions.githubusercontent.com"
        subject     = $subject
        description = "GitHub Actions deployment"
        audiences   = @("api://AzureADTokenExchange")
    } | ConvertTo-Json -Compress

    $null = Invoke-NativeText az @(
        "ad", "app", "federated-credential", "create",
        "--id", $AppId,
        "--parameters", $credential,
        "--output", "none"
    )
}

$null = Invoke-NativeText gh @(
    "api",
    "--method", "PUT",
    "repos/$Repository/environments/$EnvironmentName",
    "--silent"
)

Set-GitHubSecret -Name "NEIS_API_KEY" -Value $NeisApiKey -TargetRepository $Repository

$null = Invoke-NativeText gh @("variable", "set", "AZURE_CLIENT_ID", "--body", $AppId, "--repo", $Repository)
$null = Invoke-NativeText gh @("variable", "set", "AZURE_TENANT_ID", "--body", $TenantId, "--repo", $Repository)
$null = Invoke-NativeText gh @("variable", "set", "AZURE_SUBSCRIPTION_ID", "--body", $SubscriptionId, "--repo", $Repository)
$deploymentEnabled = $EnableDeployment.IsPresent.ToString().ToLowerInvariant()
$null = Invoke-NativeText gh @("variable", "set", "AZURE_DEPLOYMENT", "--body", $deploymentEnabled, "--repo", $Repository)
$null = Invoke-NativeText gh @("variable", "set", "AZURE_LOCATION", "--body", $Location, "--repo", $Repository)
$null = Invoke-NativeText gh @("variable", "set", "AZURE_RESOURCE_GROUP", "--body", $ResourceGroup, "--repo", $Repository)

$NeisApiKey = $null
$secureApiKey = $null

Write-Host "Azure deployment identity and GitHub Actions settings configured for $Repository."
Write-Host "Entra application client ID: $AppId"
Write-Host "Federated subject: $subject"
