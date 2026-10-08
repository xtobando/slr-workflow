# Backups, recovery and staged updates

No system can guarantee that work will never be lost. The workbench now creates
verified snapshots; protection against loss of the whole device still requires
another copy on a separate drive or trusted backup service. Keep multiple dated
copies and periodically test restoring one. Archives contain research data and
are not encrypted; choose storage appropriate for your papers and notes.

## Create and verify a backup

```sh
# macOS/Linux
bash workbench.sh backup
bash workbench.sh backup --destination "/Volumes/BackupDrive/slr-backups"
bash workbench.sh backup-verify "/path/to/backup.zip"
```

```powershell
# Windows
.\workbench.ps1 backup
.\workbench.ps1 backup --destination "E:\slr-backups"
.\workbench.ps1 backup-verify "E:\slr-backups\backup.zip"
```

The default is a sibling folder named `PROJECT-backups`. To change the default for
this terminal and its child processes, set the environment variable before starting
OpenCode or running commands:

```sh
export SLR_BACKUP_DIR="/path/to/external-or-synced/backups"
```

```powershell
$env:SLR_BACKUP_DIR = "E:\slr-backups"
```

Each archive includes the configured review database, papers, drafts, reading
conversions, notes, source code, skills, protocol/workflow and dependency lockfile.
SQLite's backup API captures committed transactions, including WAL data. The
workbench holds a database writer lock while assembling the snapshot, checks the
event chain and document hashes, and verifies all archived file checksums before
publishing the ZIP. Large archives temporarily delay writes; close other sessions
and editors first for the clearest recovery point.

Environments, Git history, build outputs, caches and `.env` files are excluded.
Provider credentials outside the project are not included. Project symlinks and
configured storage paths outside the project are rejected rather than silently
omitted. Additional databases belonging to optional tools are not given SQLite
snapshot guarantees; stop those tools first and rebuild derived indexes if needed.
Checksums detect accidental changes; they do not authenticate an archive against
an attacker able to replace both its contents and manifest.

The system keeps every published backup; there is no automatic pruning. Monitor
space and remove old copies only after checking that other verified copies remain.
A sibling folder alone does not protect against disk failure. Sync the **completed
ZIP archives**, not a live SQLite database, to another storage device or service.

## Automatic snapshots

The project launcher takes snapshots before and after OpenCode sessions and
commands that write scientific state (initialization, imports, drafts, decisions,
attachments, retrieval and study links). It stops before starting an operation if
its initial backup fails. A failed follow-up backup is reported explicitly; the
operation may already have committed and must not simply be repeated blindly.

These are snapshots at command/session boundaries, not continuous replication.
Direct `python -m slr_workbench` calls, agent commands inside a running OpenCode
session, utility PDF reads, unsaved editor buffers and abrupt process termination
are not individually covered by these launcher hooks. During long sessions, run
`backup` periodically in another terminal. You can schedule that same command
with your OS scheduler using absolute paths and your chosen backup folder; no
background scheduler is installed automatically.

`SLR_AUTO_BACKUP=0` disables launcher snapshots for that terminal when needed.
Explicit `backup` and update preparation still create archives. This setting
reduces protection; it does not disable SQLite transactions or audit validation.

## Restore without overwriting your current review

```sh
bash workbench.sh restore "/path/to/backup.zip" "../recovered-review"
```

Windows uses `.\workbench.ps1 restore "E:\backups\backup.zip" "..\recovered-review"`.
The destination must not exist. Files are verified in a temporary directory, then
published as a new project folder. The original is never overwritten. Invalid
checksums, database integrity failures or missing/changed archived evidence stop
recovery before publishing the restored folder.

Open the restored folder, run guided setup, then `audit` and `status`. Existing
approvals are in the recovered database; do not approve again merely to recover.
Restore does not reinstall environments, Git history or account credentials.
Keep the original folder until you have inspected the recovery. A restore is a
point-in-time copy: changes after that snapshot must be recovered separately.

