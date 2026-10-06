from django.contrib import admin

from theatre.models import Actor, Genre, Performance, Play, Reservation, TheatreHall, Ticket


@admin.register(Play)
class PlayAdmin(admin.ModelAdmin):
    list_display = ("title",)
    search_fields = ("title", "description")
    filter_horizontal = ("actors", "genres")


@admin.register(Performance)
class PerformanceAdmin(admin.ModelAdmin):
    list_display = ("play", "theatre_hall", "show_time")
    list_filter = ("theatre_hall", "show_time")
    search_fields = ("play__title",)


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("performance", "row", "seat", "reservation")
    list_filter = ("performance",)


admin.site.register((Actor, Genre, TheatreHall, Reservation))
