# Example 1: Basic usage with bearer token authentication
from mnh_approval.api_service import ApiService, AuthMethod
from django.conf import settings



def get_patient_data(pid=None, pid_type=None):
    api = ApiService(base_url=settings.EXTERNAL_REFERRAL_API_URL)
    response = api.get(
    endpoint=f"/shr/sharedRecords?idType={pid_type}&id={pid}" if pid is not None or pid_type is None else "/shr/sharedRecords",
        # endpoint=f"/shr/sharedRecords",
    username=settings.EXTERNAL_REFERRAL_API_USERNAME,
    password=settings.EXTERNAL_REFERRAL_API_PASSWORD,
    auth_method=AuthMethod.BASIC_AUTH
    )
    api.close()
    return response.data



# # GET request with bearer token
# response = api.get(
#     endpoint="/users",
#     auth_token="your_jwt_token_here",
#     auth_method=AuthMethod.BEARER_TOKEN,
#     params={"page": 1, "limit": 10}
# )

# if response.success:
#     print("Users:", response.data)
# else:
#     print(f"Error: {response.error}")

# # POST request with JSON data
# response = api.post(
#     endpoint="/users",
#     json_data={"name": "John", "email": "john@example.com"},
#     auth_token="your_jwt_token_here"
# )

# # Example 2: Using basic auth with username/password
# api = ApiService(base_url="https://api.example.com")

# response = api.get(
#     endpoint="/protected-data",
#     username="admin",
#     password="secret",
#     auth_method=AuthMethod.BASIC_AUTH
# )

# # Example 3: Using API key authentication
# api = ApiService(base_url="https://api.example.com")

# response = api.get(
#     endpoint="/data",
#     api_key="your-api-key-here",
#     auth_method=AuthMethod.API_KEY
# )

# # Example 4: PUT request
# response = api.put(
#     endpoint="/users/123",
#     json_data={"name": "John Updated", "email": "john.updated@example.com"},
#     auth_token="your_jwt_token_here"
# )

# # Example 5: DELETE request
# response = api.delete(
#     endpoint="/users/123",
#     auth_token="your_jwt_token_here"
# )

# # Example 6: File upload
# with open("document.pdf", "rb") as f:
#     files = {"file": ("document.pdf", f, "application/pdf")}
#     response = api.post(
#         endpoint="/upload",
#         files=files,
#         auth_token="your_jwt_token_here"
#     )

# # Example 7: Using context manager (auto-closes session)
# with ApiService(base_url="https://api.example.com") as api:
#     response = api.get(
#         endpoint="/data",
#         auth_token="your_jwt_token_here"
#     )
#     print(response.to_dict())

# # Example 8: Custom headers
# api = ApiService(base_url="https://api.example.com")
# api.add_default_header("X-Custom-Header", "custom-value")

# response = api.get(
#     endpoint="/data",
#     auth_token="your_jwt_token_here",
#     headers={"X-Another-Header": "another-value"}
# )

# # Don't forget to close the session when done
# api.close()