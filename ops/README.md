# Oracle VM deployment (2026-10-03)

The system runs on an Oracle Cloud Always-Free VM.Standard.E2.1.Micro (uncontested capacity pool,
unlike the Ampere A1.Flex shape the earlier `retry_launch.py` was stuck on). IP: 129.225.96.113.
SSH: `ssh -i ~/.ssh/oracle_trading ubuntu@129.225.96.113`.

Code is deployed via `rsync`/`tar`-over-SSH from this laptop, not `git clone` - the repo has 45+
commits ahead of origin (pushing to the public GitHub remote was blocked by the permission system
as an out-of-place publication; redeploy the same way until that's resolved).

- `systemd/` - unit + timer files, installed to /etc/systemd/system/ on the VM
- `jobs/` - the shell/python scripts the units call, installed to /opt/trading/jobs/ on the VM
- `set-token.py` is installed as /usr/local/bin/set-token, wrapped by a tiny root-owned shim that
  `sudo -u trading`'s into it (it must run as the `trading` user, which owns .env at mode 600 -
  the `ubuntu` SSH login user can't read/write it directly)

Daily token refresh: `ssh -i ~/.ssh/oracle_trading ubuntu@129.225.96.113 set-token`, paste, Ctrl-D.
Local helper: `tools/refresh-dhan-token.bat` (or the artifact) does this in one step.

Offsite backup: nightly, uploaded to Oracle Object Storage bucket `trading-vm-backups` (namespace
axencpvjdbl1, ap-hyderabad-1) via a WRITE-ONLY pre-authorized request stored at
/opt/trading/backup_par_url.txt on the VM (not in git - it's a bearer secret). PAR name
"nightly-backup-writer", expires 2028-10-03. 30-day local retention in /opt/trading/backups/;
no auto-archive tier (blocked by a missing tenancy IAM policy for the object storage service
principal - not set up, since backups are ~300KB and won't approach the 10GB free limit for years).
Rollback: the laptop's 6 scheduled tasks are Disabled (not deleted) - `Enable-ScheduledTask`.
