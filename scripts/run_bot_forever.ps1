# run_bot_forever.ps1
# Watchdog: starts luck-bot.py and restarts it automatically if it crashes.

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$LogDir     = Join-Path $ProjectDir "logs"
$LogFile    = Join-Path $LogDir "bot_runner.log"
$BotScript  = Join-Path $ProjectDir "luck-bot.py"
$PythonExe  = "C:\Python314\python.exe"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

function Write-Log($Message) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $Message" | Out-File -Append -FilePath $LogFile -Encoding utf8
}

Write-Log "=== Watchdog started ==="
Write-Log "Project : $ProjectDir"
Write-Log "Bot     : $BotScript"

while ($true) {
    Write-Log "--- Starting bot ---"
    try {
        $outFile = Join-Path $LogDir "out.tmp"
        $errFile = Join-Path $LogDir "err.tmp"

        $p = Start-Process `
            -FilePath $PythonExe `
            -ArgumentList "`"$BotScript`"" `
            -WorkingDirectory $ProjectDir `
            -PassThru `
            -NoNewWindow `
            -RedirectStandardOutput $outFile `
            -RedirectStandardError  $errFile

        $p.WaitForExit()

        # Append captured output to log
        foreach ($f in @($outFile, $errFile)) {
            if (Test-Path $f) {
                Get-Content $f | ForEach-Object { Write-Log $_ }
                Remove-Item $f
            }
        }

        Write-Log "Bot stopped (exit code $($p.ExitCode)). Restarting in 10 s..."
    } catch {
        Write-Log "Failed to start bot: $_. Retrying in 10 s..."
    }
    Start-Sleep -Seconds 10
}
