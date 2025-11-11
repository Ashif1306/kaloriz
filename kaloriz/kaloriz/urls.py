from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("catalog.urls")),
    path("", include("core.urls")),
    path("shipping/", include("shipping.urls")),  # Shipping module
    path("payment/", include("payment.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
