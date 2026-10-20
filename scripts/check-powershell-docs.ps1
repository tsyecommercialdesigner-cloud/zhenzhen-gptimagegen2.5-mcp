#requires -Version 7.0
$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path -Parent $PSScriptRoot
$Count = 0
foreach ($Name in @('README.md', 'MANUAL.md')) {
  $Text = Get-Content -LiteralPath (Join-Path $ProjectDir $Name) -Raw
  $Blocks = [regex]::Matches($Text, '(?ms)^```powershell\r?\n(.*?)\r?\n```')
  foreach ($Block in $Blocks) {
    $Tokens = $null
    $Errors = $null
    $null = [Management.Automation.Language.Parser]::ParseInput($Block.Groups[1].Value, [ref]$Tokens, [ref]$Errors)
    if ($Errors.Count) { throw "$Name PowerShell block $Count : $($Errors.Message -join ' | ')" }
    $Count++
  }
}
Write-Output "PASS: $Count PowerShell documentation blocks parsed without execution."
