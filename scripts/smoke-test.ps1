#requires -Version 7.0
param(
    [string]$ProxyUrl,
    [string]$TokenEnv = 'CHERRYSTUDIO_API_GATEWAY_API_KEY',
    [ValidateRange(1, 300)][int]$TimeoutSeconds = 30,
    [string]$InventoryPath
)
$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path -Parent $PSScriptRoot
$RunArgs = @('--directory', $ProjectDir, 'run', '--no-sync', 'python', '-m', 'zhenzhen_image_mcp.smoke', '--timeout', "$TimeoutSeconds")
if ($ProxyUrl) { $RunArgs += @('--proxy-url', $ProxyUrl, '--token-env', $TokenEnv) }
if ($InventoryPath) { $RunArgs += @('--inventory', [IO.Path]::GetFullPath($InventoryPath)) }
& uv @RunArgs
if ($LASTEXITCODE -ne 0) { throw 'MCP availability test failed. See redacted diagnostics above.' }
