"""Custom permissions for theatre API resources."""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminOrReadOnly(BasePermission):
    """Allow public reads and restrict catalogue writes to staff users."""

    def has_permission(self, request, view) -> bool:
        return request.method in SAFE_METHODS or bool(
            request.user and request.user.is_staff
        )
