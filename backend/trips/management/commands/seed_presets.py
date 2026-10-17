"""Load the demo trip presets shown in the sidebar. Safe to run repeatedly."""

from django.core.management.base import BaseCommand

from trips.models import TripPreset

PRESETS = [
    {
        "name": "Chicago → Denver (live)",
        "description": "Classic I-80 / I-76 run across the plains with a heavy load.",
        "origin": ("Chicago, Illinois, United States", 41.8781, -87.6298),
        "destination": ("Denver, Colorado, United States", 39.7392, -104.9903),
        "load_lb": 42_000,
        "interval_miles": 25,
    },
    {
        "name": "Dallas → Atlanta (live)",
        "description": "Southern I-20 corridor, mid-weight load.",
        "origin": ("Dallas, Texas, United States", 32.7767, -96.7970),
        "destination": ("Atlanta, Georgia, United States", 33.7490, -84.3880),
        "load_lb": 28_000,
        "interval_miles": 25,
    },
    {
        "name": "Los Angeles → Phoenix (live)",
        "description": "Short desert haul sampled every 10 miles.",
        "origin": ("Los Angeles, California, United States", 34.0522, -118.2437),
        "destination": ("Phoenix, Arizona, United States", 33.4484, -112.0740),
        "load_lb": 35_000,
        "interval_miles": 10,
    },
    {
        "name": "Seattle → Salt Lake City (live)",
        "description": "Mountain passes, sampled every 50 miles.",
        "origin": ("Seattle, Washington, United States", 47.6062, -122.3321),
        "destination": ("Salt Lake City, Utah, United States", 40.7608, -111.8910),
        "load_lb": 38_000,
        "interval_miles": 50,
    },
    {
        "name": "Demo: blizzard on I-80 (simulated)",
        "description": "Chicago → Denver with a simulated snow storm on the fastest route.",
        "origin": ("Chicago, Illinois, United States", 41.8781, -87.6298),
        "destination": ("Denver, Colorado, United States", 39.7392, -104.9903),
        "load_lb": 45_000,
        "interval_miles": 25,
        "simulate_storm": True,
    },
    {
        "name": "Demo: thunderstorm on I-20 (simulated)",
        "description": "Dallas → Atlanta with a simulated wind and rain storm.",
        "origin": ("Dallas, Texas, United States", 32.7767, -96.7970),
        "destination": ("Atlanta, Georgia, United States", 33.7490, -84.3880),
        "load_lb": 32_000,
        "interval_miles": 25,
        "simulate_storm": True,
    },
]


class Command(BaseCommand):
    help = "Create or update the demo trip presets."

    def handle(self, *args, **options):
        for order, preset in enumerate(PRESETS):
            o_label, o_lat, o_lon = preset["origin"]
            d_label, d_lat, d_lon = preset["destination"]
            TripPreset.objects.update_or_create(
                name=preset["name"],
                defaults={
                    "description": preset["description"],
                    "origin_label": o_label,
                    "origin_lat": o_lat,
                    "origin_lon": o_lon,
                    "destination_label": d_label,
                    "destination_lat": d_lat,
                    "destination_lon": d_lon,
                    "load_lb": preset["load_lb"],
                    "interval_miles": preset["interval_miles"],
                    "simulate_storm": preset.get("simulate_storm", False),
                    "sort_order": order,
                },
            )
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(PRESETS)} trip presets."))
