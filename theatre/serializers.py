"""Serializers for theatre catalogue resources."""

from rest_framework import serializers

from theatre.models import Actor, Genre, Performance, Play, TheatreHall


class ActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Actor
        fields = ("id", "first_name", "last_name")


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ("id", "name")


class PlaySerializer(serializers.ModelSerializer):
    actors_details = ActorSerializer(source="actors", many=True, read_only=True)
    genres_details = GenreSerializer(source="genres", many=True, read_only=True)

    class Meta:
        model = Play
        fields = (
            "id",
            "title",
            "description",
            "actors",
            "actors_details",
            "genres",
            "genres_details",
        )


class TheatreHallSerializer(serializers.ModelSerializer):
    class Meta:
        model = TheatreHall
        fields = ("id", "name", "rows", "seats_in_row")


class PerformanceSerializer(serializers.ModelSerializer):
    play_title = serializers.CharField(source="play.title", read_only=True)
    theatre_hall_name = serializers.CharField(source="theatre_hall.name", read_only=True)
    tickets_available = serializers.SerializerMethodField()

    class Meta:
        model = Performance
        fields = (
            "id",
            "play",
            "play_title",
            "theatre_hall",
            "theatre_hall_name",
            "show_time",
            "tickets_available",
        )

    def get_tickets_available(self, performance: Performance) -> int:
        total_seats = performance.theatre_hall.rows * performance.theatre_hall.seats_in_row
        sold_seats = performance.tickets.filter(reservation__isnull=False).count()
        return total_seats - sold_seats

