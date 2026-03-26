param(
    [string]$AdapterName,
    [switch]$SkipDnsReset,
    [switch]$SkipProxyReset,
    [switch]$SkipDhcpReset,
    [switch]$SkipWinsockReset,
    [switch]$SkipWinHttpReset
)

$ErrorActionPreference = "Stop"

function Write-Section([string]$Text) {
    Write-Host "`n=== $Text ===" -ForegroundColor Cyan
}

function Get-PrimaryAdapter {
    $adapter = Get-NetAdapter |
        Where-Object { $_.Status -eq "Up" -and $_.HardwareInterface -eq $true } |
        Sort-Object -Property LinkSpeed -Descending |
        Select-Object -First 1

    if (-not $adapter) {
        $adapter = Get-NetAdapter |
            Where-Object { $_.Status -eq "Up" } |
            Select-Object -First 1
    }

    return $adapter
}

if (-not $AdapterName) {
    $adapter = Get-PrimaryAdapter
    if (-not $adapter) {
        throw "No active network adapter found"
    }
    $AdapterName = $adapter.Name
}

Write-Section "Target Adapter"
Write-Host $AdapterName

if (-not $SkipProxyReset) {
    Write-Section "Reset WinINET proxy"
    netsh winhttp reset proxy | Out-Host
    Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -Name ProxyEnable -Type DWord -Value 0
    Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -Name ProxyServer -ErrorAction SilentlyContinue
    Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" -Name AutoConfigURL -ErrorAction SilentlyContinue
}

if (-not $SkipWinHttpReset) {
    Write-Section "Reset WinHTTP proxy"
    netsh winhttp reset proxy | Out-Host
}

if (-not $SkipDhcpReset) {
    Write-Section "Switch adapter to DHCP"
    Set-NetIPInterface -InterfaceAlias $AdapterName -Dhcp Enabled
    Set-DnsClientServerAddress -InterfaceAlias $AdapterName -ResetServerAddresses

    $ipConfigs = Get-NetIPConfiguration -InterfaceAlias $AdapterName
    foreach ($ipConfig in $ipConfigs) {
        foreach ($ipAddress in $ipConfig.IPv4Address) {
            if ($ipAddress) {
                try {
                    Remove-NetIPAddress -InterfaceAlias $AdapterName -IPAddress $ipAddress.IPAddress -Confirm:$false -ErrorAction SilentlyContinue
                } catch {
                }
            }
        }
    }
}

if (-not $SkipDnsReset) {
    Write-Section "Flush DNS and renew"
    ipconfig /flushdns | Out-Host
}

if (-not $SkipWinsockReset) {
    Write-Section "Reset Winsock"
    netsh winsock reset | Out-Host
}

Write-Section "Renew IP"
ipconfig /release | Out-Host
ipconfig /renew | Out-Host

Write-Section "Network Summary"
Get-NetIPConfiguration -InterfaceAlias $AdapterName |
    Select-Object InterfaceAlias, IPv4Address, IPv4DefaultGateway, DNSServer |
    Format-List | Out-Host

Write-Section "Done"
Write-Host "Reboot is recommended after Winsock reset. If network still fails, check the gateway, DNS, and whether Clash Verge profile has a fallback route."