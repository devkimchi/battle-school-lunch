#Requires -Version 7.0

[CmdletBinding()]
param(
    [string]$Repository = $env:GITHUB_REPOSITORY,
    [string]$SubscriptionId = $env:AZURE_SUBSCRIPTION_ID,
    [string]$ResourceGroup = $(
        if ($env:AZURE_RESOURCE_GROUP) { $env:AZURE_RESOURCE_GROUP }
        elseif ($env:Azure__ResourceGroup) { $env:Azure__ResourceGroup }
        else { "rg-school-lunch" }
    ),
    [string]$Location = $(
        if ($env:AZURE_LOCATION) { $env:AZURE_LOCATION }
        elseif ($env:Azure__Location) { $env:Azure__Location }
        else { "koreacentral" }
    ),
    [string]$AppName,
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

$groupExists = Invoke-NativeText az @("group", "exists", "--name", $ResourceGroup)
if ($groupExists -ne "true") {
    throw "Resource group '$ResourceGroup' does not exist. Deploy the Aspire app first."
}

if ([string]::IsNullOrWhiteSpace($AppName)) {
    $resourceSuffix = $null
    $resourceTypes = @(
        "Microsoft.App/managedEnvironments",
        "Microsoft.OperationalInsights/workspaces",
        "Microsoft.ContainerRegistry/registries"
    )

    foreach ($resourceType in $resourceTypes) {
        $resourceNames = Invoke-NativeText az @(
            "resource", "list",
            "--resource-group", $ResourceGroup,
            "--resource-type", $resourceType,
            "--query", "[].name",
            "--output", "tsv"
        )

        foreach ($resourceName in ($resourceNames -split "\r?\n")) {
            if ($resourceName -match "([a-z0-9]{13})$") {
                $resourceSuffix = $Matches[1]
                break
            }
        }

        if (-not [string]::IsNullOrWhiteSpace($resourceSuffix)) {
            break
        }
    }

    if ([string]::IsNullOrWhiteSpace($resourceSuffix)) {
        throw "Could not find an Aspire resource suffix in '$ResourceGroup'."
    }

    $resourceName = $ResourceGroup -replace "^rg-", ""
    $AppName = "spn-$resourceName-$resourceSuffix"
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

$federatedSubjects = [ordered]@{
    "github-main" = "repo:$($Repository):ref:refs/heads/main"
    "github-pr"   = "repo:$($Repository):pull_request"
}

foreach ($credName in $federatedSubjects.Keys) {
    $credSubject = $federatedSubjects[$credName]
    $existingSubject = Invoke-NativeText az @(
        "ad", "app", "federated-credential", "list",
        "--id", $AppId,
        "--query", "[?name=='$credName'].subject | [0]",
        "--output", "tsv"
    )

    if (
        -not [string]::IsNullOrWhiteSpace($existingSubject) -and
        $existingSubject -ne $credSubject
    ) {
        throw "Federated credential '$credName' already uses '$existingSubject'."
    }

    if ([string]::IsNullOrWhiteSpace($existingSubject)) {
        $credential = @{
            name        = $credName
            issuer      = "https://token.actions.githubusercontent.com"
            subject     = $credSubject
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
}

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
Write-Host "Federated subjects:"
foreach ($credName in $federatedSubjects.Keys) {
    Write-Host "  ${credName}: $($federatedSubjects[$credName])"
}

if ($EnableDeployment.IsPresent) {
    Write-Host "You can now push your commit to the remote repository to trigger deployment."
} else {
    Write-Host "Deployment remains disabled. Re-run with -EnableDeployment before pushing to deploy."
}
