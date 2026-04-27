import requests
import json
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass
from enum import Enum
import base64


class AuthMethod(Enum):
    """Authentication methods supported by the API service"""
    BEARER_TOKEN = "bearer_token"
    BASIC_AUTH = "basic_auth"
    API_KEY = "api_key"
    CUSTOM_HEADER = "custom_header"


@dataclass
class ApiResponse:
    """Global response structure for all API calls"""
    success: bool
    data: Optional[Any] = None
    status_code: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None
    headers: Optional[Dict[str, Any]] = None
    raw_response: Optional[requests.Response] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary"""
        return {
            "success": self.success,
            "data": self.data,
            "status_code": self.status_code,
            "message": self.message,
            "error": self.error,
            "headers": dict(self.headers) if self.headers else None
        }


class ApiService:
    """
    Comprehensive API service with HTTP methods and multiple authentication options
    """
    
    def __init__(
        self,
        base_url: str = "",
        timeout: int = 30,
        verify_ssl: bool = True,
        default_headers: Optional[Dict[str, str]] = None
    ):
        """
        Initialize API Service
        
        Args:
            base_url: Base URL for all API requests
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
            default_headers: Default headers for all requests
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.default_headers = default_headers or {}
        self.session = requests.Session()
        
        # Configure default headers
        if "Content-Type" not in self.default_headers:
            self.default_headers["Content-Type"] = "application/json"
        if "Accept" not in self.default_headers:
            self.default_headers["Accept"] = "application/json"
    
    def _prepare_headers(
        self,
        custom_headers: Optional[Dict[str, str]] = None,
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_method: AuthMethod = AuthMethod.BEARER_TOKEN,
        api_key: Optional[str] = None,
        api_key_header: str = "X-API-Key"
    ) -> Dict[str, str]:
        """
        Prepare headers with authentication
        
        Args:
            custom_headers: Custom headers to add
            auth_token: Authorization token (for bearer token auth)
            username: Username (for basic auth)
            password: Password (for basic auth)
            auth_method: Authentication method to use
            api_key: API key (for API key auth)
            api_key_header: Header name for API key
            
        Returns:
            Dictionary of headers
        """
        headers = self.default_headers.copy()
        
        if custom_headers:
            headers.update(custom_headers)
        
        # Add authentication headers based on method
        if auth_method == AuthMethod.BEARER_TOKEN and auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        elif auth_method == AuthMethod.BASIC_AUTH and username and password:
            # Create Basic Auth header
            credentials = f"{username}:{password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded_credentials}"
        
        elif auth_method == AuthMethod.API_KEY and api_key:
            headers[api_key_header] = api_key
        
        elif auth_method == AuthMethod.CUSTOM_HEADER and auth_token:
            # For custom header auth, assume auth_token contains the full header value
            # Format should be like "Header-Name: header-value"
            if ':' in auth_token:
                header_name, header_value = auth_token.split(':', 1)
                headers[header_name.strip()] = header_value.strip()
        
        return headers
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ApiResponse:
        """
        Make HTTP request and return standardized response
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint (relative to base_url)
            data: Form data
            params: Query parameters
            json_data: JSON data for request body
            files: Files to upload
            **kwargs: Additional arguments for requests.request()
            
        Returns:
            ApiResponse object
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}" if self.base_url else endpoint


        print("================= Making request to =============== ", url)
        
        try:
            # Prepare request data
            if json_data and not files:
                kwargs['json'] = json_data
            elif data:
                kwargs['data'] = data
            
            if params:
                kwargs['params'] = params
            
            if files:
                kwargs['files'] = files
            
            # Make the request
            response = self.session.request(
                method=method.upper(),
                url=url,
                timeout=self.timeout,
                verify=self.verify_ssl,
                **kwargs
            )

            print("Response status code: ", response)
            
            # Parse response
            try:
                response_data = response.json() if response.content else None
            except json.JSONDecodeError:
                response_data = response.text
            
            # Determine if request was successful
            is_success = 200 <= response.status_code < 300
            
            return ApiResponse(
                success=is_success,
                data=response_data,
                status_code=response.status_code,
                message=f"Request {'successful' if is_success else 'failed'}",
                error=None if is_success else response_data,
                headers=dict(response.headers),
                raw_response=response
            )
            
        except requests.exceptions.Timeout:
            return ApiResponse(
                success=False,
                status_code=408,
                message="Request timeout",
                error="Request timed out"
            )
            
        except requests.exceptions.ConnectionError:
            return ApiResponse(
                success=False,
                status_code=503,
                message="Connection error",
                error="Unable to connect to server"
            )
            
        except requests.exceptions.RequestException as e:
            return ApiResponse(
                success=False,
                message="Request failed",
                error=str(e)
            )
            
        except Exception as e:
            return ApiResponse(
                success=False,
                message="Unexpected error",
                error=str(e)
            )
    
    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_method: AuthMethod = AuthMethod.BEARER_TOKEN,
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ApiResponse:
        """
        Make GET request
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            auth_token: Authentication token
            username: Username for basic auth
            password: Password for basic auth
            auth_method: Authentication method
            api_key: API key for API key auth
            headers: Additional headers
            **kwargs: Additional arguments for requests
            
        Returns:
            ApiResponse object
        """
        request_headers = self._prepare_headers(
            custom_headers=headers,
            auth_token=auth_token,
            username=username,
            password=password,
            auth_method=auth_method,
            api_key=api_key
        )

        print("====== REQUEST HEADER=====> ", request_headers)
        
        return self._make_request(
            method="GET",
            endpoint=endpoint,
            params=params,
            headers=request_headers,
            **kwargs
        )
    
    def post(
        self,
        endpoint: str,
        data: Optional[Any] = None,
        json_data: Optional[Dict[str, Any]] = None,
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_method: AuthMethod = AuthMethod.BEARER_TOKEN,
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        files: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> ApiResponse:
        """
        Make POST request
        
        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            auth_token: Authentication token
            username: Username for basic auth
            password: Password for basic auth
            auth_method: Authentication method
            api_key: API key for API key auth
            headers: Additional headers
            files: Files to upload
            **kwargs: Additional arguments for requests
            
        Returns:
            ApiResponse object
        """
        request_headers = self._prepare_headers(
            custom_headers=headers,
            auth_token=auth_token,
            username=username,
            password=password,
            auth_method=auth_method,
            api_key=api_key
        )
        
        # Remove Content-Type header if uploading files
        if files and "Content-Type" in request_headers:
            del request_headers["Content-Type"]
        
        return self._make_request(
            method="POST",
            endpoint=endpoint,
            data=data,
            json_data=json_data,
            headers=request_headers,
            files=files,
            **kwargs
        )
    
    def put(
        self,
        endpoint: str,
        data: Optional[Any] = None,
        json_data: Optional[Dict[str, Any]] = None,
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_method: AuthMethod = AuthMethod.BEARER_TOKEN,
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ApiResponse:
        """
        Make PUT request
        
        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            auth_token: Authentication token
            username: Username for basic auth
            password: Password for basic auth
            auth_method: Authentication method
            api_key: API key for API key auth
            headers: Additional headers
            **kwargs: Additional arguments for requests
            
        Returns:
            ApiResponse object
        """
        request_headers = self._prepare_headers(
            custom_headers=headers,
            auth_token=auth_token,
            username=username,
            password=password,
            auth_method=auth_method,
            api_key=api_key
        )
        
        return self._make_request(
            method="PUT",
            endpoint=endpoint,
            data=data,
            json_data=json_data,
            headers=request_headers,
            **kwargs
        )
    
    def delete(
        self,
        endpoint: str,
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_method: AuthMethod = AuthMethod.BEARER_TOKEN,
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ApiResponse:
        """
        Make DELETE request
        
        Args:
            endpoint: API endpoint
            auth_token: Authentication token
            username: Username for basic auth
            password: Password for basic auth
            auth_method: Authentication method
            api_key: API key for API key auth
            headers: Additional headers
            **kwargs: Additional arguments for requests
            
        Returns:
            ApiResponse object
        """
        request_headers = self._prepare_headers(
            custom_headers=headers,
            auth_token=auth_token,
            username=username,
            password=password,
            auth_method=auth_method,
            api_key=api_key
        )
        
        return self._make_request(
            method="DELETE",
            endpoint=endpoint,
            headers=request_headers,
            **kwargs
        )
    
    def patch(
        self,
        endpoint: str,
        data: Optional[Any] = None,
        json_data: Optional[Dict[str, Any]] = None,
        auth_token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_method: AuthMethod = AuthMethod.BEARER_TOKEN,
        api_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> ApiResponse:
        """
        Make PATCH request
        
        Args:
            endpoint: API endpoint
            data: Form data
            json_data: JSON data
            auth_token: Authentication token
            username: Username for basic auth
            password: Password for basic auth
            auth_method: Authentication method
            api_key: API key for API key auth
            headers: Additional headers
            **kwargs: Additional arguments for requests
            
        Returns:
            ApiResponse object
        """
        request_headers = self._prepare_headers(
            custom_headers=headers,
            auth_token=auth_token,
            username=username,
            password=password,
            auth_method=auth_method,
            api_key=api_key
        )
        
        return self._make_request(
            method="PATCH",
            endpoint=endpoint,
            data=data,
            json_data=json_data,
            headers=request_headers,
            **kwargs
        )
    
    def set_base_url(self, base_url: str):
        """Set base URL for all requests"""
        self.base_url = base_url.rstrip('/')
    
    def add_default_header(self, key: str, value: str):
        """Add default header"""
        self.default_headers[key] = value
    
    def remove_default_header(self, key: str):
        """Remove default header"""
        if key in self.default_headers:
            del self.default_headers[key]
    
    def clear_default_headers(self):
        """Clear all default headers"""
        self.default_headers.clear()
    
    def close(self):
        """Close the session"""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()