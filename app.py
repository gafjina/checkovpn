from flask import Flask, request, jsonify, send_from_directory
import requests
import subprocess
import os
import time
import shutil
import uuid
import logging

# Inisialisasi Flask
app = Flask(__name__)

# Folder untuk menyimpan OVPN yang berhasil
STORED_OVPNS_FOLDER = "stored_ovpns"
os.makedirs(STORED_OVPNS_FOLDER, exist_ok=True)

# Konfigurasi logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

@app.route('/')
def index():
    # Ambil daftar file yang ada di folder stored_ovpns
    files = os.listdir(STORED_OVPNS_FOLDER)
    files_list = ''.join(
        f'<li><a href="/download/{file}" target="_blank">{file}</a></li>' for file in files
    )
    return f'''
        <form method="post" action="/check">
            <label for="url">Enter OVPN file URL:</label>
            <input type="text" id="url" name="url" required>
            <button type="submit">Check</button>
        </form>
        <h3>Available Files:</h3>
        <ul>{files_list}</ul>
        <form method="post" action="/clear" style="margin-top: 20px;">
            <button type="submit">Clear All Files</button>
        </form>
    '''

@app.route('/check', methods=['POST'])
def check_ovpn():
    url = request.form['url']
    log_file = "openvpn.log"

    try:
        # Download OVPN file
        logging.debug(f"Downloading OVPN file from: {url}")
        response = requests.get(url)
        response.raise_for_status()
        with open("temp.ovpn", "wb") as f:
            f.write(response.content)
        logging.debug("OVPN file downloaded and saved as temp.ovpn")

        # Modify the OVPN file: remove specific lines
        with open("temp.ovpn", "r") as f:
            lines = f.readlines()

        filtered_lines = []
        for line in lines:
            if "register-dns" in line or "block-outside-dns" in line:
                continue
            if "auth SHA1" in line:
                continue
            if "auth-user-pass" in line:
                if line.strip().startswith("#"):
                    line = line.lstrip("#").lstrip()
                filtered_lines.append(line)
            else:
                filtered_lines.append(line)

        # Write filtered lines back to temp.ovpn
        with open("temp.ovpn", "w") as f:
            f.writelines(filtered_lines)
        logging.debug("OVPN file modified and saved back to temp.ovpn")

        # Clear log file before starting
        if os.path.exists(log_file):
            os.remove(log_file)

        # Prepare credentials
        credentials_file = "ovpn_credentials.txt"
        with open(credentials_file, "w") as f:
            f.write("tai\n")
            f.write("tai\n")
        logging.debug("Credentials file created")

        # Start OpenVPN process
        process = subprocess.Popen(
            ["openvpn", "--config", "temp.ovpn", "--log", log_file, "--auth-user-pass", credentials_file],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # Wait for log updates
        timeout_seconds = 20  # Tambahkan waktu jika koneksi membutuhkan waktu lebih lama
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
                with open(log_file, "r") as f:
                    log_content = f.read()
                if "AUTH_FAILED" in log_content:
                    process.terminate()
                    logging.debug("Authentication failed. Saving OVPN file.")
                    unique_name = f"ovpn_{int(time.time())}_{uuid.uuid4().hex[:6]}.ovpn"
                    stored_file_path = os.path.join(STORED_OVPNS_FOLDER, unique_name)
                    
                    # Modify the file before saving
                    try:
                        with open("temp.ovpn", "r") as temp_file:
                            lines = temp_file.readlines()

                        # Modify the auth-user-pass line
                        modified_lines = []
                        for line in lines:
                            if "auth-user-pass" in line and not line.strip().startswith("#"):
                                modified_lines.append("<auth-user-pass>\n")
                                modified_lines.append("vpn\n")
                                modified_lines.append("vpn\n")
                                modified_lines.append("</auth-user-pass>\n")
                            else:
                                modified_lines.append(line)

                        # Write the modified file to stored_ovpns
                        with open(stored_file_path, "w") as modified_file:
                            modified_file.writelines(modified_lines)

                        logging.debug(f"File saved successfully with modifications: {stored_file_path}")
                    except Exception as e:
                        logging.error(f"Failed to save modified OVPN file: {e}")
                        return jsonify(status=0, error=f"Failed to save modified OVPN file: {e}")

                    return jsonify(status=1, log=log_content, download_url=f"/download/{unique_name}")

            time.sleep(1)

        # If no relevant message found, check final log content
        with open(log_file, "r") as f:
            log_content = f.read()

        logging.debug(f"Log content: {log_content}")

        if "AUTH_FAILED" in log_content:
            process.terminate()
            logging.debug("Authentication failed. Saving OVPN file.")
            unique_name = f"ovpn_{int(time.time())}_{uuid.uuid4().hex[:6]}.ovpn"
            stored_file_path = os.path.join(STORED_OVPNS_FOLDER, unique_name)
            
            # Modify the file before saving
            try:
                with open("temp.ovpn", "r") as temp_file:
                    lines = temp_file.readlines()

                # Modify the auth-user-pass line
                modified_lines = []
                for line in lines:
                    if "auth-user-pass" in line and not line.strip().startswith("#"):
                        modified_lines.append("<auth-user-pass>\n")
                        modified_lines.append("vpn\n")
                        modified_lines.append("vpn\n")
                        modified_lines.append("</auth-user-pass>\n")
                    else:
                        modified_lines.append(line)

                # Write the modified file to stored_ovpns
                with open(stored_file_path, "w") as modified_file:
                    modified_file.writelines(modified_lines)

                logging.debug(f"File saved successfully with modifications: {stored_file_path}")
            except Exception as e:
                logging.error(f"Failed to save modified OVPN file: {e}")
                return jsonify(status=0, error=f"Failed to save modified OVPN file: {e}")

            return jsonify(status=1, log=log_content, download_url=f"/download/{unique_name}")

        if "Initialization Sequence Completed" in log_content:
            # Save successful OVPN file
            unique_name = f"ovpn_{int(time.time())}_{uuid.uuid4().hex[:6]}.ovpn"
            stored_file_path = os.path.join(STORED_OVPNS_FOLDER, unique_name)
            logging.debug(f"Attempting to save file as: {stored_file_path}")

            # Modify the file before saving
            try:
                with open("temp.ovpn", "r") as temp_file:
                    lines = temp_file.readlines()

                # Modify the auth-user-pass line
                modified_lines = []
                for line in lines:
                    if "auth-user-pass" in line and not line.strip().startswith("#"):
                        modified_lines.append("<auth-user-pass>\n")
                        modified_lines.append("vpn\n")
                        modified_lines.append("vpn\n")
                        modified_lines.append("</auth-user-pass>\n")
                    else:
                        modified_lines.append(line)

                # Write the modified file to stored_ovpns
                with open(stored_file_path, "w") as modified_file:
                    modified_file.writelines(modified_lines)

                logging.debug(f"File saved successfully with modifications: {stored_file_path}")
            except Exception as e:
                logging.error(f"Failed to save modified OVPN file: {e}")
                return jsonify(status=0, error=f"Failed to save modified OVPN file: {e}")

            process.terminate()
            return jsonify(status=1, log=log_content, download_url=f"/download/{unique_name}")

        process.terminate()
        return jsonify(status=0, log=log_content)

    except requests.RequestException as e:
        logging.error(f"Failed to download OVPN file: {e}")
        return jsonify(status=0, error=f"Failed to download OVPN file: {e}")
    except FileNotFoundError:
        logging.error("OpenVPN executable not found. Please install OpenVPN.")
        return jsonify(status=0, error="OpenVPN executable not found. Please install OpenVPN.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify(status=0, error=f"An error occurred: {e}")
    finally:
        if os.path.exists(log_file):
            os.remove(log_file)
        if os.path.exists(credentials_file):
            os.remove(credentials_file)

@app.route('/download/<filename>')
def download(filename):
    return send_from_directory(STORED_OVPNS_FOLDER, filename, as_attachment=True)

@app.route('/clear', methods=['POST'])
def clear_files():
    shutil.rmtree(STORED_OVPNS_FOLDER)
    os.makedirs(STORED_OVPNS_FOLDER, exist_ok=True)
    return "All stored OVPN files have been cleared!"

if __name__ == "__main__":
    app.run(debug=True)
