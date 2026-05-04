from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .models import Maoni, MaoniComment, MaoniCategory
from .serializers import MaoniSerializer, MaoniCommentSerializer, MaoniCategorySerializer
from ppaa_portal.pagination import CustomPagination
from ppaa_portal.response_codes import CustomResponse, STATUS_CODES
from ppaa_auth.models import User
from utils.permissions import HasMethodPermission
from rest_framework.pagination import PageNumberPagination


def is_hr_user(user):
    """Check if user has HR role"""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    group_names = user.get_group_names()
    return any('hr' in name.lower() for name in group_names)


class SuggestionView(APIView):
    """API view for creating and listing suggestions"""
    permission_classes = [IsAuthenticated]
    serializer_class = MaoniSerializer

    def get(self, request):
        """List suggestions - users see their own, HR sees all.
        Includes both SUBMITTED and DRAFT so drafts are visible/editable on frontend."""
        try:
            if is_hr_user(request.user):
                # HR can see all suggestions (submitted and drafts)
                suggestions = Maoni.objects.filter(
                    is_deleted=False,
                    status__in=['SUBMITTED', 'DRAFT']
                ).order_by('-submitted_at', '-created_at')
            else:
                # Regular users see only their own suggestions (submitted and drafts)
                suggestions = Maoni.objects.filter(
                    is_deleted=False,
                    submitted_by_id=request.user.id,
                    status__in=['SUBMITTED', 'DRAFT']
                ).order_by('-submitted_at', '-created_at')

            # Use CustomPagination.paginate method
            return CustomPagination.paginate(view_class=self, results=suggestions, request=request)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve suggestions: {str(e)}")

    def post(self, request):
        """Create a new suggestion"""
        try:
            with transaction.atomic():
                serializer = self.serializer_class(
                    data=request.data,
                    context={'request': request}
                )
                if serializer.is_valid():
                    suggestion = serializer.save()
                    return CustomResponse.success(
                        message="Suggestion submitted successfully",
                        data=serializer.data
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to create suggestion: {str(e)}")


class SuggestionDetailView(APIView):
    """API view for retrieving a single suggestion with replies"""
    permission_classes = [IsAuthenticated]
    serializer_class = MaoniSerializer

    def get(self, request, uid):
        """Get suggestion detail with all replies"""
        try:
            suggestion = Maoni.objects.filter(uid=uid, is_deleted=False).first()
            if not suggestion:
                return CustomResponse.errors(
                    message="Suggestion not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            # Check access: users can only see their own, HR can see all
            if not is_hr_user(request.user):
                if suggestion.submitted_by_id != request.user.id:
                    return CustomResponse.forbidden(
                        message="You don't have permission to view this suggestion"
                    )

            serializer = self.serializer_class(suggestion)
            return CustomResponse.success(data=serializer.data)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve suggestion: {str(e)}")

    def put(self, request, uid):
        """Update an existing suggestion (only for drafts or by owner/HR)"""
        try:
            with transaction.atomic():
                suggestion = Maoni.objects.filter(uid=uid, is_deleted=False).first()
                if not suggestion:
                    return CustomResponse.errors(
                        message="Suggestion not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )

                # Check access: users can only update their own drafts, HR can update any
                if not is_hr_user(request.user):
                    if suggestion.submitted_by_id != request.user.id:
                        return CustomResponse.forbidden(
                            message="You don't have permission to update this suggestion"
                        )
                    # Regular users can only update drafts
                    if suggestion.status != 'DRAFT':
                        return CustomResponse.forbidden(
                            message="You can only edit draft suggestions. Submitted suggestions cannot be edited."
                        )

                serializer = self.serializer_class(
                    suggestion,
                    data=request.data,
                    context={'request': request},
                    partial=True  # Allow partial updates
                )
                if serializer.is_valid():
                    updated_suggestion = serializer.save()
                    return CustomResponse.success(
                        message="Suggestion updated successfully",
                        data=serializer.data
                    )
                return CustomResponse.errors(
                    message="Validation failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to update suggestion: {str(e)}")


class SuggestionReplyView(APIView):
    """API view for replying to suggestions"""
    permission_classes = [IsAuthenticated]
    serializer_class = MaoniCommentSerializer

    def post(self, request, uid):
        """Reply to a suggestion or another reply"""
        try:
            with transaction.atomic():
                suggestion = Maoni.objects.filter(uid=uid, is_deleted=False).first()
                if not suggestion:
                    return CustomResponse.errors(
                        message="Suggestion not found",
                        code=STATUS_CODES["DATA_NOT_FOUND"]
                    )

                # Check access: users can only reply to their own suggestions, HR can reply to any
                if not is_hr_user(request.user):
                    if suggestion.submitted_by_id != request.user.id:
                        return CustomResponse.forbidden(
                            message="You can only reply to your own suggestions"
                        )

                # Check if replying to another comment
                parent_comment_uid = request.data.get('parent_comment_uid')
                parent_comment = None
                if parent_comment_uid:
                    parent_comment = MaoniComment.objects.filter(
                        uid=parent_comment_uid,
                        maoni=suggestion,
                        is_deleted=False
                    ).first()
                    if not parent_comment:
                        return CustomResponse.errors(
                            message="Parent comment not found",
                            code=STATUS_CODES["DATA_NOT_FOUND"]
                        )

                # Create reply directly
                reply = MaoniComment.objects.create(
                    maoni=suggestion,
                    comment=request.data.get('comment', ''),
                    commented_by_id=request.user.id,
                    parent_comment=parent_comment,
                    is_internal=False,
                )
                
                # Update comment count
                suggestion.comment_count = MaoniComment.objects.filter(
                    maoni=suggestion,
                    is_deleted=False
                ).count()
                suggestion.save(update_fields=['comment_count'])

                serializer = self.serializer_class(reply)
                return CustomResponse.success(
                    message="Reply sent successfully",
                    data=serializer.data
                )
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to send reply: {str(e)}")


class SuggestionPrintView(APIView):
    """API view for printing suggestions - HR only"""
    permission_classes = [IsAuthenticated]
    serializer_class = MaoniSerializer

    def get(self, request, uid):
        """Get suggestion data formatted for printing"""
        try:
            # Only HR can print
            if not is_hr_user(request.user):
                return CustomResponse.forbidden(
                    message="Only HR users can print suggestions"
                )

            suggestion = Maoni.objects.filter(uid=uid, is_deleted=False).first()
            if not suggestion:
                return CustomResponse.errors(
                    message="Suggestion not found",
                    code=STATUS_CODES["DATA_NOT_FOUND"]
                )

            # Get all comments (replies) in a flat structure for printing
            all_comments = MaoniComment.objects.filter(
                maoni=suggestion,
                is_deleted=False
            ).order_by('created_at')
            
            serializer = self.serializer_class(suggestion)
            data = serializer.data
            
            # Add all comments in chronological order for printing
            data['all_comments'] = MaoniCommentSerializer(all_comments, many=True).data
            
            return CustomResponse.success(data=data)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve suggestion for printing: {str(e)}")


class MaoniCategoryView(APIView):
    """API view for fetching categories (area of concern)"""
    permission_classes = [IsAuthenticated]
    serializer_class = MaoniCategorySerializer

    def get(self, request):
        """Get all public categories"""
        try:
            categories = MaoniCategory.objects.filter(
                is_deleted=False,
                is_public=True,
                is_active=True
            ).order_by('order', 'name')
            serializer = self.serializer_class(categories, many=True)
            return CustomResponse.success(data=serializer.data)
        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to retrieve categories: {str(e)}")


