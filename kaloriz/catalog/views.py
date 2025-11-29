from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.utils.formats import number_format
from django.views.decorators.http import require_POST

from core.models import Cart

from .models import Product, Category, Testimonial, DiscountCode


def _get_watchlisted_product_ids(request):
    if request.user.is_authenticated:
        return list(
            request.user.watchlists.values_list('product_id', flat=True)
        )
    return []


def home(request):
    """Homepage with featured products"""
    featured_products = Product.objects.filter(
        available=True,
        is_featured=True,
    )[:8]
    categories = Category.objects.all()[:6]

    context = {
        'featured_products': featured_products,
        'categories': categories,
        'watchlisted_product_ids': _get_watchlisted_product_ids(request),
        'meta_title': 'Kaloriz - Toko Makanan Sehat',
        'meta_description': 'Belanja makanan sehat, praktis, dan bergizi di Kaloriz dengan informasi nutrisi lengkap.',
        'meta_url': request.build_absolute_uri(),
    }
    return render(request, 'catalog/home.html', context)


def product_list(request):
    """List all available products with filtering and search"""
    products = Product.objects.filter(available=True)
    categories = Category.objects.all()

    # Filter by category
    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)

    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Filter by price range
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    # Sort
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by in ['price', '-price', 'name', '-name', '-created_at']:
        products = products.order_by(sort_by)

    context = {
        'products': products,
        'categories': categories,
        'current_category': category_slug,
        'search_query': search_query,
        'watchlisted_product_ids': _get_watchlisted_product_ids(request),
        'meta_title': 'Daftar Produk - Kaloriz',
        'meta_description': 'Jelajahi semua produk Kaloriz lengkap dengan pilihan kategori dan filter harga.',
        'meta_url': request.build_absolute_uri(),
    }
    return render(request, 'catalog/product_list.html', context)


def product_detail(request, slug):
    """Product detail page"""
    product = get_object_or_404(Product, slug=slug, available=True)
    related_products = Product.objects.filter(
        category=product.category,
        available=True
    ).exclude(id=product.id)[:4]

    # Get approved testimonials for this product
    testimonials = Testimonial.objects.filter(
        product=product,
        is_approved=True
    ).select_related('user')[:10]

    watchlisted_ids = _get_watchlisted_product_ids(request)

    context = {
        'product': product,
        'related_products': related_products,
        'testimonials': testimonials,
        'watchlisted_product_ids': watchlisted_ids,
        'is_product_watchlisted': product.id in watchlisted_ids,
        'meta_title': f"{product.name} - Kaloriz",
        'meta_description': product.description[:150],
        'meta_image': request.build_absolute_uri(product.image.url) if product.image else request.build_absolute_uri(getattr(settings, "SITE_LOGO", "/static/images/logo.png")),
        'meta_url': request.build_absolute_uri(product.get_absolute_url()),
    }
    return render(request, 'catalog/product_detail.html', context)


def category_detail(request, slug):
    """Category page showing all products in category"""
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(category=category, available=True)

    context = {
        'category': category,
        'products': products,
        'watchlisted_product_ids': _get_watchlisted_product_ids(request),
        'meta_title': f"{category.name} - Kaloriz",
        'meta_description': category.description[:150] if category.description else f"Produk dalam kategori {category.name} di Kaloriz.",
        'meta_url': request.build_absolute_uri(category.get_absolute_url()),
    }
    return render(request, 'catalog/category_detail.html', context)


def search(request):
    """Search products"""
    query = request.GET.get('q', '')
    products = Product.objects.filter(available=True)

    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )

    context = {
        'products': products,
        'query': query,
        'watchlisted_product_ids': _get_watchlisted_product_ids(request),
        'meta_title': f"Hasil pencarian '{query}' - Kaloriz" if query else 'Pencarian Produk - Kaloriz',
        'meta_description': 'Cari produk Kaloriz dengan kata kunci favoritmu.',
        'meta_url': request.build_absolute_uri(),
    }
    return render(request, 'catalog/search_results.html', context)


def about(request):
    """About us page"""
    return render(
        request,
        'catalog/about.html',
        {
            'meta_title': 'Tentang Kaloriz',
            'meta_description': 'Kenali Kaloriz, toko online makanan sehat yang praktis dan bergizi.',
            'meta_url': request.build_absolute_uri(),
        },
    )


def contact(request):
    """Contact us page"""
    from django.http import JsonResponse

    if request.method == 'POST':
        # Handle contact form submission
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        subject = request.POST.get('subject')
        message = request.POST.get('message')

        # Here you can add logic to save to database or send email
        # For now, just return success
        messages.success(request, f'Terima kasih {name}! Pesan Anda telah diterima.')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})

        return redirect('catalog:contact')

    return render(
        request,
        'catalog/contact.html',
        {
            'meta_title': 'Kontak Kaloriz',
            'meta_description': 'Hubungi tim Kaloriz untuk pertanyaan atau dukungan pelanggan.',
            'meta_url': request.build_absolute_uri(),
        },
    )


def _format_rupiah(value):
    try:
        amount = Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal('0')
    return f"Rp {number_format(amount, decimal_pos=0, force_grouping=True)}"


