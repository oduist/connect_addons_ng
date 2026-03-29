# FreeSWITCH CLI Commands Reference

| Command | Description |
|---|---|
| `acl <ip> <list_name>` | Check if an IP is allowed/denied in a named ACL list |
| `reloadacl` | Reload ACL lists (may not re-fetch from xml_curl) |
| `reloadacl reloadxml` | Reload ACL + XML config together (deprecated, always does reloadxml) |
| `reloadxml` | Reload XML configuration from all sources including xml_curl |
| `sofia status` | Show all Sofia profiles, gateways, and their states |
| `sofia profile <name> rescan` | Rescan a profile for new gateways without restart |
| `sofia profile <name> restart` | Full restart of a Sofia profile (reloads everything) |
| `xml_curl debug_on` | Enable debug logging for xml_curl requests |
| `module_exists <name>` | Check if a FreeSWITCH module is loaded |
| `global_getvar <name>` | Get the value of a global FreeSWITCH variable |
