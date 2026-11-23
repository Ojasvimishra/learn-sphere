Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "Starting LearnSphere Platform (Django + MongoDB)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# Check if MongoDB is running
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("127.0.0.1", 27017)
    $tcp.Close()
    Write-Host "[OK] MongoDB is active on port 27017." -ForegroundColor Green
} catch {
    Write-Host "[INFO] Starting MongoDB daemon..." -ForegroundColor Yellow
    Start-Process -FilePath "C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe" -ArgumentList "--dbpath `"$PSScriptRoot\mongodb_data`" --port 27017 --bind_ip 127.0.0.1" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

Write-Host "[INFO] Launching Django Server at http://127.0.0.1:8000/ ..." -ForegroundColor Green
Start-Process "http://127.0.0.1:8000/"
& "$PSScriptRoot\.venv\Scripts\python.exe" "$PSScriptRoot\manage.py" runserver 127.0.0.1:8000
