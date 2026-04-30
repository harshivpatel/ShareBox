from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import google.oauth2.id_token
from google.auth.transport import requests
from google.cloud import firestore, storage
import local_constants

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
    # Fetches all files owned by the user in the current path.
    files = db.collection('files').where(
        'owner', '==', user_id
    ).where(
        'path', '==', current_path
    ).get()
    return [{'id': f.id, 'name': f.to_dict()['name']} for f in files]


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
    # Uses doc ID to prevent deleting the wrong directory.
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

    dir_doc = db.collection('directories').document(dir_id).get()
    if dir_doc.exists and dir_doc.to_dict().get('path') == '/' and dir_doc.to_dict().get('name') == 'root':
        return RedirectResponse('/', status_code=302)

    db.collection('directories').document(dir_id).delete()

    response = RedirectResponse('/', status_code=302)
    response.set_cookie("current_path", request.cookies.get("current_path", "/"))
    return response


@app.post("/upload-file", response_class=RedirectResponse)
async def upload_file(request: Request, file: UploadFile = File(...)):
    # Uploads a file to GCS and creates a File document in Firestore.
    # Checks for duplicate filename in current directory before uploading.
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

    # Check if file already exists in this directory
    existing = db.collection('files').where(
        'owner', '==', user_token['user_id']
    ).where(
        'path', '==', current_path
    ).where(
        'name', '==', file.filename
    ).get()

    if len(existing) > 0:
        # File exists — for now redirect back, Group 3 will add overwrite confirmation
        response = RedirectResponse('/', status_code=302)
        response.set_cookie("current_path", current_path)
        return response

    # Upload to GCS
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.bucket(local_constants.CLOUD_STORAGE_BUCKET)
    blob_path = user_token['user_id'] + current_path + "/" + file.filename
    blob = bucket.blob(blob_path)
    blob.upload_from_file(file.file, content_type=file.content_type)

    # Save file document to Firestore
    db.collection('files').add({
        'name':     file.filename,
        'path':     current_path,
        'owner':    user_token['user_id'],
        'blob_path': blob_path
    })

    response = RedirectResponse('/', status_code=302)
    response.set_cookie("current_path", current_path)
    return response