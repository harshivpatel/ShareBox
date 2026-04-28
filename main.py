from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import google.oauth2.id_token
from google.auth.transport import requests
from google.cloud import firestore
import local_constants

app = FastAPI()

# Adapter for verifying Firebase ID tokens
firebase_request_adapter = requests.Request()

# Initialize Firestore client using project name from constants
db = firestore.Client(project=local_constants.PROJECT_NAME)

# Mount static files and initialize templates
app.mount ('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates")


def get_user(user_token):
    # Fetch user document from Firestore using unique user ID
    return db.collection('users').document(user_token['user_id']).get()

def create_user(user_token):
    # Store user email in Firestore
    db.collection('users').document(user_token['user_id']).set({
        'email': user_token['email']
    })

    # Initialize a root directory for new users
    db.collection('directories').add({
        'name': 'root',
        'path': '/',
        'owner': user_token['user_id'],
        'parent': None
    })

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    # Retrieve auth token and current navigation path from cookies
    id_token = request.cookies.get("token")
    error_message = None
    user_token = None
    directories = []
    current_path = request.cookies.get("current_path", "/")

    if id_token:
        try:
            # Verify Firebase token and handle user registration if new
            user_token = google.oauth2.id_token.verify_firebase_token(
                id_token, firebase_request_adapter
            )
            user = get_user(user_token)
            if not user.exists:
                create_user(user_token)

            # Fetch directories belonging to user at current path
            dirs = db.collection('directories').where(
                'owner', '==', user_token['user_id']
            ).where(
                'path', '==', current_path
            ).get()

            directories = [{'id': d.id, 'name': d.to_dict()['name']} for d in dirs]

        except ValueError as err:
            print(str(err))
            error_message = str(err)

    # Render main page with user data and directory list
    return templates.TemplateResponse(
        request=request,
        name='main.html',
        context={
            'user_token':    user_token,
            'error_message': error_message,
            'directories':   directories,
            'current_path':  current_path
        }
    )

@app.post("/create-directory", response_class=RedirectResponse)
async def create_directory(request: Request, dirname: str = Form(...)):
    # Authenticate user via token cookie before allowing creation
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

    # Check if a directory with the same name already exists at this path
    existing = db.collection('directories').where(
        'owner', '==', user_token['user_id']
    ).where(
        'path', '==', current_path
    ).where(
        'name', '==', dirname
    ).get()

    # Add new directory if name is unique
    if len(existing) == 0:
        db.collection('directories').add({
            'name': dirname,
            'path': current_path,
            'owner': user_token['user_id'],
            'parent': current_path
        })

    return RedirectResponse('/', status_code=302)

@app.post("/delete-directory", response_class=RedirectResponse)
async def delete_directory(request: Request, dir_id: str = Form(...)):
    # Authenticate user via token cookie before allowing deletion
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
    
    # Retrieve directory details and block deletion if it is the root folder
    dir_doc = db.collection('directories').document(dir_id).get()
    if dir_doc.exists and dir_doc.to_dict().get('path') == '/' and dir_doc.to_dict().get('name') == 'root':
        return RedirectResponse('/', status_code=302)

    # Delete specified directory from Firestore
    db.collection('directories').document(dir_id).delete()

    return RedirectResponse('/', status_code=302)