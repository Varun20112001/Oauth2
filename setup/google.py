import re, logging, json, base64, os
from google.oauth2 import service_account
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
from typing import List, Optional, Dict, Any, Union
from .oauth_adapter import CloudStorageAdapter
logger = logging.getLogger(__name__)
# Load environment variables from .env file
load_dotenv()

class GDriveConnectorService(CloudStorageAdapter):
    def __init__(self, folder_service: FolderService):
        self.credentials_path = json.loads(os.getenv('GOOGLE_OAUTH_CREDS'))
        self.service_credentials_json = json.loads(os.getenv('GOOGLE_SERVICE_ACCOUNT_CREDS'))
        self.client_id = self.credentials_path['web']['client_id']
        self.client_secret = self.credentials_path['web']['client_secret']
        self.redirect_uri = os.getenv('GDRIVE_REDIRECT_URI')
        self.scopes = ['https://www.googleapis.com/auth/drive.readonly']
        self.folder_service = folder_service

    def get_auth_url(self, **kwargs) -> str:
        # Encode the custom data as base64 JSON
        custom_data = kwargs
        encoded_state = base64.b64encode(
            json.dumps(custom_data).encode()
        ).decode()

        flow = Flow.from_client_config(
            self.credentials_path,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=encoded_state
        )
        return auth_url

    def handle_callback(self, code, state):
        flow = Flow.from_client_config(
            self.credentials_path,
            scopes=self.scopes,
            state=state,
            redirect_uri=self.redirect_uri
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        return {
            'access_token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri
        }

    def get_tree(self, token_info, folder_id='root'):
        creds = Credentials(
            token_info['access_token'],
            refresh_token=token_info.get('refresh_token'),
            token_uri=token_info['token_uri'],
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.scopes
        )
        service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        
        # Fetch only one level - direct children of the specified folder
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, mimeType)"
        ).execute()
        items = results.get('files', [])
        tree = []
        for item in items:
            node = {
                'id': item['id'],
                'name': item['name'],
                'type': 'folder' if item['mimeType'] == 'application/vnd.google-apps.folder' else 'file',
                'file_type': item['mimeType']
            }
            # Don't fetch nested children - only indicate if it's a folder
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                node['has_children'] = True  # Indicate that this folder has children but don't fetch them
            tree.append(node)
        return tree
    
    def list_public_folder(self, folder_id_or_link, folder_id: str = 'root'):
        # Accepts either a folder link or ID
        folder_id = self.extract_folder_id(folder_id_or_link) if folder_id == 'root' else folder_id
        creds = service_account.Credentials.from_service_account_info(
            self.service_credentials_json, scopes=self.scopes
        )
        service = build('drive', 'v3', credentials=creds)
        
        # Fetch only one level - direct children of the specified folder
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, mimeType)"
        ).execute()
        items = results.get('files', [])
        tree = []
        for item in items:
            node = {
                'id': item['id'],
                'name': item['name'],
                'type': 'folder' if item['mimeType'] == 'application/vnd.google-apps.folder' else 'file',
                'file_type': item['mimeType']
            }
            # Don't fetch nested children - only indicate if it's a folder
            if item['mimeType'] == 'application/vnd.google-apps.folder':
                node['has_children'] = True  # Indicate that this folder has children but don't fetch them
            tree.append(node)
        return tree

    def extract_folder_id(self, link_or_id):
        """
        Extracts the folder ID from a Google Drive folder link or returns the ID if already provided.
        """
        patterns = [
            r'drive.google.com/drive/folders/([a-zA-Z0-9_-]+)',
            r'drive.google.com/open\?id=([a-zA-Z0-9_-]+)',
            r'id=([a-zA-Z0-9_-]+)'
        ]
        for pattern in patterns:
            match = re.search(pattern, link_or_id)
            if match:
                return match.group(1)
        return link_or_id.strip()  
    
        
    def get_file_metadata(
        self, file_id: str, token_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Returns metadata (like name) for a given file ID from Google Drive.
        """
        if not token_info:
            creds = service_account.Credentials.from_service_account_file(
                self.service_credentials_json, scopes=self.scopes
            )
        else:
            creds = Credentials(
                token_info['access_token'],
                refresh_token=token_info.get('refresh_token'),
                token_uri=token_info['token_uri'],
                client_id=token_info['client_id'],
                client_secret=token_info['client_secret'],
                scopes=token_info['scopes']
            )
        service = build('drive', 'v3', credentials=creds)
        try:
            file_metadata = service.files().get(fileId=file_id, fields="id, name, mimeType").execute()
            return {
                'id': file_metadata.get('id'),
                'name': file_metadata.get('name'),
                'mimeType': file_metadata.get('mimeType')
            }
        except Exception as e:
            raise Exception(f"Failed to fetch file metadata: {str(e)}")
    

