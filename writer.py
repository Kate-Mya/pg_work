import random
import subprocess
import time
from agent import Agent
from dotenv import load_dotenv
from psycopg2 import sql
from psycopg2._psycopg import connection

# Load environment variables
load_dotenv("docker/writer.env")

successfully_inserted_count = 0
failed_inserted_count = 0


def create_table_if_not_exists(table_name: str) -> None:
    cursor = agent.conn_master.cursor()
    cursor.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table_name)))
    cursor.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} (id integer PRIMARY KEY)").format(sql.Identifier(table_name)))

    agent.conn_master.commit()
    cursor.close()


def insert_number_into_table(connection: connection, number: int, table_name: str) -> bool:
    global successfully_inserted_count, failed_inserted_count
    try:
        cursor = connection.cursor()
        cursor.execute(sql.SQL("INSERT INTO {} (id) VALUES (%s)").format(sql.Identifier(table_name)), (number,))
        connection.commit()
        cursor.close()
        successfully_inserted_count += 1
        return True
    except Exception as error:
        print(f"Error while inserting number {number}: {error}")
        connection.rollback()
        failed_inserted_count += 1
        return False


def test_slave_failure():
    print("Running test where the Slave dies...")

    # Create a table if it doesn't exist
    create_table_if_not_exists("test_slave_down")

    for i in range(10000):
        if i == 5000:
            if subprocess.run(["docker", "compose", "stop", "pg-slave"]).returncode == 0:
                print("Slave was successfully killed")

        if insert_number_into_table(agent.conn_master, i, "test_slave_down"):
            print(f"Successfully wrote number {i} in the database!")
        time.sleep(random.choice([0.1, 0.2, 0.3, 0.4, 0.5]))

    print(f"Test where Slave dies is done. Successful inserts: {successfully_inserted_count}. Failed inserts: {failed_inserted_count}")
    if subprocess.run(["docker", "compose", "start", "pg-slave"]).returncode == 0:
        print("Slave was successfully resurrected")


def test_master_failure():
    print("Running test where the Master dies...")
    connection = agent.conn_master

    # Create a table if it doesn't exist
    create_table_if_not_exists("test_master_down")

    for i in range(1000000):
        if i == 500000:
            if subprocess.run(["docker", "compose", "stop", "pg-master"]).returncode == 0:
                print("Master was successfully killed")
            connection = agent.conn_slave

        if insert_number_into_table(connection, i, "test_master_down"):
            print(f"Successfully wrote number {i} in the database!")
        time.sleep(random.choice([0.1, 0.2, 0.3, 0.4, 0.5]))

    print(f"Test where Master dies is done. Successful inserts: {successfully_inserted_count}. Failed inserts: {failed_inserted_count}")
    if subprocess.run(["docker", "compose", "start", "pg-master"]).returncode == 0:
        print("Master was successfully resurrected")


if __name__ == '__main__':
    agent = Agent()

    test_slave_failure()

    successfully_inserted_count = 0
    failed_inserted_count = 0

    time.sleep(5)  # Wait for the Slave database to fully come up
    agent.initialize_connections()
    test_master_failure()