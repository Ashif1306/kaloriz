from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def compute_total_weight_gram(cart_items) -> int:
    """
    Menghitung total berat dari item keranjang.

    Args:
        cart_items: iterable dengan .product (punya weight_gram) dan .quantity

    Returns:
        Total berat dalam gram, minimal 1000 gram (1 kg).

    Example:
        >>> cart_items = CartItem.objects.filter(cart=cart)
        >>> total_weight = compute_total_weight_gram(cart_items)
    """
    total = 0
    for item in cart_items:
        w = getattr(item.product, "weight_gram", 0) or 0
        q = getattr(item, "quantity", 1) or 1
        total += w * q
    return max(1000, int(total))


def send_verification_email(user, verification_code):
    """
    Send verification code email to user

    Args:
        user: User object
        verification_code: EmailVerification object with the code

    Returns:
        Boolean indicating success/failure
    """
    subject = 'Kode Verifikasi Login - Kaloriz'

    # Create HTML message
    html_message = render_to_string('core/emails/verification_code.html', {
        'user': user,
        'code': verification_code.code,
        'expires_in': '10 menit'
    })

    # Create plain text version
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def send_welcome_email(user):
    """
    Send welcome email to newly registered user

    Args:
        user: User object

    Returns:
        Boolean indicating success/failure
    """
    subject = 'Selamat Datang di Kaloriz!'

    # Create HTML message
    html_message = render_to_string('core/emails/welcome.html', {
        'user': user,
    })

    # Create plain text version
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending welcome email: {e}")
        return False
