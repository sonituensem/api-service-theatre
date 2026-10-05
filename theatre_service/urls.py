"""URL configuration for the public catalogue API."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

from theatre.views import (
    ActorViewSet,
    GenreViewSet,
    PerformanceViewSet,
    PlayViewSet,
    TheatreHallViewSet,
)

router = DefaultRouter()
router.register("plays", PlayViewSet)
router.register("actors", ActorViewSet)
router.register("genres", GenreViewSet)
router.register("theatre-halls", TheatreHallViewSet)
router.register("performances", PerformanceViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]

