"""API tests for the theatre catalogue and seat booking workflow."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from theatre.models import (
    Actor,
    Genre,
    Performance,
    Play,
    Reservation,
    TheatreHall,
    Ticket,
)


class TheatreApiTests(APITestCase):
    def setUp(self) -> None:
        self.actor = Actor.objects.create(
            first_name="Meryl", last_name="Streep"
        )
        self.genre = Genre.objects.create(name="Drama")
        self.play = Play.objects.create(title="Doubt", description="A drama.")
        self.play.actors.add(self.actor)
        self.play.genres.add(self.genre)
        self.hall = TheatreHall.objects.create(
            name="Main", rows=2, seats_in_row=3
        )
        self.performance = Performance.objects.create(
            play=self.play,
            theatre_hall=self.hall,
            show_time=timezone.now() + timedelta(days=1),
        )
        self.user = get_user_model().objects.create_user(
            username="patron", password="Strong-Password-739!"
        )

    def authenticate(self) -> None:
        self.client.force_authenticate(user=self.user)

    def test_play_filters_and_invalid_filter(self) -> None:
        response = self.client.get(
            reverse("play-list"),
            {"genre": self.genre.pk, "actor": self.actor.pk},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data["results"]], [self.play.pk]
        )

        response = self.client.get(reverse("play-list"), {"genre": "invalid"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_performance_filters_validate_date_and_ids(self) -> None:
        response = self.client.get(
            reverse("performance-list"),
            {
                "play": self.play.pk,
                "show_time": self.performance.show_time.date(),
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data["results"]],
            [self.performance.pk],
        )
        self.assertEqual(
            self.client.get(
                reverse("performance-list"), {"play": 0}
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.get(
                reverse("performance-list"), {"show_time": "not-a-date"}
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_available_seats_excludes_reserved_seats(self) -> None:
        reservation = Reservation.objects.create(user=self.user)
        Ticket.objects.create(
            performance=self.performance,
            reservation=reservation,
            row=1,
            seat=2,
        )

        response = self.client.get(
            reverse("performance-available-seats", args=(self.performance.pk,))
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["performance"], self.performance.pk)
        self.assertNotIn(
            {"row": 1, "seat": 2}, response.data["available_seats"]
        )
        self.assertEqual(len(response.data["available_seats"]), 5)

    def test_registration_and_jwt_token(self) -> None:
        response = self.client.post(
            reverse("user-register"),
            {
                "username": "new_patron",
                "password": "Another-Strong-Password-739!",
                "password_confirmation": "Another-Strong-Password-739!",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            get_user_model().objects.filter(username="new_patron").exists()
        )

        response = self.client.post(
            reverse("token_obtain_pair"),
            {
                "username": "new_patron",
                "password": "Another-Strong-Password-739!",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_booking_rejects_anonymous_request_and_records_owner(self) -> None:
        payload = {
            "tickets": [
                {"performance": self.performance.pk, "row": 1, "seat": 1}
            ]
        }

        self.assertEqual(
            self.client.post(
                reverse("reservation-list"), payload
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

        self.authenticate()
        response = self.client.post(
            reverse("reservation-list"), payload, format="json"
        )

        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED, response.data
        )
        self.assertEqual(Reservation.objects.get().user, self.user)
        self.assertEqual(Ticket.objects.get().reservation.user, self.user)

    def test_booking_rejects_duplicate_or_invalid_seats(self) -> None:
        self.authenticate()
        url = reverse("reservation-list")

        duplicate_payload = {
            "tickets": [
                {
                    "performance": self.performance.pk,
                    "row": 1,
                    "seat": 1,
                },
                {
                    "performance": self.performance.pk,
                    "row": 1,
                    "seat": 1,
                },
            ]
        }
        duplicate_response = self.client.post(
            url, duplicate_payload, format="json"
        )
        self.assertEqual(
            duplicate_response.status_code, status.HTTP_400_BAD_REQUEST
        )

        occupied_reservation = Reservation.objects.create(user=self.user)
        Ticket.objects.create(
            performance=self.performance,
            reservation=occupied_reservation,
            row=1,
            seat=2,
        )
        occupied_response = self.client.post(
            url,
            {
                "tickets": [
                    {
                        "performance": self.performance.pk,
                        "row": 1,
                        "seat": 2,
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(
            occupied_response.status_code, status.HTTP_400_BAD_REQUEST
        )

        out_of_range_response = self.client.post(
            url,
            {
                "tickets": [
                    {"performance": self.performance.pk, "row": 3, "seat": 1}
                ]
            },
            format="json",
        )
        self.assertEqual(
            out_of_range_response.status_code, status.HTTP_400_BAD_REQUEST
        )

    def test_reservations_are_private_to_their_owner(self) -> None:
        other_user = get_user_model().objects.create_user(
            username="another_patron", password="Strong-Password-738!"
        )
        reservation = Reservation.objects.create(user=other_user)
        self.authenticate()

        list_response = self.client.get(reverse("reservation-list"))
        detail_response = self.client.delete(
            reverse("reservation-detail", args=(reservation.pk,))
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["results"], [])
        self.assertEqual(
            detail_response.status_code, status.HTTP_404_NOT_FOUND
        )
        self.assertTrue(Reservation.objects.filter(pk=reservation.pk).exists())

    def test_catalogue_reads_are_public(self) -> None:
        for resource in (
            "actors",
            "genres",
            "plays",
            "theatre-halls",
            "performances",
        ):
            with self.subTest(resource=resource):
                response = self.client.get(f"/api/{resource}/")

                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_regular_users_cannot_write_catalogue(self) -> None:
        self.authenticate()
        resources = (
            ("actors", self.actor.pk, {"first_name": "New", "last_name": "Actor"}),
            ("genres", self.genre.pk, {"name": "Comedy"}),
            (
                "plays",
                self.play.pk,
                {"title": "New Play", "description": "A new play."},
            ),
            (
                "theatre-halls",
                self.hall.pk,
                {"name": "Small Hall", "rows": 2, "seats_in_row": 3},
            ),
            (
                "performances",
                self.performance.pk,
                {
                    "play": self.play.pk,
                    "theatre_hall": self.hall.pk,
                    "show_time": (timezone.now() + timedelta(days=2)).isoformat(),
                },
            ),
        )

        for resource, object_id, payload in resources:
            with self.subTest(resource=resource, method="POST"):
                response = self.client.post(f"/api/{resource}/", payload)
                self.assertEqual(
                    response.status_code, status.HTTP_403_FORBIDDEN
                )

            detail_url = f"/api/{resource}/{object_id}/"
            with self.subTest(resource=resource, method="PATCH"):
                response = self.client.patch(detail_url, payload)
                self.assertEqual(
                    response.status_code, status.HTTP_403_FORBIDDEN
                )

            with self.subTest(resource=resource, method="DELETE"):
                response = self.client.delete(detail_url)
                self.assertEqual(
                    response.status_code, status.HTTP_403_FORBIDDEN
                )

    def test_staff_users_can_write_catalogue(self) -> None:
        staff_user = get_user_model().objects.create_user(
            username="catalogue_admin",
            password="Strong-Password-737!",
            is_staff=True,
        )
        self.client.force_authenticate(user=staff_user)
        later_show_time = timezone.now() + timedelta(days=2)
        resources = (
            ("actors", {"first_name": "New", "last_name": "Actor"}, {"first_name": "Updated"}),
            ("genres", {"name": "Comedy"}, {"name": "Updated Genre"}),
            (
                "plays",
                {"title": "New Play", "description": "A new play."},
                {"title": "Updated Play"},
            ),
            (
                "theatre-halls",
                {"name": "Small Hall", "rows": 2, "seats_in_row": 3},
                {"name": "Updated Hall"},
            ),
            (
                "performances",
                {
                    "play": self.play.pk,
                    "theatre_hall": self.hall.pk,
                    "show_time": later_show_time.isoformat(),
                },
                {"show_time": (later_show_time + timedelta(days=1)).isoformat()},
            ),
        )

        for resource, create_payload, update_payload in resources:
            with self.subTest(resource=resource):
                response = self.client.post(
                    f"/api/{resource}/", create_payload
                )
                self.assertEqual(
                    response.status_code, status.HTTP_201_CREATED, response.data
                )
                detail_url = f"/api/{resource}/{response.data['id']}/"

                update_response = self.client.patch(detail_url, update_payload)
                self.assertEqual(
                    update_response.status_code,
                    status.HTTP_200_OK,
                    update_response.data,
                )
                delete_response = self.client.delete(detail_url)
                self.assertEqual(
                    delete_response.status_code, status.HTTP_204_NO_CONTENT
                )
