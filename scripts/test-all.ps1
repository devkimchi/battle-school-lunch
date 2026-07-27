$ErrorActionPreference = "Stop"

function Invoke-Native {
    param(
        [Parameter(Mandatory)]
        [scriptblock] $Command
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE."
    }
}

$rootDirectory = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Write-Host "==> AppHost"
Push-Location $rootDirectory
try {
    Invoke-Native { npm ci }
    Invoke-Native { npm run build }
}
finally {
    Pop-Location
}

foreach ($service in @("api", "mcp", "agent")) {
    Write-Host "==> $service"
    Push-Location (Join-Path $rootDirectory "src\$service")
    try {
        Invoke-Native { uv sync --all-groups --frozen }
        Invoke-Native { uv run pytest }
    }
    finally {
        Pop-Location
    }
}

Write-Host "==> web"
Push-Location (Join-Path $rootDirectory "src\web")
try {
    Invoke-Native { npm ci }
    Invoke-Native { npm run lint }
    Invoke-Native { npm test }
    Invoke-Native { npm run build }
}
finally {
    Pop-Location
}

Write-Host "==> e2e"
Push-Location (Join-Path $rootDirectory "src\e2e")
try {
    Invoke-Native { npm ci }
    Invoke-Native { npx playwright install chromium }
    Invoke-Native { npm test }
}
finally {
    Pop-Location
}

Write-Host "All validations passed."
