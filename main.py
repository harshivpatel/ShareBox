from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import google.oauth2.id_token
from google.auth.transport import requests
from google.cloud import firestore, storage
import local_constants
import hashlib
import datetime
import io

app = FastAPI()

firebase_request_adapter = requests.Request()
db = firestore.Client(project=local_constants.PROJECT_NAME)

app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates")


def get_user(user_token):
    # Fetches the user document from Firestore.
    # Returns None if user doesn't exist yet.
    return db.collection('users').document(user_token['user_id']).get()


def create_user(user_token):
    # Creates a new user document and a root directory for first-time login.
    db.collection('users').document(user_token['user_id']).set({
        'email': user_token['email']
    })
    db.collection('directories').add({
        'name': 'root',
        'path': '/',
        'owner': user_token['user_id'],
        'parent': None
    })


def get_directories(user_id, current_path):
    # Fetches all directories owned by the user in the current path.
    dirs = db.collection('directories').where(
        'owner', '==', user_id
    ).where(
        'path', '==', current_path
    ).get()
    return [{'id': d.id, 'name': d.to_dict()['name']} for d in dirs]


def get_files(user_id, current_path):
    # Fetches all files in current path and flags duplicates using MD5 hash comparison.
    files = db.collection('files').where(
        'owner', '==', user_id
    ).where(
        'path', '==', current_path
    ).get()

    file_list = []
    for f in files:
        data = f.to_dict()
        file_list.append({
            'id':   f.id,
            'name': data['name'],
            'hash': data.get('hash', '')
        })

    # Count how many files share each hash
    hash_counts = {}
    for f in file_list:
        h = f['hash']
        if h:
            hash_counts[h] = hash_counts.get(h, 0) + 1

    # Mark files that share a hash as duplicates
    for f in file_list:
        f['is_duplicate'] = hash_counts.get(f['hash'], 0) > 1

    return file_list


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    id_token = request.cookies.get("token")
    error_message = None
    user_token = None
    directories = []
    files = []
    current_path = request.cookies.get("current_path", "/")

    if id_token:
        try:
            user_token = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter
            )
            user = get_user(user_token)
            if not user.exists:
                create_user(user_token)

            directories = get_directories(user_token['user_id'], current_path)
            files = get_files(user_token['user_id'], current_path)

        except ValueError as err:
            print(str(err))
            error_message = str(err)

    return templates.TemplateResponse(
        request=request,
        name='main.html',
        context={
            'user_token':    user_token,
            'error_message': error_message,
            'directories':   directories,
            'files':         files,
            'current_path':  current_path
        }
    )


@app.post("/navigate", response_class=RedirectResponse)
async def navigate(request: Request, dir_name: str = Form(...)):
    # Navigates into a subdirectory by updating the current_path cookie.
    current_path = request.cookies.get("current_path", "/")

    if current_path == "/":
        new_path = "/" + dir_name
    else:
        new_path = current_path + "/" + dir_name

    response = RedirectResponse('/', status_code=302)
    response.set_cookie("current_path", new_path)
    return response


@app.get("/navigate-up", response_class=RedirectResponse)
async def navigate_up(request: Request):
    # Navigates up one directory level by trimming the last segment of current_path.
    current_path = request.cookies.get("current_path", "/")

    if current_path != "/":
        new_path = current_path.rsplit("/", 1)[0]
        if new_path == "":
            new_path = "/"
    else:
        new_path = "/"

    response = RedirectResponse('/', status_code=302)
    response.set_cookie("current_path", new_path)
    return response


@app.post("/create-directory", response_class=RedirectResponse)
async def create_directory(request: Request, dirname: str = Form(...)):
    # Creates a new directory in the current path.
    # Checks for duplicate names to prevent major bug.
    id_token = request.cookies.get("token")
    user_token = None

    if id_token:
        try:
            user_token = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter
            )
        except ValueError as err:
            print(str(err))
            return RedirectResponse('/', status_code=302)

    if not user_token:
        return RedirectResponse('/', status_code=302)

    current_path = request.cookies.get("current_path", "/")

    existing = db.collection('directories').where(
        'owner', '==', user_token['user_id']
    ).where(
        'path', '==', current_path
    ).where(
        'name', '==', dirname
    ).get()

    if len(existing) == 0:
        db.collection('directories').add({
            'name':   dirname,
            'path':   current_path,
            'owner':  user_token['user_id'],
            'parent': current_path
        })

    response = RedirectResponse('/', status_code=302)
    response.set_cookie("current_path", current_path)
    return response


