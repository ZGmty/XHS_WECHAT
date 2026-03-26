# Node 50 Network Recovery

## Goal

Restore the Windows network configuration for node `192.168.20.50` so it can reach the LAN and the internet without requiring Clash Verge system proxy.

## Recommended Recovery Order

1. Disable any system proxy settings left behind by Clash Verge.
2. Restore the active adapter to DHCP for IP and DNS.
3. Flush DNS, reset WinHTTP, and reset Winsock.
4. Renew the lease and reboot the node.

## One-Shot Script

Run this on the node itself in an elevated PowerShell session:

```powershell
c:/python314/python.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\repair_windows_network.ps1
```

If you know the adapter name, pass it explicitly:

```powershell
c:/python314/python.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\repair_windows_network.ps1 -AdapterName "Ethernet"
```

## What The Script Does

- turns off WinINET proxy values in the current user registry hive;
- resets WinHTTP proxy;
- enables DHCP on the selected adapter;
- resets DNS server addresses to automatic;
- flushes DNS cache;
- resets Winsock;
- renews the IP lease.

## If Ping Still Fails After Recovery

Check these in order:

1. Run `ipconfig /all` and confirm the adapter received an IPv4 address, gateway, and DNS server.
2. Run `route print` and confirm there is a default route `0.0.0.0/0` pointing to the gateway.
3. Verify the gateway is reachable inside the LAN with `ping <gateway-ip>`.
4. If the node only reaches the internet when Clash Verge is on, then the network path itself is proxy-only and must be fixed upstream, not only on Windows.

## Notes

- If this node is remote, you need to run the script on that node itself or through your remote management channel.
- If the node has a static IP requirement, do not leave it on DHCP permanently; switch the adapter back to the site-approved static config after connectivity is restored.