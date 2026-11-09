<#
.SYNOPSIS
    Run the reconciliation engine and return its exit code.

.DESCRIPTION
    The script calls Python with an argument array. It does not build a shell
    command string. Install universal-qa-utils in the selected Python first.

    Exit codes come from the engine:
    0 = technical success and, in strict mode, a passing reconciliation
    2 = technical success with business exceptions (strict mode)
    1 = technical failure

    Use -ExitCodeMode defer when the caller needs to read the JSON or the
    key=value result file before making its own business assertion.

    This script is not a Tosca module. Confirm the approved process-execution
    mechanism in the installed Tricentis Tosca On-Premises environment, then
    point that mechanism at this file.

.EXAMPLE
    .\run_reconciliation.ps1 -Config ..\..\examples\config\cam_mdg.json -Python python
#>
[CmdletBinding()]
param(
    [string]$Config,
    [string]$Python = "python",
    [string]$ResultFile,
    [ValidateSet("strict", "defer")]
    [string]$ExitCodeMode = "strict",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArguments
)

$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}
$arguments = @("-m", "universal_utils.cli", "--exit-code-mode", $ExitCodeMode)
if ($Config) {
    $arguments += @("--config", $Config)
}
if ($ResultFile) {
    $arguments += @("--result-file", $ResultFile)
}
if ($RemainingArguments) {
    $arguments += $RemainingArguments
}

& $Python @arguments
$code = $LASTEXITCODE
if ($null -eq $code) {
    $code = 1
}
exit $code
