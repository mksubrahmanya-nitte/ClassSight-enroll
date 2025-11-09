import os
import re
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, auth
from firebase_admin.exceptions import FirebaseError

# --- Configuration ---
ROOT_DIR = "enrollment_data"  # main folder for all enrollment photos
SERVICE_ACCOUNT_KEY_PATH = "cam-attendance-a4881-firebase-adminsdk-fbsvc-9067f34903.json"

# --- Initialize Firebase ---
try:
    cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)
    firebase_admin.initialize_app(cred)
    print("[INFO] Firebase Admin SDK initialized successfully.")
except FileNotFoundError:
    print(f"[FATAL ERROR] Firebase key missing at: {SERVICE_ACCOUNT_KEY_PATH}")
    exit()
except FirebaseError as e:
    print(f"[FATAL ERROR] Firebase init failed: {e}")
    exit()

# --- Initialize Flask ---
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Ensure root folder exists
if not os.path.exists(ROOT_DIR):
    os.makedirs(ROOT_DIR)

def get_usn_from_email(email):
    """
    Extracts branch and number from email like nnm24cs124@nmamit.in -> (CS, CS_124)
    """
    match = re.search(r'([a-z]{2})(\d{3})@nmamit\.in', email)
    if match:
        branch = match.group(1).upper()  # CS
        number = match.group(2)          # 124
        usn_folder = f"{branch}_{number}"
        return branch, usn_folder
    else:
        return "UNKNOWN", email.split('@')[0].replace('.', '_')


@app.route('/enroll', methods=['POST'])
def enroll():
    """Receives base64 images and saves them in the correct folder"""
    # 1️⃣ Verify Firebase token
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"status": "error", "message": "Missing authentication token"}), 401

        token = auth_header.split(' ')[1]
        decoded_token = auth.verify_id_token(token)
        email = decoded_token.get('email', None)
        if not email:
            return jsonify({"status": "error", "message": "No email found in token"}), 401

    except Exception as e:
        return jsonify({"status": "error", "message": f"Authentication failed: {e}"}), 401

    # 2️⃣ Extract branch and USN
    branch, usn_folder = get_usn_from_email(email)
    print(f"[INFO] Enrollment request for {email} => Branch: {branch}, USN: {usn_folder}")

    # 3️⃣ Create folders dynamically
    branch_dir = os.path.join(ROOT_DIR, branch)
    person_dir = os.path.join(branch_dir, usn_folder)
    os.makedirs(person_dir, exist_ok=True)

    # 4️⃣ Process and save images
    try:
        data = request.get_json()
        if not data or 'images' not in data:
            return jsonify({"status": "error", "message": "'images' key missing"}), 400

        images_data_urls = data['images']
        if len(images_data_urls) != 5:
            return jsonify({"status": "error", "message": f"Expected 5 images, got {len(images_data_urls)}"}), 400

        angle_names = ["frontal", "left", "right", "up", "down"]
        for i, data_url in enumerate(images_data_urls):
            if ',' in data_url:
                encoded = data_url.split(",", 1)[1]
            else:
                encoded = data_url
            binary_data = base64.b64decode(encoded)
            filepath = os.path.join(person_dir, f"{angle_names[i]}.jpg")
            with open(filepath, "wb") as f:
                f.write(binary_data)

        print(f"[SUCCESS] Saved 5 images for {usn_folder} in {person_dir}")
        return jsonify({
            "status": "success",
            "message": f"Enrollment saved for {usn_folder} under branch {branch}",
            "path": person_dir
        }), 200

    except Exception as e:
        print(f"[ERROR] Enrollment failed: {e}")
        return jsonify({"status": "error", "message": f"Internal error: {e}"}), 500


if __name__ == "__main__":
    print("[INFO] Server running at http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
