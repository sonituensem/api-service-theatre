"""Browsable API viewsets for theatre catalogue resources."""

from django.utils.dateparse import parse_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from theatre.models import Actor, Genre, Performance, Play, Reservation, TheatreHall
from theatre.permissions import IsAdminOrReadOnly
from theatre.serializers import (
    ActorSerializer,
    AvailableSeatsSerializer,
    GenreSerializer,
    PerformanceSerializer,
    PlaySerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
    TheatreHallSerializer,
    UserRegistrationSerializer,
)


def _positive_integer_query_param(request, parameter: str) -> int | None:
    value = request.query_params.get(parameter)
    if value is None:
        return None
    try:
        parsed_value = int(value)
    except ValueError as exc:
        raise ValidationError({parameter: "A valid integer is required."}) from exc
    if parsed_value < 1:
        raise ValidationError({parameter: "Ensure this value is greater than 0."})
    return parsed_value


class ActorViewSet(viewsets.ModelViewSet):
    queryset = Actor.objects.all()
    serializer_class = ActorSerializer
    permission_classes = (IsAdminOrReadOnly,)
    search_fields = ("first_name", "last_name")
    ordering_fields = ("first_name", "last_name")


class GenreViewSet(viewsets.ModelViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    permission_classes = (IsAdminOrReadOnly,)
    search_fields = ("name",)
    ordering_fields = ("name",)


class PlayViewSet(viewsets.ModelViewSet):
    queryset = Play.objects.prefetch_related("actors", "genres")
    serializer_class = PlaySerializer
    permission_classes = (IsAdminOrReadOnly,)
    search_fields = ("title", "description")
    ordering_fields = ("title",)

    @extend_schema(
        parameters=[
            OpenApiParameter("genre", int, description="Filter by genre ID."),
            OpenApiParameter("actor", int, description="Filter by actor ID."),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        genre_id = _positive_integer_query_param(self.request, "genre")
        actor_id = _positive_integer_query_param(self.request, "actor")
        if genre_id:
            queryset = queryset.filter(genres__id=genre_id)
        if actor_id:
            queryset = queryset.filter(actors__id=actor_id)
        return queryset.distinct()


class TheatreHallViewSet(viewsets.ModelViewSet):
    queryset = TheatreHall.objects.all()
    serializer_class = TheatreHallSerializer
    permission_classes = (IsAdminOrReadOnly,)
    search_fields = ("name",)
    ordering_fields = ("name", "rows", "seats_in_row")


class PerformanceViewSet(viewsets.ModelViewSet):
    queryset = Performance.objects.select_related("play", "theatre_hall").prefetch_related(
        "tickets"
    )
    serializer_class = PerformanceSerializer
    permission_classes = (IsAdminOrReadOnly,)
    search_fields = ("play__title", "theatre_hall__name")
    ordering_fields = ("show_time", "play__title")

    @extend_schema(
        parameters=[
            OpenApiParameter("play", int, description="Filter by play ID."),
            OpenApiParameter("theatre_hall", int, description="Filter by hall ID."),
            OpenApiParameter(
                "show_time",
                OpenApiTypes.DATE,
                description="Filter by show date in YYYY-MM-DD format.",
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        for query_param, field in (("play", "play_id"), ("theatre_hall", "theatre_hall_id")):
            value = _positive_integer_query_param(self.request, query_param)
            if value is not None:
                queryset = queryset.filter(**{field: value})
        show_time = self.request.query_params.get("show_time")
        if show_time is not None:
            show_date = parse_date(show_time)
            if show_date is None:
                raise ValidationError(
                    {"show_time": "Use an ISO date in YYYY-MM-DD format."}
                )
            queryset = queryset.filter(show_time__date=show_date)
        return queryset

    @action(detail=True, methods=("get",), url_path="available-seats")
    @extend_schema(responses=AvailableSeatsSerializer)
    def available_seats(self, request, pk=None):
        performance = self.get_object()
        hall = performance.theatre_hall
        reserved_seats = set(
            performance.tickets.filter(reservation__isnull=False).values_list(
                "row", "seat"
            )
        )
        seats = [
            {"row": row, "seat": seat}
            for row in range(1, hall.rows + 1)
            for seat in range(1, hall.seats_in_row + 1)
            if (row, seat) not in reserved_seats
        ]
        return Response(
            {"performance": performance.pk, "available_seats": seats},
            status=status.HTTP_200_OK,
        )


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all()
    permission_classes = (IsAuthenticated,)
    http_method_names = ("get", "post", "delete", "head", "options")

    def get_queryset(self):
        return (
            Reservation.objects.filter(user=self.request.user)
            .prefetch_related("tickets__performance__play", "tickets__performance__theatre_hall")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return ReservationCreateSerializer
        return ReservationSerializer


class UserRegistrationView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = UserRegistrationSerializer
