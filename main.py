import subprocess
import time
from agent import Agent
from flask import Flask, jsonify

app = Flask(__name__)

def monitor_master():
    while True:
        print("Checking if connection to Arbiter is alive...")
        arbiter_status = agent.check_connection_to_arbiter()
        slave_status = agent.check_connection_to_slave()
        
        if not arbiter_status and not slave_status:
            print("Connections to Arbiter and Slave are dead. Blocking input connections...")
            insert_success = subprocess.run(["iptables", "-P", "INPUT", "DROP"])
            save_success = subprocess.run(["iptables-save", ">", "/etc/iptables/rules.v4"])
            
            if insert_success.returncode == 0:
                print('Successfully blocked input connections')
                break
            else:
                print('Error while inserting rule')
        
        time.sleep(5)

def monitor_slave():
    while True:
        print("Checking if connection between Arbiter and Master is alive...")
        arbiter_master_status = agent.check_connection_arbiter_to_master()

        if arbiter_master_status or arbiter_master_status is None:
            time.sleep(1)
        else:
            master_status = agent.check_connection_to_master()
            print(f"Checking if Master is alive: {master_status}")

            if not master_status:
                print('Promoting me to Master...')
                promote_trigger = subprocess.run(["touch", "/tmp/promote_me"])
                
                if promote_trigger.returncode == 0:
                    print('Successfully promoted to Master')
                    break
                else:
                    print('Error while creating trigger file')

def run_arbiter():
    @app.route('/check/master', methods=['GET'])
    def check_master():
        if agent.check_connection_to_master():
            return jsonify({"Master alive": True})
        else:
            return jsonify({"Master alive": False})

    @app.route('/check/arbiter', methods=['GET'])
    def check_arbiter():
        return jsonify({"Arbiter alive": True})
    # Start the web server to handle requests from A trying to connect to M and S
    # Arbiter needs to be responsive about itself and M
    app.run(debug=False, host='0.0.0.0')
    agent.initialize_connections()

if __name__ == '__main__':
    agent = Agent()

    if agent.role == "Master":
        monitor_master()
    elif agent.role == "Slave":
        monitor_slave()
    else:
        run_arbiter()