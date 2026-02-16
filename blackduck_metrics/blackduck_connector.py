"""
Black Duck SCA connection handler using HubRestApi.

This module provides functionality to connect to Black Duck SCA
and interact with its REST API.
"""

import os
import requests
from typing import Optional, Dict, Any
from blackduck.HubRestApi import HubInstance

MAX_LIMIT=1000  # Maximum items per page for API requests

class BlackDuckConnector:
    """
    Manages connection to Black Duck SCA server.
    
    Attributes:
        hub_instance: The connected HubInstance object
        base_url: Black Duck server base URL
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        insecure: bool = False,
        timeout: int = 15
    ):
        """
        Initialize Black Duck connector.
        
        Args:
            base_url: Black Duck server URL (or use BD_URL env var)
            api_token: API token for authentication (or use BD_API_TOKEN env var)
            username: Username for authentication (or use BD_USERNAME env var)
            password: Password for authentication (or use BD_PASSWORD env var)
            insecure: If True, disable SSL verification
            timeout: Request timeout in seconds
        
        Note:
            Authentication priority:
            1. API token (recommended)
            2. Username/password
            Environment variables will be used if parameters are not provided.
        """
        self.base_url = base_url or os.getenv('BD_URL')
        self.api_token = api_token or os.getenv('BD_API_TOKEN')
        self.username = username or os.getenv('BD_USERNAME')
        self.password = password or os.getenv('BD_PASSWORD')
        self.insecure = insecure
        self.timeout = timeout
        self.hub_instance = None
        
        if not self.base_url:
            raise ValueError(
                "Black Duck URL must be provided either as parameter or BD_URL environment variable"
            )
        else:
            # Ensure base_url does not end with a slash
            self.base_url = self.base_url.rstrip('/')
        self.hub_instance = self.connect() 
    
    def connect(self) -> HubInstance:
        """
        Establish connection to Black Duck server.
        
        Returns:
            HubInstance: Connected hub instance
            
        Raises:
            ValueError: If authentication credentials are missing
            Exception: If connection fails
        """
        if self.hub_instance:
            return self.hub_instance
        
        try:
            if self.api_token:
                # Authenticate using API token (recommended)
                self.hub_instance = HubInstance(
                    self.base_url,
                    api_token=self.api_token,
                    insecure=self.insecure,
                    timeout=self.timeout
                )
            elif self.username and self.password:
                # Authenticate using username/password
                self.hub_instance = HubInstance(
                    self.base_url,
                    username=self.username,
                    password=self.password,
                    insecure=self.insecure,
                    timeout=self.timeout
                )
            else:
                raise ValueError(
                    "Authentication credentials required: provide either "
                    "api_token or username/password"
                )
            
            print(f"Successfully connected to Black Duck at {self.base_url}")
            return self.hub_instance
            
        except Exception as e:
            raise Exception(f"Failed to connect to Black Duck: {str(e)}")
    
    
    def get_project_group_projects(self, project_group_name: str) -> Dict[str, Any]:
        try:
            projects = {"totalCount": 0, "items": []}
            url = f'{self.hub_instance.get_urlbase()}/api/project-groups'
            headers = self.hub_instance.get_headers()
            headers['Accept'] = 'application/vnd.blackducksoftware.project-detail-5+json'
            parameters={"q":f'name:{project_group_name}'}
            response = requests.get(url, headers=headers, params=parameters, verify = not self.hub_instance.config['insecure'])
            if response.status_code == 200:
                jsondata = response.json()
                if "totalCount" in jsondata and int(jsondata["totalCount"]) > 0:
                    for projectGroup in jsondata["items"]:
                        self.__get_project_groups_children_projects(projectGroup, projects, headers)
            return projects
        except Exception as e:
            print(f"Error fetching project groups: {str(e)}")

    def __get_project_groups_children_projects(self, projectGroup, projects, headers) -> None:
        parameters={"limit": MAX_LIMIT}
        response = requests.get(projectGroup['_meta']['href']+"/children", headers=headers, params=parameters, verify = not self.hub_instance.config['insecure'])
        if response.status_code == 200:
            childrens = response.json()
            if "totalCount" in childrens and int(childrens["totalCount"]) > MAX_LIMIT:
                downloaded = MAX_LIMIT
                while int(childrens["totalCount"]) > downloaded:
                    parameters={"offset": downloaded, "limit": MAX_LIMIT}
                    moreProjects = requests.get(projectGroup['_meta']['href']+"/children", headers=headers, params=parameters, verify = not self.hub_instance.config['insecure'])
                    childrens["items"] = childrens["items"] + moreProjects.json()["items"]
                    downloaded += MAX_LIMIT
            if "totalCount" in childrens and int(childrens["totalCount"]) > 0:
                for children in childrens["items"]:
                    if "isProject" in children and children["isProject"] is False:
                        self.__get_project_groups_children_projects(children, projects, headers)
                    else:
                        #This phase there will always be one project, so no need for limits
                        project_response = requests.get(children['_meta']['href'], headers=headers, verify = not self.hub_instance.config['insecure'])
                        if project_response.status_code == 200:
                            children_projects = project_response.json()
                            if children_projects:
                                projectList = [children_projects]
                                projects["totalCount"] = int(projects["totalCount"]) + 1
                                projects["items"] = projects["items"] + projectList
    def disconnect(self):
        """
        Clean up connection resources.
        """
        self.hub_instance = None
        print("Disconnected from Black Duck")