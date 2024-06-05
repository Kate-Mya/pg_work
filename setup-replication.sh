#!/bin/bash

# Проверяем, установлен ли REPLICATE_FROM
if [[ -z "$REPLICATE_FROM" ]]; then
  # Если нет, настраиваем PostgreSQL для горячего резервирования
  cat >> "${PGDATA}/postgresql.conf" <<EOF
wal_level = hot_standby
max_wal_senders = "$PG_MAX_WAL_SENDERS"
wal_keep_segments = "$PG_WAL_KEEP_SEGMENTS"
hot_standby = on
synchronous_commit = remote_apply
EOF
else
  # Если да, настраиваем PostgreSQL в режиме резервной копии
  cat > "${PGDATA}/recovery.conf" <<EOF
standby_mode = on
primary_conninfo = 'host="$REPLICATE_FROM" port=5432 user="$POSTGRES_USER" password="$POSTGRES_PASSWORD"'
trigger_file = "/tmp/promote_me"
EOF

  # Настраиваем права доступа к recovery.conf
  chown postgres "${PGDATA}/recovery.conf"
  chmod 600 "${PGDATA}/recovery.conf"
fi