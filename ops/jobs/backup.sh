#!/bin/bash
set -e
cd /opt/trading
STAMP=$(date +%Y%m%d_%H%M)
mkdir -p backups
tar --exclude='repo/exec_data/*.lock' --exclude='repo/journal_data/cache' \
    -I 'zstd -19' -cf "backups/trading_${STAMP}.tar.zst" repo/exec_data repo/journal_data
# verify the archive reads back before trusting it / uploading / pruning anything
zstd -t "backups/trading_${STAMP}.tar.zst"
# 30-day local retention
find backups -name "trading_*.tar.zst" -mtime +30 -delete

# offsite: Oracle Object Storage, via a WRITE-ONLY pre-authorized link (can't list, read or delete
# existing backups even if this VM is ever compromised - see trading-vm-backups bucket, PAR
# "nightly-backup-writer", expires 2028-10-03). Local success is reported regardless of this.
UPLOAD_OK=0
if [ -f backup_par_url.txt ]; then
  PAR_URL=$(cat backup_par_url.txt)
  if curl -sf -X PUT -T "backups/trading_${STAMP}.tar.zst" "${PAR_URL}trading_${STAMP}.tar.zst"; then
    UPLOAD_OK=1
  fi
fi

cd /opt/trading/repo && export PYTHONPATH=/opt/trading/repo
if [ "$UPLOAD_OK" = "1" ]; then
  .venv/bin/python -c "
from trading_exec.notify import notify
notify('[backup] nightly snapshot', ['wrote backups/trading_${STAMP}.tar.zst', 'verified readable', 'uploaded offsite (Oracle Object Storage)'], 'info')
"
else
  .venv/bin/python -c "
from trading_exec.notify import notify
notify('[backup] nightly snapshot - OFFSITE UPLOAD FAILED', ['wrote backups/trading_${STAMP}.tar.zst', 'verified readable', 'offsite upload did not succeed - local copy is still fine, check backup_par_url.txt / network'], 'warning')
"
fi