@app.post("/delete-directory", response_class=RedirectResponse)
async def delete_directory(request: Request, dir_id: str = Form(...)):
    # Deletes a directory by its Firestore document ID.
    # Blocks deletion if directory contains files or subdirectories.
    id_token = request.cookies.get("token")
    user_token = None

    if id_token:
        try:
            user_token = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter
            )
        except ValueError as err:
            print(str(err))
            return RedirectResponse('/', status_code=302)

    if not user_token:
        return RedirectResponse('/', status_code=302)

    current_path = request.cookies.get("current_path", "/")

    # Block deletion of root directory
    dir_doc = db.collection('directories').document(dir_id).get()
    if not dir_doc.exists:
        return RedirectResponse('/', status_code=302)

    dir_data = dir_doc.to_dict()
    if dir_data.get('path') == '/' and dir_data.get('name') == 'root':
        return RedirectResponse('/', status_code=302)

    # Build the full path of the directory being deleted
    if dir_data.get('path') == '/':
        full_path = '/' + dir_data.get('name')
    else:
        full_path = dir_data.get('path') + '/' + dir_data.get('name')

    # Check for subdirectories and files inside this directory
    subdirs = db.collection('directories').where(
        'path', '==', full_path
    ).get()

    subfiles = db.collection('files').where(
        'path', '==', full_path
    ).get()

    if len(subdirs) > 0 or len(subfiles) > 0:
        response = RedirectResponse('/', status_code=302)
        response.set_cookie("current_path", current_path)
        response.set_cookie("dir_error", "not_empty")
        return response

    db.collection('directories').document(dir_id).delete()

    response = RedirectResponse('/', status_code=302)
    response.set_cookie("current_path", current_path)
    response.delete_cookie("dir_error")
    return response


@app.post("/upload-file", response_class=RedirectResponse)
async def upload_file(request: Request, file: UploadFile = File(...), overwrite: str = Form(default="no")):
    # Uploads a file to GCS and creates a File document in Firestore.
    # Computes MD5 hash for duplicate detection.
    # If file already exists, asks user to confirm overwrite.
    id_token = request.cookies.get("token")
    user_token = None

    if id_token:
        try:
            user_token = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter
            )
        except ValueError as err:
            print(str(err))
            return RedirectResponse('/', status_code=302)

    if not user_token:
        return RedirectResponse('/', status_code=302)

    current_path = request.cookies.get("current_path", "/")

    # Read file contents and compute MD5 hash
    contents = await file.read()
    file_hash = hashlib.md5(contents).hexdigest()

    # Check if file already exists in this directory
    existing = db.collection('files').where(
        'owner', '==', user_token['user_id']
    ).where(
        'path', '==', current_path
    ).where(
        'name', '==', file.filename
    ).get()

    if len(existing) > 0 and overwrite != "yes":
        # File exists and user has not confirmed overwrite
        response = RedirectResponse('/', status_code=302)
        response.set_cookie("current_path", current_path)
        response.set_cookie("overwrite_file", file.filename)
        return response

    if len(existing) > 0 and overwrite == "yes":
        # Delete old GCS blob and Firestore document before re-uploading
        storage_client = storage.Client(project=local_constants.PROJECT_NAME)
        bucket = storage_client.bucket(local_constants.CLOUD_STORAGE_BUCKET)
        for doc in existing:
            old_blob_path = doc.to_dict().get('blob_path')
            bucket.blob(old_blob_path).delete()
            db.collection('files').document(doc.id).delete()

    # Upload to GCS
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.bucket(local_constants.CLOUD_STORAGE_BUCKET)
    blob_path = user_token['user_id'] + current_path + "/" + file.filename
    blob = bucket.blob(blob_path)
    blob.upload_from_file(io.BytesIO(contents), content_type=file.content_type)

    # Save file document to Firestore with hash
    db.collection('files').add({
        'name':      file.filename,
        'path':      current_path,
        'owner':     user_token['user_id'],
        'blob_path': blob_path,
        'hash':      file_hash
    })

    response = RedirectResponse('/', status_code=302)
    response.set_cookie("current_path", current_path)
    response.delete_cookie("overwrite_file")
    return response


