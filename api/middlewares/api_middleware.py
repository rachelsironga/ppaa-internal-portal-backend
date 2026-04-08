from ppaa_portal.response_codes import CustomResponse


class APIMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            # Only do this for API responses (not HTML/template ones)
            if request.path.startswith("/api/") and response.status_code == 403:
                return CustomResponse.forbidden(
                    message="You don’t have permission to access this resource.",
                )
        except Exception:
            # fallback for unrendered template responses
            pass

        return response
