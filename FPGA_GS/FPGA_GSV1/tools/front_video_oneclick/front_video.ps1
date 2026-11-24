param([switch]$Restore, [switch]$CheckOnly, [string]$Video)
$ErrorActionPreference = 'Stop'
$project = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$console = Join-Path $project 'release\FPGA_GSV1_SOURCE_MAP_3_6_1_CANDIDATE\tools\m3\console.py'
$python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python39\python.exe'
$stateFile = Join-Path $PSScriptRoot 'network_restore_state.clixml'
$address = '192.168.50.1'
$description = 'Realtek PCIe GbE Family Controller'

function Restore-Network {
    if (!(Test-Path -LiteralPath $stateFile)) { Write-Host 'No network change recorded.'; return }
    $saved = Import-Clixml -LiteralPath $stateFile
    $nic = @(Get-NetAdapter | Where-Object { $_.InterfaceGuid.ToString() -eq $saved.Guid })
    if ($nic.Count -ne 1) { throw 'Original network adapter not found. Saved state retained.' }
    $idx = $nic[0].ifIndex
    Get-NetIPAddress -InterfaceIndex $idx -AddressFamily IPv4 -PolicyStore ActiveStore |
        Where-Object IPAddress -eq $address |
        Remove-NetIPAddress -Confirm:$false
    if ($saved.Dhcp -eq 'Enabled') {
        Set-NetIPInterface -InterfaceIndex $idx -AddressFamily IPv4 -Dhcp Enabled -PolicyStore ActiveStore
    }
    Move-Item -LiteralPath $stateFile -Destination (Join-Path $PSScriptRoot ('network_restored_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.clixml'))
    Write-Host 'Original DHCP restored. Wi-Fi, DNS and gateway were not changed.' -ForegroundColor Green
}

function Start-Sender {
    Write-Host 'Select a video with the file-selection button in the sender window.'
    Write-Host 'FPGA KEY5: FRONT. Close the sender window normally to restore DHCP.'
    Push-Location (Split-Path $console -Parent)
    try {
        $senderArgs = @($console, '--role', 'right', '--bind', $address, '--board', '192.168.50.2', '--right-fps', '20')
        if ($Video) { $senderArgs += @('--video', $Video, '--loop') }
        & $python @senderArgs
        if ($LASTEXITCODE -ne 0) { throw "Sender exited with code $LASTEXITCODE" }
    } finally { Pop-Location }
}

try {
    if (!(Test-Path -LiteralPath $console)) { throw "Missing sender: $console" }
    if (!(Test-Path -LiteralPath $python)) { throw "Missing existing Python: $python" }
    if ($Video -and !(Test-Path -LiteralPath $Video -PathType Leaf)) { throw "Missing video: $Video" }
    & $python -c 'import tkinter, PIL; print(PIL.__version__)'
    if ($LASTEXITCODE -ne 0) { throw 'Existing Python dependencies are unavailable.' }
    $adapters = @(Get-NetAdapter | Where-Object InterfaceDescription -eq $description)
    if ($adapters.Count -ne 1) { throw 'Expected exactly one physical Realtek adapter; no network change made.' }
    $adapter = $adapters[0]
    $idx = $adapter.ifIndex
    $ips = @(Get-NetIPAddress -InterfaceIndex $idx -AddressFamily IPv4 -PolicyStore ActiveStore)
    $ipif = Get-NetIPInterface -InterfaceIndex $idx -AddressFamily IPv4 -PolicyStore ActiveStore
    Write-Host "Adapter: $($adapter.Name), index $idx, link $($adapter.Status), $($adapter.LinkSpeed)"
    $ips | Format-Table IPAddress, PrefixLength, PrefixOrigin
    if ($CheckOnly) {
        Write-Host "CHECK ONLY. DHCP=$($ipif.Dhcp). No address changes or sender launch."
        exit 0
    }
    if (!$Restore -and $adapter.Status -ne 'Up') { throw 'Ethernet cable/link is not up.' }
    $ready = @($ips | Where-Object { $_.IPAddress -eq $address -and $_.PrefixLength -eq 24 -and $_.AddressState -eq 'Preferred' }).Count -gt 0
    if (!$Restore -and $ready -and !(Test-Path -LiteralPath $stateFile)) {
        Start-Sender
        exit 0
    }
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (!$isAdmin) {
        $arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + $PSCommandPath + '"'
        if ($Restore) { $arguments += ' -Restore' }
        if ($Video) { $arguments += ' -Video "' + $Video + '"' }
        $child = Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $arguments -Wait -PassThru
        exit $child.ExitCode
    }
    if ($Restore) { Restore-Network; exit 0 }
    if (Test-Path -LiteralPath $stateFile) {
        throw 'An earlier session has saved network state. Close its sender and run the restore entry before starting again.'
    }
    $manual = @($ips | Where-Object PrefixOrigin -eq 'Manual')
    $gateways = @(Get-NetRoute -InterfaceIndex $idx -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue)
    if ($ipif.Dhcp -ne 'Enabled' -or $manual.Count -gt 0 -or $gateways.Count -gt 0) {
        throw 'Adapter has a static address or default gateway. Refusing to overwrite its configuration.'
    }
    $conflicts = @(Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '192.168.50.0/24' -ErrorAction SilentlyContinue | Where-Object InterfaceIndex -ne $idx)
    if ($conflicts.Count -gt 0) { throw '192.168.50.0/24 is already routed through another adapter.' }
    [pscustomobject]@{
        Guid = $adapter.InterfaceGuid.ToString(); Name = $adapter.Name
        Dhcp = $ipif.Dhcp.ToString(); SavedAt = (Get-Date).ToString('o')
        OriginalAddresses = $ips; OriginalInterface = $ipif
        OriginalDns = (Get-DnsClientServerAddress -InterfaceIndex $idx -AddressFamily IPv4)
    } | Export-Clixml -LiteralPath $stateFile
    try {
        New-NetIPAddress -InterfaceIndex $idx -AddressFamily IPv4 -IPAddress $address -PrefixLength 24 -PolicyStore ActiveStore | Out-Null
        $valid = $false
        for ($attempt = 0; $attempt -lt 20; $attempt++) {
            $current = Get-NetIPAddress -InterfaceIndex $idx -IPAddress $address -AddressFamily IPv4 -ErrorAction SilentlyContinue
            if ($current.AddressState -eq 'Duplicate') { throw 'Windows detected an address conflict.' }
            if ($current.AddressState -eq 'Preferred') { $valid = $true; break }
            Start-Sleep -Milliseconds 500
        }
        if (!$valid) { throw 'Temporary address did not become usable.' }
        Write-Host 'Temporary Ethernet address 192.168.50.1/24 is ready.' -ForegroundColor Green
        Start-Sender
    } finally { Restore-Network }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'If this window was forcibly closed earlier, use the network-restore entry.'
    Read-Host 'Press Enter to close'
    exit 1
}
