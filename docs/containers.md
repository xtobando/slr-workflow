# Container workflow

Docker provides the same Linux Python/OpenCode runtime on Windows, macOS and Linux.
It replaces host Python setup, but requires a running Docker installation and network
access for the initial image build and hosted model providers. The core image includes
Python 3.13.5, uv 0.12.23, OpenCode V2 2.0.23, PDF extraction, pytest and Ruff.
Both amd64 and arm64 package selection are supported; local validation may cover only
one architecture. No host Python environment is mounted into the container runtime.

## Start

Install Docker Desktop on Windows/macOS or Docker Engine and the Compose plugin on
Linux. Windows must use Linux containers. Extract or clone the repository, open a
terminal in the folder containing `compose.yaml`, then run:

```sh
docker compose build
docker compose run --rm workbench cli --help
docker compose run --rm workbench test -q
```

Customize `protocol.yaml` and `workflow.yaml` on the host before beginning a real
review. Initialize without approving anything:

```sh
docker compose run --rm workbench init
docker compose run --rm workbench status
docker compose run --rm workbench opencode --standalone
```

Use `/connect` and `/models` inside OpenCode. Authentication persists in its Docker
volume. An interactive session can be ended normally; `--rm` removes only the
container, leaving the project files and persistent volumes in place. Compose
publishes no network ports. No background workbench service is required.

In a separate human-operated terminal, use commands such as:

```sh
docker compose run --rm workbench approve-protocol --reviewer REVIEWER_ID
docker compose run --rm workbench review PROPOSAL_ID --reviewer REVIEWER_ID
```

These remain human decisions requiring interactive confirmation. Replace identifiers
with actual configured identities and proposal IDs. Agents must not execute them.

## Files and persistence

| Location | Storage | Contents |
| --- | --- | --- |
| `/review` | Your project folder, mounted from the host | Editable configuration, `data/`, papers, drafts, exports |
| `/backups` | Compose `backups` volume | Verified backup ZIPs |
| `/state` | Compose `opencode-state` volume | OpenCode credentials/configuration, logs and caches |
| `/opt/venv` | Image | Locked Python dependencies, independent of any host `.venv` |

Use paths relative to the project folder when passing files. For example, put a
paper in `data/incoming/paper.pdf`, then run:

```sh
docker compose run --rm workbench read-pdf data/incoming/paper.pdf
```

A Windows path such as `C:\papers\paper.pdf` is not a container path. Copy the paper
into the mounted project folder, or explicitly add a separate mount for it. Review
storage paths must remain project-local for backup verification to work.

The image runs as a non-root user. On Linux, if your checkout belongs to a different
UID/GID, set `SLR_UID` and `SLR_GID` to those IDs before running Compose. Ensure that
this user can write the checkout and the persistent volumes. Changing IDs after
creating volumes can require adjusting ownership. Docker Desktop normally handles
host bind-mount access without a UID override.

## Backups and moving devices

Launcher backup hooks still run before and after OpenCode sessions and selected
writing commands. Explicit backup and verification work too:

```sh
docker compose run --rm workbench backup
docker compose run --rm workbench backup-verify /backups/BACKUP_NAME.zip
```

To copy archives onto the host for transfer, start a temporary export container:

```sh
docker compose run -d --name slr-backup-export --entrypoint sleep workbench infinity
docker cp slr-backup-export:/backups ./exported-backups
docker rm -f slr-backup-export
```

Store completed ZIPs on another device or trusted backup service. The archives are
not encrypted. They do not include OpenCode credentials, which live outside the
project; connect your provider again on another device. Named volumes do not move
automatically with a copied checkout, and Compose volume names depend on the
project name. Do not use `docker compose down --volumes` unless you intend to delete
the backup and OpenCode state volumes.

On a new device, install Docker, copy your project including its ignored `data/`
folder, and rebuild the image. Alternatively restore a backup using a separate
mount as described in the recovery guide, then build/run Compose from the restored
folder. Backups exclude host environments and `.env` files.

## Updates

Containers use image rebuilds rather than the staged Git updater. Automatic version
routing is bypassed and `update` / `auto-update` commands are rejected with guidance.
This avoids creating host-style Python environments and routing to sibling checkouts
outside the mounted project.

Close running sessions, make and export a verified backup, then update your host
checkout (preserve local changes) or download the new source into a separate folder.
Run `docker compose build` and the tests again. Existing data and state are retained
when you keep the same project folder and Compose volume names. Follow protocol
revision and migration requirements; rebuilding does not approve research changes.
Rebuild after Python code/dependency changes: the installed package and launcher
are baked into the image. YAML, skills and research files are read from the mounted
project at runtime. Tests exercise the mounted source, so rebuild before relying
on CLI behavior from a changed checkout.

## Optional OCR and semantic retrieval

The default image uses lightweight PDF text extraction. To include Docling and
Chroma dependencies, set the build extras and rebuild. In PowerShell:

```powershell
$env:SLR_EXTRAS = "documents rag"
docker compose build
```

In bash:

```sh
SLR_EXTRAS="documents rag" docker compose build
```

You can select only `documents` or only `rag`. These extras greatly increase image
size and may download models at runtime. Dependencies/model compatibility and OCR
quality require separate validation; installing extras is not evidence that a
particular conversion works. The state cache volume retains supported model caches.

## Managed networks

Docker Desktop's proxy/network settings must allow package registries and your model
provider. The Dockerfile accepts an optional BuildKit `build_ca` secret for a trusted
CA bundle on managed networks; this bundle is used only during builds and is not
copied into image layers. For example:

```sh
docker build --secret id=build_ca,src=/path/to/trusted-ca-bundle.pem -t slr-workflow-workbench .
```

Supply proxy build arguments when your network requires them. Runtime provider
connections may also need Docker's proxy and trust configuration. Keep TLS and
package verification enabled.
