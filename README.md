# easyucs-scripts

`eucs` is a command-line tool that saves the **Config** and **Inventory** of every **Device** managed by one or more EasyUCS **Instances**, in one run, without clicking through each Instance's UI.

It is built for air-gapped and locked-down environments: every release ships as a single self-contained file, either a standalone executable that needs nothing installed, or a universal zipapp that runs with any Python 3.9+.

- [What it does](#what-it-does)
- [Supported platforms](#supported-platforms)
- [Installation (air-gapped)](#installation-air-gapped)
- [Usage](#usage)
- [Instances file](#instances-file)
- [Output](#output)
- [Exit codes](#exit-codes)
- [TLS](#tls)
- [Development and releases](#development-and-releases)
- [Why only pure-Python dependencies](#why-only-pure-python-dependencies)

## What it does

The terms below are defined in [GLOSSARY.md](GLOSSARY.md).

An **Instance** is a running EasyUCS server. Each Instance manages **Devices**: UCS Manager domains, CIMCs, IMM domains, UCS Central and Intersight. For every Device, EasyUCS can store a **Config** (a configuration snapshot) and an **Inventory** (a hardware and component inventory snapshot).

`eucs extract` performs an **Extraction** of every selected Device:

1. It lists the Devices of each Instance. **Catalog Devices**, the hidden pseudo-Devices EasyUCS creates to hold its config catalogs, are always skipped.
2. It asks the Instance to **Fetch** each Device, that is, to reconnect to it live and produce a fresh Config and Inventory. Use `--no-fetch` to skip this and take the most recent ones already stored.
3. It downloads the Config and Inventory of each Device into a new timestamped folder, then prints a summary table and exits with a non-zero code if anything failed.

All Instances are processed in parallel, with a bounded number of Devices per Instance, and a live progress bar shows each Device. One failing Device or Instance never stops the others.

## Supported platforms

| Artifact | Runs on |
| --- | --- |
| `eucs-windows-x86_64.exe` | Windows 10, Windows 11, Windows Server 2016 and later (x86-64) |
| `eucs-linux-x86_64` | RHEL 8+ and its rebuilds (AlmaLinux, Rocky Linux, Oracle Linux), Ubuntu 22.04+, SLES 15 SP4+ (x86-64, glibc 2.28 or later) |
| `eucs-macos-arm64` | macOS on Apple silicon; built in CI and smoke-tested, but unsigned and not tested by the maintainer |
| `eucs.pyz` | Any OS with Python 3.9 or later |

The executables embed their own Python; nothing else needs to be installed. End-of-life operating systems (RHEL/CentOS 7, Ubuntu 20.04 and older) are not supported.

## Installation (air-gapped)

Every [GitHub Release](https://github.com/rlilaud/easyucs-scripts/releases) carries the four artifacts above and a `SHA256SUMS` file. Pick the artifact for your platform, download it together with `SHA256SUMS` on a connected machine, and transfer both files into the air-gapped network.

### 1. Verify the checksum

Always verify the file after the transfer, on the target machine, to make sure it arrived intact.

**Linux**

```sh
sha256sum --check --ignore-missing SHA256SUMS
```

**macOS**

```sh
shasum -a 256 eucs-macos-arm64
grep eucs-macos-arm64 SHA256SUMS
```

The two hashes must be identical.

**Windows (PowerShell)**

```powershell
$expected = (Select-String -Path SHA256SUMS -Pattern 'eucs-windows-x86_64.exe').Line.Split(' ')[0]
(Get-FileHash .\eucs-windows-x86_64.exe -Algorithm SHA256).Hash -eq $expected
```

It must print `True`. Use the same commands with `eucs.pyz` to check the zipapp.

> [!IMPORTANT]
> A checksum only proves that the file was not altered after `SHA256SUMS` was downloaded. Get `SHA256SUMS` from the GitHub Release page itself, not from a copy someone sent you.

### 2. Install the artifact

**Windows executable**: copy `eucs-windows-x86_64.exe` anywhere, optionally rename it `eucs.exe` and put its folder on your `PATH`, then run:

```powershell
.\eucs-windows-x86_64.exe --version
```

**Linux executable**: make it executable and optionally move it onto your `PATH`:

```sh
chmod +x eucs-linux-x86_64
sudo mv eucs-linux-x86_64 /usr/local/bin/eucs
eucs --version
```

> [!NOTE]
> The executable unpacks itself into the temporary folder on each start. If `/tmp` is mounted `noexec` on hardened systems, point `TMPDIR` to a folder that allows execution, e.g. `TMPDIR=$HOME/tmp eucs --version`.

**macOS executable**: the executable is not signed or notarised, so Gatekeeper blocks it. Once you have verified its checksum, remove the quarantine flag the browser added and make it executable:

```sh
xattr -d com.apple.quarantine eucs-macos-arm64
chmod +x eucs-macos-arm64
./eucs-macos-arm64 --version
```

If `xattr` answers `No such xattr`, the file carries no quarantine flag (it was copied from a USB drive, for example) and there is nothing to remove. Alternatively, run it once, then open **System Settings > Privacy & Security** and click **Open Anyway** next to the message about `eucs-macos-arm64`.

**Zipapp**: run it with the Python already installed, no installation step needed:

```sh
python3 eucs.pyz --version        # Linux, macOS
py eucs.pyz --version             # Windows (or: python eucs.pyz --version)
```

On Linux and macOS you can also `chmod +x eucs.pyz` and run `./eucs.pyz` directly.

In the rest of this README, `eucs` stands for whichever artifact you installed.

## Usage

```sh
eucs --version                     # print the version
eucs --help                        # list the commands
eucs extract --help                # every option of extract
```

### `eucs extract`

Give at least one Instance, with `--url`, with `--instances`, or both:

```sh
# One Instance, by the root URL you type in your browser
eucs extract --url http://10.0.0.5:5010

# Several Instances ad hoc
eucs extract --url http://10.0.0.5:5010 --url https://easyucs.example.com

# A reusable Instances file, plus a one-off Instance
eucs extract --instances instances.yaml --url http://10.0.0.9:5010

# Only the UCS Manager and IMM domain Devices
eucs extract --instances instances.yaml --type ucsm --type imm_domain

# Only two Devices, without Fetching them again
eucs extract --instances instances.yaml --device FI-PARIS --device FI-LYON --no-fetch
```

| Option | Default | Description |
| --- | --- | --- |
| `--instances <file>` | | YAML or JSON [Instances file](#instances-file) listing the Instances to extract. |
| `--url <root-url>` | | Root URL of an Instance, as typed in a browser, e.g. `http://10.0.0.5:5010`. Repeatable; combines with `--instances`. |
| `--type <type>` | all types | Only extract Devices of this type: `ucsm`, `cimc`, `imm_domain`, `ucsc` or `intersight`. Repeatable. |
| `--device <name>` | all Devices | Only extract the Device with this name. Repeatable. |
| `--output <dir>` | `./extractions` | Directory in which a new timestamped run folder is created. |
| `--timeout <duration>` | `30m` | Maximum time to wait for each Device's Fetch: a number followed by `s`, `m` or `h` (`90s`, `30m`, `1h`), or a bare number of seconds. |
| `--no-fetch` | off | Skip the Fetch and save the most recent Config and Inventory already stored in the Instance. A Device with nothing stored is reported as failed. |
| `--force` | off | Ask EasyUCS to carry on the Fetch past failed SDK objects or Intersight license validation. **The saved Config may then be incomplete.** |
| `--workers <n>` | `4` | Maximum number of Devices extracted at the same time in each Instance. Instances always run in parallel. |
| `-v`, `--verbose` | off | Also show on the console the detailed log written to `run.log`. |

When `--type` and `--device` are both given, a Device must match both. If the filters match no Device in an Instance, `eucs` says so; this is not a failure.

## Instances file

An Instances file keeps a reusable list of Instances. It is YAML, or JSON if its name ends in `.json`.

```yaml
instances:
  # Only 'url' is required; this Instance is named 10.0.0.5_5010 after its host and port.
  - url: http://10.0.0.5:5010

  # A short name for readable output folders and summaries.
  - url: https://easyucs-paris.example.com
    name: paris
    # Verify the certificate against an internal CA, relative to this file's folder.
    ca_bundle: certs/company-root-ca.pem

  # A lab Instance with a self-signed certificate.
  - url: https://10.1.0.20
    name: lab
    verify_tls: false

  # Explicitly no authentication (the only type EasyUCS supports today).
  - url: http://10.0.0.6:5010
    name: lyon
    auth:
      type: none
```

The same file in JSON:

```json
{
  "instances": [
    { "url": "http://10.0.0.5:5010" },
    { "url": "https://easyucs-paris.example.com", "name": "paris", "ca_bundle": "certs/company-root-ca.pem" },
    { "url": "https://10.1.0.20", "name": "lab", "verify_tls": false },
    { "url": "http://10.0.0.6:5010", "name": "lyon", "auth": { "type": "none" } }
  ]
}
```

| Field | Required | Description |
| --- | --- | --- |
| `url` | yes | Root URL of the Instance, `http://` or `https://`, as typed in a browser. Must not contain credentials. |
| `name` | no | Name used for the output folder and in the summary. Defaults to the host and port, e.g. `10.0.0.5_5010`. |
| `verify_tls` | no | `true` (default) or `false`. See [TLS](#tls). |
| `ca_bundle` | no | PEM file of the CA certificates to trust for this Instance. A relative path is relative to the Instances file's folder. See [TLS](#tls). |
| `auth` | no | Authentication block, reserved for the future. See below. |

Every Instance, from the file or from `--url`, must end up with a distinct name; give `name` to tell apart two Instances on the same host and port. Unknown fields are rejected so that typos don't pass silently, and an error in an entry names the file, the entry and the field at fault.

### The `auth` block

EasyUCS has no authentication today, but the Instances file already reserves an `auth` block so that your files keep working when it does:

- `type` is required in the block. Only `none` is accepted today; any other type is refused with a clear error, so you are never led to believe credentials are being used.
- `username` and `password_env` are reserved for future authentication types. `password_env` holds the **name of an environment variable** that holds the password, never the password itself. When such a type exists and the variable is not set, `eucs` will ask for the password with a masked prompt instead.

```yaml
instances:
  - url: https://easyucs-paris.example.com
    name: paris
    auth:
      type: none                   # the only type accepted today
      # Reserved for a future authentication type:
      # username: operator
      # password_env: EUCS_PARIS_PASSWORD
```

A `password` field, at the top of an entry or in `auth`, is always refused. A plain-text password in a file ends up in backups, shared folders and repositories; reading it from an environment variable keeps it out of every file. For the same reason, URLs containing `@`, as in `user:password@host`, are refused, and `eucs` never writes secrets or authentication headers to the console, `run.log` or `summary.json`.

## Output

Each run creates a new folder named after its start time inside `--output`, so previous runs are never overwritten:

```text
extractions/
└── 2026-09-30_17-14-05/
    ├── run.log
    ├── summary.json
    ├── paris/
    │   ├── FI-PARIS/
    │   │   ├── config.json
    │   │   └── inventory.json
    │   └── intersight-eu/
    │       ├── config.json
    │       └── inventory.json
    └── 10.0.0.5_5010/
        └── ...
```

- `config.json` and `inventory.json` are the files EasyUCS returns, saved as-is.
- Instance and Device names are made safe for file names on every OS, Windows included: characters such as `<>:"/\|?*` become `_`. When two names end up the same, the later folder gets a `_2`, `_3`... suffix. A second run started in the same second also gets a `_2` suffix.
- `run.log` is the detailed log of the run, to diagnose a failure or send to someone. `-v` shows it on the console too.
- `summary.json` is the machine-readable summary of the run:

```json
{
  "parameters": {
    "instances_file": "instances.yaml",
    "urls": [],
    "device_types": [],
    "device_names": [],
    "output": "extractions",
    "no_fetch": false,
    "force": false,
    "timeout_seconds": 1800.0,
    "workers": 4
  },
  "succeeded": false,
  "instances": [
    { "name": "paris", "url": "https://easyucs-paris.example.com", "outcome": "succeeded", "reason": null },
    { "name": "lyon", "url": "http://10.0.0.6:5010", "outcome": "failed", "reason": "GET http://10.0.0.6:5010/api/v1/devices failed: ..." }
  ],
  "devices": [
    {
      "instance": "paris",
      "name": "FI-PARIS",
      "type": "ucsm",
      "outcome": "succeeded",
      "reason": null,
      "files": { "config": "paris/FI-PARIS/config.json", "inventory": "paris/FI-PARIS/inventory.json" }
    },
    {
      "instance": "paris",
      "name": "intersight-eu",
      "type": "intersight",
      "outcome": "failed",
      "reason": "...",
      "files": {}
    }
  ]
}
```

File paths in `summary.json` are relative to the run folder, with `/` separators on every OS.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Every selected Device was extracted. An Instance where the filters match no Device does not count as a failure. |
| `1` | At least one Device or Instance failed (unreachable Instance, Fetch failed or timed out, nothing stored with `--no-fetch`...). Everything else was still extracted; see the summary table, `summary.json` and `run.log`. |
| `2` | Invalid input: no Instance given, invalid Instances file, or invalid option value. Nothing was extracted. |

## TLS

For `https://` Instances, `eucs` verifies the Instance's certificate by default. Without `ca_bundle`, it is verified against the public CAs bundled with `eucs` (the Mozilla list shipped by [certifi](https://pypi.org/project/certifi/)), **not** against your operating system's certificate store, unless the `REQUESTS_CA_BUNDLE` or `CURL_CA_BUNDLE` environment variable names another CA bundle file. For an Instance whose certificate is issued by an internal CA, list it in an Instances file and set `ca_bundle`.

- **`ca_bundle: <file>`**: the PEM file of the CA certificates that issued the Instance's certificate (the root CA, plus any intermediate CA the Instance does not send). A relative path is relative to the Instances file's folder.
- **`verify_tls: false`**: disables verification for that Instance, for lab Instances with self-signed certificates. Anyone on the network path could then intercept the connection, so `eucs` prints a warning on every run. `ca_bundle` and `verify_tls: false` cannot be combined.

These options exist only in the Instances file; an Instance given with `--url` is verified against the bundled public CAs, or the bundle named by `REQUESTS_CA_BUNDLE` or `CURL_CA_BUNDLE`.

### Checking a CA bundle

A CA bundle decides whom `eucs` trusts, so check it before use:

```sh
openssl x509 -text -noout -in certs/company-root-ca.pem
```

This shows the first certificate of the file; if the bundle holds several, check each one. Look for:

- **Validity**: `Not Before` is in the past and `Not After` is in the future. An expired CA certificate makes every connection fail.
- **Key strength**: under `Subject Public Key Info`, an RSA key of at least 2048 bits (`Public-Key: (2048 bit)` or more), or an EC key on P-256 or stronger (`NIST CURVE: P-256`, `P-384` or `P-521`).
- **Signature algorithm**: from the SHA-2 family, such as `sha256WithRSAEncryption` or `ecdsa-with-SHA256`. Never `md5` or `sha1`, which allow certificate forgery.
- **Issuer and Subject**: they are identical for a root CA, which is expected. They should not be identical for the Instance's own certificate: a self-signed Instance certificate is only acceptable in a lab, where `verify_tls: false` is the honest setting.

## Development and releases

Development needs Python 3.9 or later:

```sh
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest                   # tests run against a fake EasyUCS, no real Instance needed
python -m mypy
```

Set `EUCS_TEST_URL` to the root URL of a real Instance to also run the integration test against it.

`eucs` is a single Python package, `easyucs_scripts`, with one module per subcommand under `commands/`, registered explicitly in `cli.py`. All HTTP traffic to an Instance goes through `client.py`, which new subcommands reuse.

Every pull request runs the tests on Windows and Linux with Python 3.9 and 3.13. Pull requests that touch the build also build and smoke-test the artifacts (`scripts/build_executable.py`, `scripts/build_zipapp.py`, `scripts/smoke_test.py`).

To publish a release:

1. Set `__version__` in `src/easyucs_scripts/__init__.py` to the new version, e.g. `1.2.0`, and merge it.
2. Tag that commit `v1.2.0` and push the tag: `git tag v1.2.0 && git push origin v1.2.0`.

The Artifacts workflow then checks that the tag matches `__version__`, builds and smoke-tests every artifact on its OS, and publishes them with `SHA256SUMS` as a GitHub Release. The smoke tests check that each artifact's `eucs --version` prints that same version.

## Why only pure-Python dependencies

`eucs` must run where nothing can be installed, so it ships as a one-file executable per OS and as a single zipapp for any Python 3.9+ on any OS. The zipapp is what makes that universal promise possible, and it only holds if **every bundled dependency is pure Python**: a compiled extension (`.so`, `.pyd`, `.dylib`) only works on the OS, CPU architecture and Python version it was built for, and Python cannot import extensions from inside a zip file anyway.

That is why the dependencies are limited to pure-Python packages: [Typer](https://typer.tiangolo.com/) (with Click), [Rich](https://rich.readthedocs.io/), [requests](https://requests.readthedocs.io/) with its pure-Python dependencies, and [PyYAML](https://pyyaml.org/).

PyYAML is the one exception that needs care: its wheels include an optional compiled accelerator, `_yaml`. The zipapp build removes it, and PyYAML then falls back to its own pure-Python implementation, which is plenty fast for an Instances file. The build fails if any compiled file remains in the zipapp.

Before adding a dependency, check that it is pure Python (it publishes a `py3-none-any` wheel) and that its own dependencies are too. A compiled dependency would break the zipapp for every operator who relies on it.
