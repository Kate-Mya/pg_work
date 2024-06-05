!/bin/bash

# Установка флага -e для выхода при ошибке
set -e

# Функция для инициализации базы данных
initialize_database() {
  # Создание директории данных PostgreSQL
  mkdir -p "$PGDATA"
  chmod 700 "$PGDATA"
  chown -R postgres "$PGDATA"

  # Создание директории для запуска PostgreSQL
  mkdir -p /run/postgresql
  chmod g+s /run/postgresql
  chown -R postgres /run/postgresql

  # Проверка на существование файла PG_VERSION
  if [ ! -s "$PGDATA/PG_VERSION" ]; then
    # Инициализация новой базы данных
    if [ -z "$REPLICATE_FROM" ]; then
      echo "Initializing PostgreSQL database..."
      gosu postgres initdb $POSTGRES_INITDB_ARGS
    else
      # Репликация данных с мастер-сервера
      echo "Replicating data from master server..."
      until gosu postgres pg_basebackup -h ${REPLICATE_FROM} -D ${PGDATA} -U ${POSTGRES_USER} -vP -w
      do
        echo "Waiting for master to connect..."
        sleep 1s
      done
    fi

    # Проверка пароля и установка метода аутентификации
    if [ -n "$POSTGRES_PASSWORD" ]; then
      pass="PASSWORD '$POSTGRES_PASSWORD'"
      authMethod=md5
    else
      echo "ⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷ"
      echo "WARNING: No password has been set for the database."
      echo "         This will allow anyone with access to the"
      echo "         Postgres port to access your database. In"
      echo "         Docker's default configuration, this is"
      echo "         effectively any other container on the same"
      echo "         system."
      echo "         Use '-e POSTGRES_PASSWORD=password' to set"
      echo "         it in 'docker run'."
      echo "ⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷⒷ"
      pass=
      authMethod=trust
    fi

    # Настройка pg_hba.conf
    echo "host replication all 0.0.0.0/0 $authMethod" | gosu postgres tee -a "$PGDATA/pg_hba.conf" > /dev/null
    echo "host all all 0.0.0.0/0 $authMethod" | gosu postgres tee -a "$PGDATA/pg_hba.conf" > /dev/null

    # Запуск сервера PostgreSQL
    echo "Starting PostgreSQL server..."
    gosu postgres pg_ctl -D "$PGDATA" -o "-c listen_addresses='localhost'" -w start

    # Создание базы данных, если не задана переменная окружения POSTGRES_DB
    if [ -z "$POSTGRES_DB" ]; then
      POSTGRES_DB=$POSTGRES_USER
    fi

    # Создание пользователя, если не задан пароль
    if [ -z "$POSTGRES_PASSWORD" ]; then
      echo "Creating user '$POSTGRES_USER'..."
      gosu postgres psql -v ON_ERROR_STOP=1 --username postgres -c "CREATE USER '$POSTGRES_USER' WITH SUPERUSER;"
    else
      echo "Creating user '$POSTGRES_USER' with password..."
      gosu postgres psql -v ON_ERROR_STOP=1 --username postgres -c "CREATE USER '$POSTGRES_USER' WITH SUPERUSER PASSWORD '$POSTGRES_PASSWORD';"
    fi

    # Создание базы данных
    echo "Creating database '$POSTGRES_DB'..."
    gosu postgres psql -v ON_ERROR_STOP=1 --username postgres -c "CREATE DATABASE '$POSTGRES_DB';"

    echo "PostgreSQL init process complete; ready for start up."
  fi
}

# Экспорт переменных из файла /app.env в окружение
export $(egrep -v '^#' /app.env | xargs)

# Запуск агента
python3 -u /app/main.py &

# Обратная совместимость для старых имен переменных (устарело)
if [ "x$PGUSER" != "x" ]; then
    POSTGRES_USER=$PGUSER
fi
if [ "x$PGPASSWORD" != "x" ]; then
    POSTGRES_PASSWORD=$PGPASSWORD
fi

# Совместимость для старых имен переменных (pg_basebackup использует их)
if [ "x$PGPASSWORD" = "x" ]; then
    export PGPASSWORD=$POSTGRES_PASSWORD
fi

# Проверка первого аргумента
if [ "${1:0:1}" = '-' ]; then
  set -- postgres "$@"
fi

# Обработка команды 'postgres'
if [ "$1" = 'postgres' ]; then
  # Вызов функции для инициализации базы данных
  initialize_database
fi

# Запуск команды PostgreSQL
exec gosu postgres "$@"