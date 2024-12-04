from flask import Flask, request, jsonify
import requests
import subprocess
import os
import time

app = Flask(__name__)

@app.route('/')
def index():
    return '''
        <form method="post" action="/check">
            <label for="url">Enter OVPN file URL:</label>
            <input type="text" id="url" name="url" required>
            <button type="submit">Check</button>
        </form>
    '''

@app.route('/check', methods=['POST'])
def check_ovpn():
    url = request.form['url']
    log_file = "openvpn.log"  # Use a file for logging

    try:
        # Download OVPN file
        response = requests.get(url)
        response.raise_for_status()
        with open("temp.ovpn", "wb") as f:
            f.write(response.content)

        # Modify the OVPN file: remove specific lines
        with open("temp.ovpn", "r") as f:
            lines = f.readlines()

        filtered_lines = []
        for line in lines:
            # Filter out lines with specific configurations
            if "register-dns" in line or "block-outside-dns" in line:
                continue  # Remove lines containing "register-dns" or "block-outside-dns"
            
            if "auth SHA1" in line:
                continue  # Remove lines containing "auth SHA1"
            
            if "auth-user-pass" in line:
                # If "auth-user-pass" is commented (i.e., starts with #), remove the comment
                if line.strip().startswith("#"):
                    line = line.lstrip("#").lstrip()  # Remove the '#' and any leading spaces
                filtered_lines.append(line)
            else:
                filtered_lines.append(line)

        # Write the filtered lines back to the OVPN file
        with open("temp.ovpn", "w") as f:
            f.writelines(filtered_lines)

        # Clear log file before starting
        if os.path.exists(log_file):
            os.remove(log_file)

        # Prepare credentials
        credentials_file = "ovpn_credentials.txt"
        with open(credentials_file, "w") as f:
            f.write("tai\n")  # Username
            f.write("tai\n")  # Password

        # Start OpenVPN process
        process = subprocess.Popen(
            ["openvpn", "--config", "temp.ovpn", "--log", log_file, "--auth-user-pass", credentials_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # Wait and check for AUTH_FAILED status
        timeout_seconds = 20
        wait_time = 10
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
                with open(log_file, "r") as f:
                    log_content = f.read()
                if "AUTH_FAILED" in log_content:
                    process.terminate()
                    return jsonify(status=1, log=log_content)  # Treat AUTH_FAILED as successful for your case
            time.sleep(1)

        # If we waited and no relevant message is found
        with open(log_file, "r") as f:
            log_content = f.read()

        if "AUTH_FAILED" in log_content:
            process.terminate()
            return jsonify(status=1, log=log_content)  # Treat AUTH_FAILED as successful for your case

        # Check if VPN initialized successfully
        if "Initialization Sequence Completed" in log_content:
            process.terminate()
            return jsonify(status=1, log=log_content)

        # If no relevant message found, return failure
        process.terminate()
        return jsonify(status=0, log=log_content)

    except requests.RequestException as e:
        return jsonify(status=0, error=f"Failed to download OVPN file: {e}")
    except FileNotFoundError:
        return jsonify(status=0, error="OpenVPN executable not found. Please install OpenVPN.")
    except Exception as e:
        return jsonify(status=0, error=f"An error occurred: {e}")
    finally:
        if os.path.exists(log_file):
            os.remove(log_file)
        if os.path.exists(credentials_file):
            os.remove(credentials_file)

if __name__ == "__main__":
    app.run(debug=True)
