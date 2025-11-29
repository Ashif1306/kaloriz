from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from catalog.sitemaps import CategorySitemap, ProductSitemap, StaticViewSitemap


sitemaps = {
    "products": ProductSitemap,
    "categories": CategorySitemap,
    "static": StaticViewSitemap,
}


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("catalog.urls")),
    path("", include("core.urls")),
    path("shipping/", include("shipping.urls")),  # Shipping module
    path("payment/", include("payment.urls")),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path(
        "robots.txt",
        lambda request: HttpResponse("User-agent: *\nDisallow:\nSitemap: " + request.build_absolute_uri("/sitemap.xml"), content_type="text/plain"),
    ),
]

# SELALU tambahkan static & media (tidak pakai if settings.DEBUG)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
