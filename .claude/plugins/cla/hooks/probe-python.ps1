$CLA_PYTHON_COMMAND = $null
$CLA_PYTHON_PREFIX = @()

function Get-ClaPythonCandidate {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string[]]$Prefix = @()
    )
    $application = Get-Command -Name $Name -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($application) {
        return @{
            Command = $application.Path
            Prefix = $Prefix
        }
    }
    return $null
}

$candidates = @()
if ($env:CLA_PYTHON) {
    $override = Get-ClaPythonCandidate -Name $env:CLA_PYTHON
    if ($override) {
        $candidates += $override
    }
}
else {
    foreach ($name in @('python3', 'py', 'python')) {
        $prefix = if ($name -eq 'py') { @('-3') } else { @() }
        $candidate = Get-ClaPythonCandidate -Name $name -Prefix $prefix
        if ($candidate) {
            $candidates += $candidate
        }
    }

    $knownPaths = @()
    if ($env:LOCALAPPDATA) {
        $knownPaths += Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" `
            -File -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
    }
    if ($env:ProgramFiles) {
        $knownPaths += Get-ChildItem -Path "$env:ProgramFiles\Python3*\python.exe" `
            -File -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
    }
    foreach ($path in $knownPaths) {
        $candidates += @{ Command = $path; Prefix = @() }
    }
}

$versionCheck = 'import sys; sys.stdout.write("1" if sys.version_info >= (3, 8) else "0")'
foreach ($candidate in $candidates) {
    $testArgs = @($candidate.Prefix) + @('-c', $versionCheck)
    $result = & $candidate.Command @testArgs 2>$null
    if ($LASTEXITCODE -eq 0 -and (($result -join '').Trim() -eq '1')) {
        $CLA_PYTHON_COMMAND = $candidate.Command
        $CLA_PYTHON_PREFIX = @($candidate.Prefix)
        break
    }
}

if ($env:CLA_PYTHON -and -not $CLA_PYTHON_COMMAND) {
    [Console]::Error.WriteLine("cla: CLA_PYTHON=$env:CLA_PYTHON is not a working Python 3.8+ — guard hooks are NOT running")
}
elseif (-not $CLA_PYTHON_COMMAND) {
    [Console]::Error.WriteLine('cla: no working Python 3.8+ found — guard hooks are NOT running')
}
