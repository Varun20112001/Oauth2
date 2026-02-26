from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union


class CloudStorageAdapter(ABC):
    """
    Abstract base class defining the interface for all cloud storage adapters.
    """
    @abstractmethod
    def get_auth_url(self, **kwargs) -> str:
        """Returns the authentication URL for OAuth flow"""
        pass

    @abstractmethod
    def handle_callback(self, code: str, state: Optional[str] = None) -> Dict[str, Any]:
        """Handles the OAuth callback and returns token info"""
        pass

    @abstractmethod
    def get_tree(self, token_info: Dict[str, Any], folder_id: str = 'root') -> List[Dict[str, Any]]:
        """Returns a tree structure of files and folders"""
        pass

    @abstractmethod
    def list_public_folder(self, folder_link_or_id: str, folder_id: str = 'root') -> Dict[str, Any]:
        """Lists contents of a public folder given its link or ID"""
        pass

    @abstractmethod
    def get_file_metadata(self, file_id: str, token_info: Dict[str, Any]) -> Dict[str, Any]:
        """Returns metadata (like name) for a given file ID"""
        pass

    @abstractmethod
    def submit_download_task(
        self, org_id: str, created_by: str, files: Dict[str,str], folders: Dict[str,str],
        parent_folder_id: Optional[str], token_info: Dict[str, Any], method:str
    ) -> List[Dict[str, Any]]:
        """Downloads files from cloud storage and saves them to org vault"""
        pass
