$device = Get-PnpDevice | Where-Object { $_.FriendlyName -like "*Prolific*" -or $_.FriendlyName -like "*COM3*" }
if ($device) {
    Write-Host "Restarting: $($device.FriendlyName)"
    Disable-PnpDevice -InstanceId $device.InstanceId -Confirm:$false
    Start-Sleep -Seconds 2
    Enable-PnpDevice -InstanceId $device.InstanceId -Confirm:$false
    Start-Sleep -Seconds 2
    Write-Host "Done"
} else {
    Write-Host "Device not found"
}
