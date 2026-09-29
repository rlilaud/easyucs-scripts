# easyucs-scripts

Tooling that talks to one or more EasyUCS servers to pull the configuration and inventory of the UCS equipment they manage.

## Language

### Sources

**Instance**:
A running EasyUCS server, reached through its base URL. The tool may work against several Instances at once.
_Avoid_: Server, EasyUCS host, node

**Device**:
A piece of UCS equipment (UCS Manager, CIMC, IMM domain, UCS Central, Intersight) registered in exactly one Instance. The same physical equipment registered in two Instances counts as two Devices; no deduplication.
_Avoid_: UCS, equipment, target

**Catalog Device**:
A built-in, hidden pseudo-Device that EasyUCS creates per device type to hold its config catalog. It has no real equipment behind it.
_Avoid_: System device

### Artifacts

**Config**:
A snapshot of a Device's configuration as stored by its Instance.
_Avoid_: Configuration file, backup

**Inventory**:
A snapshot of a Device's hardware and component inventory as stored by its Instance.
_Avoid_: Hardware list, report

### Operations

**Fetch**:
Asking an Instance to reconnect to a Device live and produce a fresh Config and Inventory.
_Avoid_: Refresh, pull, sync

**Extraction**:
Getting a Device's Config and Inventory out of its Instance and saving them locally, with or without a Fetch first.
_Avoid_: Export, dump, backup