@app.post("/clear-overwrite", response_class=RedirectResponse)
async def clear_overwrite(request: Request):
    # Clears the overwrite confirmation cookie when user cancels.
    response = RedirectResponse('/', status_code=302)
    response.delete_cookie("overwrite_file")
    return response


@app.post("/delete-file", response_class=RedirectResponse)
async def delete_file(request: Request, file_id: str = Form(...)):
    # Deletes a file from GCS and removes its Firestore document.
    # Uses document ID to prevent deleting the wrong file.
    id_token = request.cookies.get("token")
    user_token = None

    if id_token:
        try:
            user_token = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter
            )
        except ValueError as err:
            print(str(err))
            return RedirectResponse('/', status_code=302)

    if not user_token:
        return RedirectResponse('/', status_code=302)

    current_path = request.cookies.get("current_path", "/")

    # Get file document to find the blob path in GCS
    file_doc = db.collection('files').document(file_id).get()
    if file_doc.exists:
        blob_path = file_doc.to_dict().get('blob_path')

        # Delete from GCS
        storage_client = storage.Client(project=local_constants.PROJECT_NAME)
        bucket = storage_client.bucket(local_constants.CLOUD_STORAGE_BUCKET)
        bucket.blob(blob_path).delete()

        # Delete from Firestore
        db.collection('files').document(file_id).delete()

    response = RedirectResponse('/', status_code=302)
    response.set_cookie("current_path", current_path)
    return response


@app.get("/download-file/{file_id}")
async def download_file(request: Request, file_id: str):
    # Downloads a file by streaming it directly from GCS to the browser.
    # Avoids signed URLs which require a service account key.
    from fastapi.responses import StreamingResponse
    import io

    id_token = request.cookies.get("token")
    user_token = None

    if id_token:
        try:
            user_token = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter
            )
        except ValueError as err:
            print(str(err))
            return RedirectResponse('/', status_code=302)

    if not user_token:
        return RedirectResponse('/', status_code=302)

    file_doc = db.collection('files').document(file_id).get()
    if file_doc.exists:
        file_data = file_doc.to_dict()
        blob_path = file_data.get('blob_path')
        file_name = file_data.get('name')

        storage_client = storage.Client(project=local_constants.PROJECT_NAME)
        bucket = storage_client.bucket(local_constants.CLOUD_STORAGE_BUCKET)
        blob = bucket.blob(blob_path)

        # Download blob into memory and stream it to the browser
        file_bytes = io.BytesIO()
        blob.download_to_file(file_bytes)
        file_bytes.seek(0)

        return StreamingResponse(
            file_bytes,
            media_type='application/octet-stream',
            headers={'Content-Disposition': f'attachment; filename="{file_name}"'}
        )

    return RedirectResponse('/', status_code=302)

def get_all_duplicates(user_id):
    # Fetches all files owned by the user across all directories.
    # Groups them by hash and returns only groups with more than one file.
    all_files = db.collection('files').where(
        'owner', '==', user_id
    ).get()

    hash_map = {}
    for f in all_files:
        data = f.to_dict()
        h = data.get('hash', '')
        if not h:
            continue
        if h not in hash_map:
            hash_map[h] = []
        hash_map[h].append({
            'id':   f.id,
            'name': data['name'],
            'path': data['path']
        })

    # Return only groups that have more than one file
    return [group for group in hash_map.values() if len(group) > 1]


@app.get("/duplicates", response_class=HTMLResponse)
async def duplicates(request: Request):
    # Displays all duplicate files across the user's entire Dropbox.
    id_token = request.cookies.get("token")
    user_token = None
    duplicate_groups = []

    if id_token:
        try:
            user_token = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter
            )
            duplicate_groups = get_all_duplicates(user_token['user_id'])
        except ValueError as err:
            print(str(err))

    return templates.TemplateResponse(
        request=request,
        name='duplicates.html',
        context={
            'user_token':       user_token,
            'duplicate_groups': duplicate_groups
        }
    )