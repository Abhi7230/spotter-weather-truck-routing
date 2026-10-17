import logging

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from trips.models import TripPlan, TripPreset
from trips.planner import PlanRequest, plan_trip
from trips.serializers import (
    PlanRequestSerializer,
    TripPlanListSerializer,
    TripPlanSerializer,
    TripPresetSerializer,
)
from trips.services.geocoding import search_places
from trips.services.http import UpstreamError

logger = logging.getLogger(__name__)


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["GET"])
def geocode(request):
    query = request.query_params.get("q", "").strip()
    if len(query) < 3:
        return Response([])
    try:
        return Response(search_places(query))
    except UpstreamError as exc:
        logger.warning("Geocoding failed: %s", exc)
        return Response({"detail": "Place search is unavailable."}, status=502)


class PresetList(ListAPIView):
    queryset = TripPreset.objects.all()
    serializer_class = TripPresetSerializer
    pagination_class = None


class PlanList(ListAPIView):
    serializer_class = TripPlanListSerializer
    pagination_class = None

    throttle_scope = "plans"

    def get_queryset(self):
        return TripPlan.objects.all()[:10]

    def get_throttles(self):
        # Each plan fans out to hundreds of weather lookups, so creation is rate limited.
        return [ScopedRateThrottle()] if self.request.method == "POST" else super().get_throttles()

    def post(self, request):
        serializer = PlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        origin, destination = data["origin"], data["destination"]

        try:
            result = plan_trip(
                PlanRequest(
                    origin=(origin["lat"], origin["lon"]),
                    destination=(destination["lat"], destination["lon"]),
                    departure=data["departure"],
                    load_lb=data["load_lb"],
                    interval_miles=data["interval_miles"],
                    simulate_storm=data["simulate_storm"],
                )
            )
        except UpstreamError as exc:
            logger.warning("Planning failed: %s", exc)
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        plan = TripPlan.objects.create(
            origin_label=origin["label"],
            origin_lat=origin["lat"],
            origin_lon=origin["lon"],
            destination_label=destination["label"],
            destination_lat=destination["lat"],
            destination_lon=destination["lon"],
            departure=data["departure"],
            load_lb=data["load_lb"],
            interval_miles=data["interval_miles"],
            simulate_storm=data["simulate_storm"],
            result=result,
        )
        return Response(TripPlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class PlanDetail(RetrieveAPIView):
    queryset = TripPlan.objects.all()
    serializer_class = TripPlanSerializer
