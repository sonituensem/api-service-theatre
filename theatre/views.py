"""Browsable API viewsets for theatre catalogue resources."""

from rest_framework import viewsets

from theatre.models import Actor, Genre, Performance, Play, TheatreHall
from theatre.serializers import (
    ActorSerializer,
    GenreSerializer,
    PerformanceSerializer,
    PlaySerializer,
    TheatreHallSerializer,
)


class ActorViewSet(viewsets.ModelViewSet):
    queryset = Actor.objects.all()
    serializer_class = ActorSerializer
    search_fields = ("first_name", "last_name")
    ordering_fields = ("first_name", "last_name")


class GenreViewSet(viewsets.ModelViewSet):
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer
    search_fields = ("name",)
    ordering_fields = ("name",)


class PlayViewSet(viewsets.ModelViewSet):
    queryset = Play.objects.prefetch_related("actors", "genres")
    serializer_class = PlaySerializer
    search_fields = ("title", "description")
    ordering_fields = ("title",)

    def get_queryset(self):
        queryset = super().get_queryset()
        genre_id = self.request.query_params.get("genre")
        actor_id = self.request.query_params.get("actor")
        if genre_id:
            queryset = queryset.filter(genres__id=genre_id)
        if actor_id:
            queryset = queryset.filter(actors__id=actor_id)
        return queryset.distinct()


class TheatreHallViewSet(viewsets.ModelViewSet):
    queryset = TheatreHall.objects.all()
    serializer_class = TheatreHallSerializer
    search_fields = ("name",)
    ordering_fields = ("name", "rows", "seats_in_row")


class PerformanceViewSet(viewsets.ModelViewSet):
    queryset = Performance.objects.select_related("play", "theatre_hall").prefetch_related(
        "tickets"
    )
    serializer_class = PerformanceSerializer
    search_fields = ("play__title", "theatre_hall__name")
    ordering_fields = ("show_time", "play__title")

    def get_queryset(self):
        queryset = super().get_queryset()
        for query_param, field in (
            ("play", "play_id"),
            ("theatre_hall", "theatre_hall_id"),
            ("show_time", "show_time__date"),
        ):
            value = self.request.query_params.get(query_param)
            if value:
                queryset = queryset.filter(**{field: value})
        return queryset

