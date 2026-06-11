$dev = Get-PnpDevice | Where-Object { $_.FriendlyName -like "*Prolific*" } | Select-Object -First 1
if ($dev) {
    Disable-PnpDevice -InstanceId $dev.InstanceId -Confirm:$false
    Start-Sleep -Seconds 3
    Enable-PnpDevice -InstanceId $dev.InstanceId -Confirm:$false
    Write-Output "Reset OK"
} else {
    Write-Output "Prolific device not found"
}
