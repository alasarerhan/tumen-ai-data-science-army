$ports = @(8000, 5173)

foreach ($port in $ports) {
  $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  if (-not $listeners) {
    Write-Host "Port $port is already free."
    continue
  }

  $pids = $listeners | Select-Object -ExpandProperty OwningProcess -Unique
  foreach ($pid in $pids) {
    try {
      Stop-Process -Id $pid -Force -ErrorAction Stop
      Write-Host "Stopped process $pid on port $port."
    } catch {
      Write-Host "Could not stop process $pid on port $port: $($_.Exception.Message)"
    }
  }
}
