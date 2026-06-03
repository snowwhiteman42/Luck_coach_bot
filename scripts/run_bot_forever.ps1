# run_bot_forever.ps1
# Watchdog: starts luck-bot.py and restarts it automatically if it crashes.

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$LogDir     = Join-Path $ProjectDir "logs"
$LogFile    = Join-Path $LogDir "bot_runner.log"
$BotScript  = Join-Path $ProjectDir "luck-bot.py"
$PythonExe  = "C:\Python314\python.exe"
$PythonPkgs = "C:\Users\Ilia\AppData\Roaming\Python\Python314\site-packages"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

function Write-Log($Message) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $Message" | Out-File -Append -FilePath $LogFile -Encoding UTF8
}

Write-Log "=== Watchdog started ==="
Write-Log "Project : $ProjectDir"
Write-Log "Python  : $PythonExe"
Write-Log "Pkgs    : $PythonPkgs"

while ($true) {
    Write-Log "--- Starting bot ---"
    try {
        # Use ProcessStartInfo directly for full control over env and output
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName               = $PythonExe
        $psi.Arguments              = "-X utf8 `"$BotScript`""
        $psi.WorkingDirectory       = $ProjectDir
        $psi.UseShellExecute        = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError  = $true
        $psi.CreateNoWindow         = $true

        # Set environment variables directly on the child process
        $psi.EnvironmentVariables['PYTHONPATH']       = $PythonPkgs
        $psi.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'

        $p = New-Object System.Diagnostics.Process
        $p.StartInfo = $psi
        $p.Start() | Out-Null

        # Read stdout and stderr asynchronously to avoid deadlock
        $outTask = $p.StandardOutput.ReadToEndAsync()
        $errTask = $p.StandardError.ReadToEndAsync()
        $p.WaitForExit()

        foreach ($text in @($outTask.Result, $errTask.Result)) {
            if ($text) {
                $text -split "`r?`n" | Where-Object { $_ -ne '' } | ForEach-Object {
                    Write-Log $_
                }
            }
        }

        Write-Log "Bot stopped (exit code $($p.ExitCode)). Restarting in 10 s..."
    } catch {
        Write-Log "Error launching bot: $_. Retrying in 10 s..."
    }
    Start-Sleep -Seconds 10
}
