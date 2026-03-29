#!/bin/bash
# Yörünge Temizliği — 30 dakikada bir otomatik pipeline
# Kurulum: crontab -e  →  */30 * * * * /root/bursenal/scripts/cron_pipeline.sh

LOCKFILE=/tmp/bursenal_pipeline.lock
LOGFILE=/root/bursenal/pipeline_cron.log
PROJDIR=/root/bursenal

# Zaten çalışıyorsa atla
if [ -f "$LOCKFILE" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') [SKIP] Pipeline zaten çalışıyor (lock: $LOCKFILE)" >> "$LOGFILE"
    exit 0
fi

touch "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

echo "" >> "$LOGFILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') [START] Pipeline başlatıldı" >> "$LOGFILE"

cd "$PROJDIR"
"$PROJDIR/.venv/bin/python" run_pipeline.py >> "$LOGFILE" 2>&1
EXIT_CODE=$?

echo "$(date '+%Y-%m-%d %H:%M:%S') [END] exit=$EXIT_CODE" >> "$LOGFILE"
exit $EXIT_CODE
