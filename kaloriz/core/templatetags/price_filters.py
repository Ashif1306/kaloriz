from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='rupiah')
def rupiah(value):
    """Format number as Rupiah with dot separator for thousands"""
    try:
        value = float(value)
        # Format with dot as thousand separator
        formatted = "{:,.0f}".format(value).replace(',', '.')
        return f"Rp {formatted}"
    except (ValueError, TypeError):
        return value


@register.filter(name='dot_separator')
def dot_separator(value):
    """Format number with dot as thousand separator"""
    try:
        value = float(value)
        # Format with dot as thousand separator
        return "{:,.0f}".format(value).replace(',', '.')
    except (ValueError, TypeError):
        return value


@register.filter(name='rating_stars')
def rating_stars(product):
    """Generate star rating HTML for product"""
    try:
        # Get average rating from testimonials
        testimonials = product.testimonials.filter(is_approved=True)
        if testimonials.exists():
            avg_rating = sum(t.rating for t in testimonials) / testimonials.count()
            rating_text = f"{avg_rating:.1f}"
        else:
            avg_rating = 0
            rating_text = "0.0"

        html = '<div class="product-rating">'

        # Generate stars
        for i in range(1, 6):
            if i <= avg_rating:
                html += '<i class="fas fa-star"></i>'
            elif i - 0.5 <= avg_rating:
                html += '<i class="fas fa-star-half-alt"></i>'
            else:
                html += '<i class="far fa-star"></i>'

        html += f'<span class="rating-text">{rating_text}</span>'
        html += '</div>'

        return mark_safe(html)
    except:
        # Default: 5 gray stars
        html = '<div class="product-rating">'
        for i in range(5):
            html += '<i class="far fa-star"></i>'
        html += '<span class="rating-text">0.0</span>'
        html += '</div>'
        return mark_safe(html)
