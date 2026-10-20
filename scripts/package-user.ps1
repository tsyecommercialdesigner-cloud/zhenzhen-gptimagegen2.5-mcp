#requires -Version 7.0
param([switch]$VerifyOnly)
$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path -Parent $PSScriptRoot
$RunArgs = @('--directory', $ProjectDir, 'run', '--no-sync', 'python', (Join-Path $PSScriptRoot 'package_user.py'))
if ($VerifyOnly) { $RunArgs += '--verify-only' }
& uv @RunArgs
if ($LASTEXITCODE -ne 0) { throw 'Packaging or clean online validation failed; no verified release published.' }
