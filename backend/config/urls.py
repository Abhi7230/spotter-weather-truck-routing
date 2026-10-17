from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import include, path, re_path


def spa(request):
    """Serve the React app for any non-API path (client-side routing)."""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        raise Http404("Frontend not built. Run `npm run build` in frontend/.")
    return FileResponse(index.open("rb"), content_type="text/html")


urlpatterns = [
    path("api/", include("trips.urls")),
    re_path(r"^(?!api/|static/).*$", spa),
]
