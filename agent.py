import os
import psycopg2
import requests
import time
from typing import Union
from psycopg2 import OperationalError
from psycopg2._psycopg import connection

def create_db_connection(dbname: str, user: str, password: str, host: str, port: int = 5432) -> Union[connection, None]:
    try:
        conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
        print(f"Successfully connected to {host}:{port}")
        return conn
    except OperationalError as err:
        print(f"Error while creating connection to {host}: {err}")
        return None

class DatabaseAgent:
    def __init__(self):
        self.role = os.environ.get('ROLE')
        self.user = os.environ.get('POSTGRES_USER')
        self.password = os.environ.get('POSTGRES_PASSWORD')
        self.dbname = os.environ.get('POSTGRES_DB')
        self.master_host = os.environ.get('MASTER_HOST')
        self.slave_host = os.environ.get('SLAVE_HOST')
        self.arbiter_host = os.environ.get('ARBITER_HOST')

        self.conn_to_master = None
        self.conn_to_slave = None

        print(f"Running as {self.role}")

        if self.role != "Arbiter":
            self.initialize_connections()

    def initialize_connections(self) -> None:
        """
        Master connects to Slave DB, Slave to Master DB, and Arbiter to both Master and Slave DBs.
        If the agent fails to connect to any DB during initialization within 20 seconds,
        connection attempts will cease but will resume in runMaster, runSlave, and runArbiter functions.
        """
        print("Trying to initialize connections...")

        if self.role == "Writer":
            self.conn_to_master = create_db_connection(self.dbname, self.user, self.password, self.master_host)
            self.conn_to_slave = create_db_connection(self.dbname, self.user, self.password, self.slave_host, 5433)
        else:
            for _ in range(4):
                if self.master_host and self.conn_to_master is None:
                    self.conn_to_master = create_db_connection(self.dbname, self.user, self.password, self.master_host)
                if self.slave_host and self.conn_to_slave is None:
                    self.conn_to_slave = create_db_connection(self.dbname, self.user, self.password, self.slave_host)

                if (self.master_host and not self.conn_to_master) or (self.slave_host and not self.conn_to_slave):
                    time.sleep(5)
                else:
                    break

    def check_conn_to_master(self) -> bool:
        try:
            if self.conn_to_master is None:
                self.conn_to_master = create_db_connection(self.dbname, self.user, self.password, self.master_host)
            cursor = self.conn_to_master.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception as err:
            print(f"Error while checking connection to Master, seems like it's dead: {err}")
            self.conn_to_master = None
            return False

    def check_conn_to_slave(self) -> bool:
        try:
            if self.conn_to_slave is None:
                self.conn_to_slave = create_db_connection(self.dbname, self.user, self.password, self.slave_host)
            cursor = self.conn_to_slave.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception as err:
            print(f"Error while checking connection to Slave, seems like it's dead: {err}")
            self.conn_to_slave = None
            return False

    def check_conn_arbiter_to_master(self) -> Union[bool, None]:
        try:
            response = requests.get(f'http://{self.arbiter_host}:5000/check/master')
            status = response.json().get('Master alive')
            print(f"Successfully received response from Arbiter. Master alive: {status}")
            return status
        except Exception as err:
            print(f"Error while making GET-request to Arbiter, seems like it's dead: {err}")
            return None

    def check_conn_to_arbiter(self) -> bool:
        try:
            response = requests.get(f'http://{self.arbiter_host}:5000/check/arbiter')
            status = response.json().get('Arbiter alive')
            print(f"Successfully received response from Arbiter. Arbiter alive: {status}")
            return status
        except Exception as err:
            print(f"Error while making GET-request to Arbiter, seems like it's dead: {err}")
            return False