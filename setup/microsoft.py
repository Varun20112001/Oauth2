import re, logging, json, base64, os
import msal
import requests
from dotenv import load_dotenv
from typing import List, Optional, Dict, Any, Union
from .oauth_adapter import CloudStorageAdapter
load_dotenv()

class OneDriveConnectorService(CloudStorageAdapter):
    def __init__(self, folder_service: FolderService):
        self.folder_service = folder_service
        self.application_id = os.getenv("AZURE_CLIENT_ID")
        self.client_secret = os.getenv("AZURE_CLIENT_SECRET")
        self.redirect_uri = os.getenv('ONEDRIVE_REDIRECT_URI')
        self.scopes = ['Files.Read.All','User.Read']
        if self.application_id and self.client_secret:
            self.msal_client = msal.ConfidentialClientApplication(
                client_id=self.application_id,
                client_credential=self.client_secret,
                authority="https://login.microsoftonline.com/common"
            )

    def get_auth_url(self, **kwargs) -> str:
        """Get the Microsoft login URL for OAuth2 authentication."""
        custom_data = kwargs
        encoded_state = base64.b64encode(
            json.dumps(custom_data).encode()
        ).decode()
        auth_request_url = self.msal_client.get_authorization_request_url(
            self.scopes, state=encoded_state
        )
        return auth_request_url

    def handle_callback(self, code: str, state: Optional[str] = None):
        """Exchange authorization code for access token."""
        tokens = self.msal_client.acquire_token_by_authorization_code(
            scopes=self.scopes, code=code
        )
        if tokens.get("error"):
            raise ValueError("Error getting access token.")
        data={
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in"),
            "token_type": tokens.get("token_type")
        }
        return data

    def get_formated_drive_tree(self, resp):
        """
        Accepts OneDrive API response (dict with 'value' key) and returns tree format like demo.json.
        Returns single level only with has_children indicator for folders.
        """
        if isinstance(resp, dict) and 'value' in resp:
            items = resp['value']
        elif isinstance(resp, list):
            items = resp
        else:
            items = []
        
        # Build single-level tree structure
        result = []
        for item in items:
            node = {
                'id': item['id'],
                'name': item['name'],
                'type': 'folder' if 'folder' in item else 'file',
            }
            if 'file' in item:
                node['file_type'] = item['file'].get('mimeType', None)
            if 'folder' in item:
                # For folders, add has_children indicator instead of recursive children
                node['has_children'] = item.get('folder', {}).get('childCount', 0) > 0
            result.append(node)
        
        return result
    
    def get_tree(self, token_info: Dict[str, Any], folder_id: str = 'root'):
        access_token = token_info.get('access_token')
        headers = {'Authorization': f'Bearer {access_token}'}
        resp = requests.get(f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}/children', headers=headers)
        return self.get_formated_drive_tree(resp.json())

    def list_public_folder(self, folder_link_or_id: str, folder_id: str = 'root') -> Dict[str, Any]:
        """
        Lists contents of a public folder given its link or ID.
        """
        pass
        # folder_id = self.extract_folder_id(folder_link_or_id)
        # if not folder_id:
        #     raise ValueError("Invalid OneDrive folder link or ID.")
        # # For public folders, we might not need an access token, but OneDrive API typically requires it.
        # # Here, we assume the folder is shared and accessible via a special link.
        # # In practice, you might need to handle this differently based on your requirements.
        # headers = {}
        # resp = requests.get(
        #     f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}/children',
        #     headers=headers
        # )
        # if resp.status_code != 200:
        #     raise Exception(f"Failed to fetch folder contents: {resp.text}")
        # return self.get_formated_drive_tree(resp.json())
    
    def get_download_link(self, access_token, file_id) -> Optional[str]:
        """
        Returns the direct download link for a file given its file_id.
        """
        headers = {'Authorization': f'Bearer {access_token}'}
        url = f'https://graph.microsoft.com/v1.0/me/drive/items/{file_id}?select=@microsoft.graph.downloadUrl'
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            return data.get('@microsoft.graph.downloadUrl')
        return None

    def download_file_in_memory(self, access_token, file_id):
        """
        Downloads a file from OneDrive into memory using file_id and access_token.
        Returns (filename, BytesIO object).
        """
        import io
        headers = {'Authorization': f'Bearer {access_token}'}
        # Get file metadata for filename
        meta_url = f'https://graph.microsoft.com/v1.0/me/drive/items/{file_id}'
        meta_resp = requests.get(meta_url, headers=headers)
        meta_resp.raise_for_status()
        meta = meta_resp.json()
        filename = meta.get('name', f'{file_id}.bin')
        # Get download URL
        download_url = meta.get('@microsoft.graph.downloadUrl')
        if not download_url:
            # Try to fetch download URL if not present
            url = f'https://graph.microsoft.com/v1.0/me/drive/items/{file_id}?select=@microsoft.graph.downloadUrl'
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            download_url = resp.json().get('@microsoft.graph.downloadUrl')
        if not download_url:
            raise Exception('Could not retrieve download URL')
        # Download file content
        file_resp = requests.get(download_url)
        file_resp.raise_for_status()
        file_bytes = io.BytesIO(file_resp.content)
        file_bytes.seek(0)
        return filename, file_bytes

    def get_file_metadata(self, file_id: str, token_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns metadata (like name) for a given file ID
        """
        access_token = token_info.get('access_token')
        if not access_token:
            raise Exception("Access token not found in token_info")
        headers = {'Authorization': f'Bearer {access_token}'}
        url = f'https://graph.microsoft.com/v1.0/me/drive/items/{file_id}'
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            raise Exception(f"Failed to fetch file metadata: {resp.text}")
        return resp.json()