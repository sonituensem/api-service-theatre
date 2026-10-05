"""Database models for theatre programming and reservations."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Actor(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Play(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    actors = models.ManyToManyField(Actor, related_name="plays", blank=True)
    genres = models.ManyToManyField(Genre, related_name="plays", blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class TheatreHall(models.Model):
    name = models.CharField(max_length=100, unique=True)
    rows = models.PositiveSmallIntegerField()
    seats_in_row = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=Q(rows__gt=0), name="hall_rows_positive"),
            models.CheckConstraint(
                condition=Q(seats_in_row__gt=0), name="hall_seats_in_row_positive"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Performance(models.Model):
    play = models.ForeignKey(Play, on_delete=models.CASCADE, related_name="performances")
    theatre_hall = models.ForeignKey(
        TheatreHall, on_delete=models.CASCADE, related_name="performances"
    )
    show_time = models.DateTimeField()

    class Meta:
        ordering = ["show_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["theatre_hall", "show_time"],
                name="one_performance_per_hall_time",
            )
        ]

    def __str__(self) -> str:
        return f"{self.play} at {self.show_time:%Y-%m-%d %H:%M}"


class Reservation(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reservations"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Reservation #{self.pk} by {self.user}"


class Ticket(models.Model):
    row = models.PositiveSmallIntegerField()
    seat = models.PositiveSmallIntegerField()
    performance = models.ForeignKey(
        Performance, on_delete=models.CASCADE, related_name="tickets"
    )
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="tickets",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["performance", "row", "seat"]
        constraints = [
            models.UniqueConstraint(
                fields=["performance", "row", "seat"],
                name="unique_ticket_seat_per_performance",
            ),
            models.CheckConstraint(condition=Q(row__gt=0), name="ticket_row_positive"),
            models.CheckConstraint(condition=Q(seat__gt=0), name="ticket_seat_positive"),
        ]

    def clean(self) -> None:
        super().clean()
        if not self.performance_id:
            return
        hall = self.performance.theatre_hall
        errors = {}
        if self.row > hall.rows:
            errors["row"] = f"Row must be between 1 and {hall.rows}."
        if self.seat > hall.seats_in_row:
            errors["seat"] = f"Seat must be between 1 and {hall.seats_in_row}."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.performance}: row {self.row}, seat {self.seat}"
