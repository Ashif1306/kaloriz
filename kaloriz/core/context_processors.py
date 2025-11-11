"""Context processors for core app"""
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
        'cart_count': cart_count
    }