If the original project is gone, download a fresh workbench, run setup, then run
its `restore` command against the archive and a new destination.

## Check and prepare an update

Updates use the current branch's configured Git upstream; they do not assume a
repository owner. A ZIP checkout has no upstream: use a Git clone for this feature.

```sh
bash workbench.sh update --check
bash workbench.sh update --destination "../updated-review"
```

On Windows use `.\workbench.ps1 update --check` and
`.\workbench.ps1 update --destination "..\updated-review"`.

Preparation fetches the upstream branch, checks that it advances your current
commit, creates a verified backup, and creates a separate candidate checkout.
It installs locked dependencies and tests the candidate's example configuration,
then copies your saved data/configuration/customized OpenCode files and validates
the project plus database audit. Unsupported local source edits, deleted
customizations, divergent history or failing checks stop preparation. The
candidate's `update-validation.log` contains installation/test output. Failed
candidates must not be used; the active project remains intact.

Close OpenCode and other writers before preparing an update. When preparation
succeeds, inspect `status` in the new folder, then deliberately switch to it. Do
not work in both copies: updates capture only the backup's point in time. Keep
the old folder and backup for rollback. A future incompatible database migration
must provide an explicit migration path; the updater does not invent one or
approve a protocol amendment.

## Automatic updates through the stable launcher

Automatic updates are enabled by default for Git checkouts. Keep using the
**original** `workbench.sh` / `workbench.ps1`, even after switching versions.
It becomes the stable entry point and routes every command to the active copy.
Do not delete the original folder or its environment.

After a successful OpenCode session exits, the launcher checks the Git upstream,
backs up the saved review, prepares a separate candidate, installs dependencies,
and runs tests/audit. This can take several minutes; progress and failures are in
the candidate's `update-validation.log`. Network/test failures leave the current
version active. ZIP checkouts remain usable, but cannot auto-update without a Git
upstream. No machine-wide scheduler or background service is installed.

On the next OpenCode startup, the launcher creates verified snapshots of both
copies and compares them with the preparation fingerprints. Only an unchanged
source and unchanged tested candidate are eligible. New work, edited files or
altered candidates cancel activation; current work is retained and another update
can be prepared after the session. Changes to upstream protocol/workflow files or
SQL migrations stop automatic preparation for manual review. Approvals are never
silently transferred to a different protocol revision.

```sh
bash workbench.sh auto-update status
bash workbench.sh auto-update disable
bash workbench.sh auto-update enable
bash workbench.sh auto-update rollback
```

Windows uses `.\workbench.ps1` with the same arguments. `status` shows the active,
pending and previous folders. `disable` leaves the active version in place and
suspends preparation/activation. Rollback restores the previous route and disables
auto-update, but only if neither copy has changed since activation. If work has
continued, rollback refuses rather than discard it; use the backup/recovery path
to migrate that latest data deliberately. Older folders and archives are retained,
so monitor disk space.

Launcher invocations are serialized while a session or update is running. An
interrupted process can leave `.workbench-state/running.lock` in the original
folder. Close all workbench/OpenCode processes before removing that directory and
retrying. Never remove it while another session is active. Direct module commands,
editors and launching a candidate's own wrapper bypass this coordination: do not
write to either copy during switching. This is not protection against arbitrary
external processes or failing storage.

State is stored in `.workbench-state/state.json` in the original folder using
atomic replacement. It is excluded from review backups: restored reviews start
independently without routing into another installation. `SLR_CHECK_UPDATES=1`
still requests an extra check at session startup; it is unnecessary for the new
automatic preparation after successful sessions.

## Python command names

`python3.12` is a valid version-specific executable name, but some installations
provide only `python3`, `python`, or the Windows `py` launcher. `pyton` is a typo.
The setup scripts now try available command names and verify Python **3.12**
before continuing. They also accept `SLR_PYTHON` (an executable path); PowerShell
accepts `-PythonPath`. Routine work uses the project's own environment, so it does
not depend on a particular global Python command name.
