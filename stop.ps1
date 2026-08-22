# LearningOS PowerShell Stop Script
$Port = if ($env:LEARNINGOS_PORT) { [int]$env:LEARNINGOS_PORT } else { 8000 }
$DevPort = 5173

Write-Host "Stopping LearningOS instances on ports $Port and $DevPort..." -ForegroundColor Yellow

foreach ($p in @($Port, $DevPort)) {
    try {
        $connections = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue
        if ($connections) {
            foreach ($conn in $connections) {
                if ($conn.OwningProcess -and $conn.OwningProcess -ne 0) {
                    Write-Host "Killing process ID $($conn.OwningProcess) on port $p..." -ForegroundColor Gray
                    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
                }
            }
        }
    } catch {
        # continue
    }
}

Write-Host "LearningOS stopped." -ForegroundColor Green
