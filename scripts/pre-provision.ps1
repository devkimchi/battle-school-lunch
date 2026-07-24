$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($env:NEIS_API_KEY)) {
    [Console]::Error.WriteLine("ERROR: NEIS_API_KEY is not set in the azd environment.")
    [Console]::Error.WriteLine("Run: azd env set NEIS_API_KEY <your-key>")
    exit 1
}
