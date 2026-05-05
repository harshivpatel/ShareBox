# ShareBox

A simplified cloud storage application built with FastAPI and Google Cloud Platform, allowing users to manage files and directories in the cloud.

## Tech Stack

- Python 3.12
- FastAPI
- Google Cloud Firestore
- Google Cloud Storage
- Firebase Authentication
- Jinja2 Templates

## Project Structure

```text
ShareBox/
├── static/
│   ├── firebase-login.js    # Firebase Auth logic (Frontend)
│   └── styles.css           # Custom UI styling
├── templates/
│   ├── main.html
│   └── duplicates.html
├── main.py                  # FastAPI backend and Firestore logic
├── local_constants.py       # Local GCP/Firebase config (git-ignored)
├── requirements.txt         # Python dependencies
├── .gitignore               # Files excluded from version control
└── app.yaml                 # App Engine deployment configuration


## Setup

### 1. Clone the repository

```bash
git clone https://github.com/harshivpatel/ShareBox.git
cd ShareBox
```

### 2. Create and activate virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure local constants

Create a `local_constants.py` file in the root directory:

```python
PROJECT_NAME = "csp-2026-489809"
CLOUD_STORAGE_BUCKET = "csp-2026-489809.appspot.com"
```

### 5. Authenticate with Google Cloud

```bash
gcloud auth application-default login
```

### 6. Run the application

```bash
uvicorn main:app --reload
```

Open your browser at `http://localhost:8000`

## Features

### Group 1
- Firebase login and signup
- User document created on first login
- Root directory created on first login
- Create directory
- Delete directory

### Group 2
- Navigate into directories
- Go up a directory
- Hide go up option at root
- Upload files to Cloud Storage

### Group 3
- Delete files
- Download files
- Prevent deletion of non-empty directories
- Duplicate file detection in current directory

### Group 4
- Global duplicate file detection
- File sharing between accounts
- UI improvements