@require_POST
@login_required
def apply_discount(request):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Permintaan tidak valid.'}, status=400)

    code = request.POST.get('code', '').strip()
    if not code:
        return JsonResponse({'success': False, 'error': 'Kode diskon harus diisi.'}, status=400)

    checkout_data = request.session.get('checkout', {})
    raw_subtotal = checkout_data.get('subtotal')
    raw_shipping = checkout_data.get('shipping_cost')

    try:
        subtotal = Decimal(raw_subtotal or 0)
    except (InvalidOperation, TypeError, ValueError):
        subtotal = Decimal('0')

    try:
        shipping_cost = Decimal(raw_shipping or 0)
    except (InvalidOperation, TypeError, ValueError):
        shipping_cost = Decimal('0')

    if subtotal == 0:
        cart = (
            Cart.objects.filter(user=request.user)
            .order_by('-updated_at', '-id')
            .prefetch_related('items__product')
            .first()
        )
        if cart:
            subtotal = Decimal(cart.get_selected_total() or 0)
            checkout_data['subtotal'] = str(subtotal)
            request.session['checkout'] = checkout_data
            request.session.modified = True

    try:
        discount = DiscountCode.objects.get(code__iexact=code)
    except DiscountCode.DoesNotExist:
        request.session.pop('discount', None)
        request.session.modified = True
        total = max(Decimal('0'), subtotal + shipping_cost)
        return JsonResponse({
            'success': False,
            'error': 'Kode diskon tidak ditemukan.',
            'discount_display': _format_rupiah(0),
            'total_display': _format_rupiah(total),
            'discount_active': False,
        }, status=404)

    shipping_method = checkout_data.get('shipping_method')
    grand_total = subtotal + shipping_cost

    if not discount.is_valid():
        request.session.pop('discount', None)
        request.session.modified = True
        total = max(Decimal('0'), grand_total)
        return JsonResponse({
            'success': False,
            'error': 'Kupon tidak aktif.',
            'discount_display': _format_rupiah(0),
            'total_display': _format_rupiah(total),
            'discount_active': False,
        }, status=400)

    if not discount.is_shipping_allowed(shipping_method):
        request.session.pop('discount', None)
        request.session.modified = True
        total = max(Decimal('0'), grand_total)
        return JsonResponse({
            'success': False,
            'error': 'Kupon tidak berlaku untuk kurir ini.',
            'discount_display': _format_rupiah(0),
            'total_display': _format_rupiah(total),
            'discount_active': False,
        }, status=400)

    min_spend = discount.get_min_spend()
    if grand_total < min_spend:
        request.session.pop('discount', None)
        request.session.modified = True
        total = max(Decimal('0'), grand_total)
        return JsonResponse({
            'success': False,
            'error': f'Minimal belanja { _format_rupiah(min_spend) }',
            'discount_display': _format_rupiah(0),
            'total_display': _format_rupiah(total),
            'discount_active': False,
        }, status=400)

    discount_amount = discount.calculate_discount(grand_total)
    if discount_amount > grand_total:
        discount_amount = grand_total

    request.session['discount'] = {
        'code': discount.code,
        'amount': str(discount_amount),
        'type': discount.discount_type,
        'type_label': discount.get_type_label(),
    }
    request.session.modified = True

    total = max(Decimal('0'), grand_total - discount_amount)

    return JsonResponse({
        'success': True,
        'code': discount.code,
        'discount_display': _format_rupiah(discount_amount),
        'discount_type_label': discount.get_type_label(),
        'total_display': _format_rupiah(total),
        'subtotal_display': _format_rupiah(subtotal),
        'shipping_cost_display': _format_rupiah(shipping_cost),
        'message': 'Kupon berhasil diterapkan.',
        'discount_active': True,
    })


@require_POST
@login_required
def cancel_discount(request):
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'success': False, 'error': 'Permintaan tidak valid.'}, status=400)

    checkout_data = request.session.get('checkout', {})
    raw_subtotal = checkout_data.get('subtotal')
    raw_shipping = checkout_data.get('shipping_cost')

    try:
        subtotal = Decimal(raw_subtotal or 0)
    except (InvalidOperation, TypeError, ValueError):
        subtotal = Decimal('0')

    try:
        shipping_cost = Decimal(raw_shipping or 0)
    except (InvalidOperation, TypeError, ValueError):
        shipping_cost = Decimal('0')

    if subtotal == 0:
        cart = (
            Cart.objects.filter(user=request.user)
            .order_by('-updated_at', '-id')
            .prefetch_related('items__product')
            .first()
        )
        if cart:
            subtotal = Decimal(cart.get_selected_total() or 0)
            checkout_data['subtotal'] = str(subtotal)
            request.session['checkout'] = checkout_data
            request.session.modified = True

    request.session.pop('discount', None)
    request.session.modified = True

    total = max(Decimal('0'), subtotal + shipping_cost)

    return JsonResponse({
        'success': True,
        'discount': 0,
        'discount_display': _format_rupiah(0),
        'total_after': str(total),
        'total_display': _format_rupiah(total),
        'subtotal_display': _format_rupiah(subtotal),
        'shipping_cost_display': _format_rupiah(shipping_cost),
        'discount_active': False,
        'discount_type_label': '',
    })
