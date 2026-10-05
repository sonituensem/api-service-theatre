"""Serializers for theatre catalogue resources."""

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from theatre.models import Actor, Genre, Performance, Play, Reservation, TheatreHall, Ticket


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
        sold_seats = sum(
            ticket.reservation_id is not None for ticket in performance.tickets.all()
        )
        return total_seats - sold_seats


class TicketSerializer(serializers.ModelSerializer):
    play_title = serializers.CharField(source="performance.play.title", read_only=True)
    show_time = serializers.DateTimeField(source="performance.show_time", read_only=True)
    theatre_hall_name = serializers.CharField(
        source="performance.theatre_hall.name", read_only=True
    )

    class Meta:
        model = Ticket
        fields = (
            "id",
            "performance",
            "play_title",
            "show_time",
            "theatre_hall_name",
            "row",
            "seat",
        )


class SeatCoordinateSerializer(serializers.Serializer):
    row = serializers.IntegerField()
    seat = serializers.IntegerField()


class AvailableSeatsSerializer(serializers.Serializer):
    performance = serializers.IntegerField()
    available_seats = SeatCoordinateSerializer(many=True)


class ReservationSerializer(serializers.ModelSerializer):
    tickets = TicketSerializer(many=True, read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Reservation
        fields = ("id", "created_at", "username", "tickets")


class SeatSelectionSerializer(serializers.Serializer):
    performance = serializers.PrimaryKeyRelatedField(queryset=Performance.objects.all())
    row = serializers.IntegerField(min_value=1)
    seat = serializers.IntegerField(min_value=1)

    def validate(self, attrs: dict) -> dict:
        performance = attrs["performance"]
        hall = performance.theatre_hall
        if attrs["row"] > hall.rows:
            raise serializers.ValidationError(
                {"row": f"Row must be between 1 and {hall.rows}."}
            )
        if attrs["seat"] > hall.seats_in_row:
            raise serializers.ValidationError(
                {"seat": f"Seat must be between 1 and {hall.seats_in_row}."}
            )
        if performance.show_time <= timezone.now():
            raise serializers.ValidationError(
                {"performance": "Seats can only be reserved for future performances."}
            )
        return attrs


class ReservationCreateSerializer(serializers.ModelSerializer):
    tickets = SeatSelectionSerializer(many=True, allow_empty=False, write_only=True)
    booked_tickets = TicketSerializer(source="tickets", many=True, read_only=True)

    class Meta:
        model = Reservation
        fields = ("id", "created_at", "tickets", "booked_tickets")
        read_only_fields = ("id", "created_at")

    def validate_tickets(self, selections: list[dict]) -> list[dict]:
        seats = [
            (selection["performance"].pk, selection["row"], selection["seat"])
            for selection in selections
        ]
        if len(seats) != len(set(seats)):
            raise serializers.ValidationError("The same seat cannot be selected twice.")
        return selections

    @transaction.atomic
    def create(self, validated_data: dict) -> Reservation:
        selections = validated_data.pop("tickets")
        performance_ids = sorted(
            {selection["performance"].pk for selection in selections}
        )
        locked_performances = {
            performance.pk: performance
            for performance in Performance.objects.select_for_update()
            .select_related("theatre_hall")
            .filter(pk__in=performance_ids)
            .order_by("pk")
        }
        reservation = Reservation.objects.create(user=self.context["request"].user)
        tickets = []
        for selection in selections:
            performance = locked_performances[selection["performance"].pk]
            row = selection["row"]
            seat = selection["seat"]
            if Ticket.objects.filter(
                performance=performance,
                row=row,
                seat=seat,
                reservation__isnull=False,
            ).exists():
                raise serializers.ValidationError(
                    {"tickets": f"Row {row}, seat {seat} is already reserved."}
                )
            tickets.append(
                Ticket(
                    performance=performance,
                    row=row,
                    seat=seat,
                    reservation=reservation,
                )
            )
        try:
            with transaction.atomic():
                Ticket.objects.bulk_create(tickets)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"tickets": "One or more selected seats are no longer available."}
            ) from exc
        return reservation


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )
    password_confirmation = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    class Meta:
        model = get_user_model()
        fields = ("id", "username", "password", "password_confirmation")
        read_only_fields = ("id",)

    def validate(self, attrs: dict) -> dict:
        password = attrs["password"]
        if password != attrs.pop("password_confirmation"):
            raise serializers.ValidationError(
                {"password_confirmation": "The passwords do not match."}
            )
        candidate_user = get_user_model()(username=attrs.get("username"))
        try:
            password_validation.validate_password(password, user=candidate_user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data: dict):
        return get_user_model().objects.create_user(**validated_data)

