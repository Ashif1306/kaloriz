"""Context processors for core app"""
from django.conf import settings
from .models import Cart


def cart_context(request):
    """Add cart count to all templates"""
    cart_count = 0
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            cart_count = cart.items.count()
        except Cart.DoesNotExist:
            cart_count = 0

    return {
        "cart_count": cart_count,
        "meta_title": getattr(settings, "SITE_NAME", "Kaloriz"),
        "meta_description": getattr(settings, "SITE_DESCRIPTION", ""),
        "meta_image": request.build_absolute_uri(
            getattr(settings, "SITE_LOGO", "/static/images/logo.png")
        ) if request else getattr(settings, "SITE_LOGO", ""),
        "site_url": getattr(settings, "SITE_URL", ""),
        "site_name": getattr(settings, "SITE_NAME", "Kaloriz"),
    }
