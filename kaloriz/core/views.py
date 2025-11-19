import json
import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db import transaction
from django.db.models import F, Count
from django.utils import timezone
from django.utils.formats import number_format
from django.urls import reverse

from .models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    PaymentMethod,
    UserProfile,
    Watchlist,
    EmailVerification,
)
from catalog.models import Product, DiscountCode, Testimonial
from .forms import CustomUserRegistrationForm, TestimonialForm
from .utils import send_verification_email, send_welcome_email
from .services.orders import create_order_from_checkout, cancel_order_due_to_timeout
from shipping.models import District, Address
from shipping.views import calculate_shipping_cost, validate_shipping_data
from shipping.forms import AddressForm

from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST


def _get_active_cart(request):
    """Return the most recent cart for the current user with items preloaded."""
    if not request.user.is_authenticated:
        raise Http404("Cart not found")

    cart = (
        Cart.objects.filter(user=request.user)
        .order_by('-updated_at', '-id')
        .prefetch_related('items__product')
        .first()
    )

    if cart is None:
        raise Http404("Cart not found")

    return cart


def _prepare_selected_cart_items(selected_items_qs):
    """Return selected cart items with fresh quantity data from the database."""
    items = list(selected_items_qs)

    if not items:
        return items, {}

    quantities = dict(
        CartItem.objects.filter(pk__in=[item.pk for item in items])
        .values_list('pk', 'quantity')
    )

    for item in items:
        item.quantity = quantities.get(item.pk, item.quantity)

    return items, quantities

# Cart Views
@login_required
def cart_view(request):
    """Display user's shopping cart"""
    cart, created = Cart.objects.get_or_create(user=request.user)
    context = {
        'cart': cart,
    }
    return render(request, 'core/cart.html', context)


@login_required
def add_to_cart(request, product_id):
    """Add product to cart"""
    from django.http import JsonResponse

    product = get_object_or_404(Product, id=product_id, available=True)
    cart, created = Cart.objects.get_or_create(user=request.user)
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    # Check stock
    quantity = int(request.POST.get('quantity', 1))
    if product.stock < quantity:
        if request.POST.get('buy_now'):
            return JsonResponse({'success': False, 'message': 'Stok tidak mencukupi'})
        error_message = f'Stok {product.name} tidak mencukupi.'
        if is_ajax:
            return JsonResponse({'success': False, 'message': error_message}, status=400)
        messages.error(request, error_message)
        return redirect('catalog:product_detail', slug=product.slug)

    # Check if this is a "Buy Now" request
    is_buy_now = request.POST.get('buy_now') == 'true'

    if is_buy_now:
        # Unselect all current items
        cart.items.all().update(is_selected=False)

    # Add or update cart item
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': quantity, 'is_selected': True}
    )

    if not created:
        # Update quantity if item already exists
        if is_buy_now:
            # For buy now, replace quantity instead of adding
            cart_item.quantity = quantity
        else:
            new_quantity = cart_item.quantity + quantity
            if product.stock < new_quantity:
                if request.POST.get('buy_now'):
                    return JsonResponse({'success': False, 'message': 'Stok tidak mencukupi'})
                if is_ajax:
                    return JsonResponse({'success': False, 'message': f'Stok {product.name} tidak mencukupi.'}, status=400)
                messages.error(request, f'Stok {product.name} tidak mencukupi.')
                return redirect('catalog:product_detail', slug=product.slug)
            cart_item.quantity = new_quantity

        cart_item.is_selected = True
        cart_item.save()

    if is_buy_now:
        return JsonResponse({'success': True})

    success_message = f'{product.name} berhasil ditambahkan ke keranjang.'
    if is_ajax:
        return JsonResponse({
            'success': True,
            'message': 'Produk berhasil ditambahkan ke keranjang.',
            'cart_count': cart.items.count(),
        })

    messages.success(request, success_message)
    return redirect('core:cart')


@login_required
def update_cart_item(request, item_id):
    """Update cart item quantity"""
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    quantity = int(request.POST.get('quantity', 1))

    if quantity > 0:
        if cart_item.product.stock >= quantity:
            cart_item.quantity = quantity
            cart_item.save()
            messages.success(request, 'Keranjang berhasil diperbarui.')
        else:
            messages.error(request, f'Stok {cart_item.product.name} tidak mencukupi.')
    else:
        cart_item.delete()
        messages.success(request, 'Item berhasil dihapus dari keranjang.')

    return redirect('core:cart')


@login_required
def remove_from_cart(request, item_id):
    """Remove item from cart"""
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    product_name = cart_item.product.name
    cart_item.delete()
    messages.success(request, f'{product_name} berhasil dihapus dari keranjang.')
    return redirect('core:cart')


@login_required
def clear_cart(request):
    """Clear all items from cart"""
    cart = get_object_or_404(Cart, user=request.user)
    cart.items.all().delete()
    messages.success(request, 'Keranjang berhasil dikosongkan.')
    return redirect('core:cart')


@login_required
def toggle_cart_item_selection(request, item_id):
    """Toggle cart item selection for checkout"""
    from django.http import JsonResponse
    import json

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})

    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)

    try:
        data = json.loads(request.body)
        is_selected = data.get('is_selected', True)
        cart_item.is_selected = is_selected
        cart_item.save()

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def delete_selected_cart_items(request):
    """Delete selected cart items"""
    from django.http import JsonResponse
    import json

    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})

    try:
        data = json.loads(request.body)
        item_ids = data.get('item_ids', [])

        if not item_ids:
            return JsonResponse({'success': False, 'message': 'No items selected'})

        # Delete items that belong to current user
        deleted_count = CartItem.objects.filter(
            id__in=item_ids,
            cart__user=request.user
        ).delete()[0]

        return JsonResponse({
            'success': True,
            'message': f'{deleted_count} item berhasil dihapus'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


# Checkout Views
def _format_rupiah(value):
    """Format decimal value into Indonesian Rupiah string."""
    try:
        value = Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        value = Decimal('0')
    return f"Rp {number_format(value, decimal_pos=0, force_grouping=True)}"


@login_required
def checkout(request):
    """Modern multi-step checkout - Step 1: Select Address"""
    cart = _get_active_cart(request)

    # Check if there are any selected items
    selected_items_qs = cart.items.filter(is_selected=True).select_related('product')

    if not selected_items_qs.exists():
        messages.error(request, 'Pilih minimal 1 item untuk checkout.')
        return redirect('core:cart')

    selected_items, _ = _prepare_selected_cart_items(selected_items_qs)

    # Get user profile for pre-filling form
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = None

    user_addresses = list(
        Address.objects.filter(user=request.user)
        .select_related('district')
        .order_by('-is_default', '-created_at')
    )

    default_address = next((addr for addr in user_addresses if addr.is_default), None)

    # Get user's saved addresses
    user_addresses_qs = Address.objects.filter(
        user=request.user,
        is_deleted=False,
    ).select_related('district').annotate(
        used_in_orders=Count('order', distinct=True),
    )

    user_addresses = list(user_addresses_qs.order_by('-is_default', '-created_at'))

    # Get default address if exists
    default_address = next((addr for addr in user_addresses if addr.is_default), None)

    checkout_data = request.session.get('checkout', {})
    selected_address_id = checkout_data.get('address_id')
    active_address = None

    if selected_address_id:
        active_address = next(
            (addr for addr in user_addresses if addr.id == selected_address_id),
            None,
        )
        if not active_address and user_addresses:
            # Selected address no longer available; clear stale session state
            for key in ['address_id', 'shipping_method', 'shipping_cost', 'eta']:
                checkout_data.pop(key, None)
            request.session['checkout'] = checkout_data
            request.session.modified = True
            messages.warning(
                request,
                'Alamat aktif Anda sudah tidak tersedia. Silakan pilih alamat lain.',
            )

    if not active_address:
        active_address = default_address or (user_addresses[0] if user_addresses else None)

    districts = District.objects.filter(is_active=True).order_by('name')

    subtotal = Decimal(cart.get_selected_total() or 0)
    raw_shipping_cost = checkout_data.get('shipping_cost')
    selected_shipping_cost = None

    if raw_shipping_cost not in (None, ''):
        try:
            selected_shipping_cost = Decimal(raw_shipping_cost)
        except (InvalidOperation, TypeError, ValueError):
            selected_shipping_cost = None

    selected_total = subtotal + (selected_shipping_cost or Decimal('0'))
    selected_eta = checkout_data.get('eta')
    has_initial_quote = bool(selected_shipping_cost is not None and checkout_data.get('shipping_method'))

    context = {
        'cart': cart,
        'selected_items': selected_items,
        'profile': profile,
        'user_addresses': user_addresses,
        'default_address': default_address,
        'active_address_id': active_address.id if active_address else None,
        'selected_shipping_method': checkout_data.get('shipping_method'),
        'districts': districts,
        'selected_shipping_cost': selected_shipping_cost,
        'selected_total': selected_total,
        'selected_eta': selected_eta,
        'has_initial_quote': has_initial_quote,
    }
    return render(request, 'core/checkout_address.html', context)


@login_required
def checkout_payment(request):
    """Checkout step 2 - choose payment method."""
    cart = _get_active_cart(request)

    selected_items_qs = cart.items.filter(is_selected=True).select_related('product')
    if not selected_items_qs.exists():
        messages.error(request, 'Pilih minimal 1 item untuk checkout.')
        return redirect('core:cart')

    checkout_data = request.session.get('checkout', {})
    address_id = checkout_data.get('address_id')
    shipping_method = checkout_data.get('shipping_method')
    raw_shipping_cost = checkout_data.get('shipping_cost')

    if not address_id or not shipping_method or raw_shipping_cost in (None, ''):
        messages.warning(request, 'Lengkapi informasi pengiriman terlebih dahulu.')
        return redirect('core:checkout')

    try:
        shipping_cost = Decimal(raw_shipping_cost)
    except (InvalidOperation, TypeError, ValueError):
        for key in ['shipping_cost', 'shipping_method', 'eta']:
            checkout_data.pop(key, None)
        request.session['checkout'] = checkout_data
        request.session.modified = True
        messages.warning(request, 'Informasi ongkir tidak valid. Silakan pilih ulang alamat dan kurir.')
        return redirect('core:checkout')

    subtotal = Decimal(cart.get_selected_total() or 0)
    total = subtotal + shipping_cost

    payment_methods_qs = PaymentMethod.objects.filter(is_active=True).order_by('display_order', 'name')
    payment_methods = list(payment_methods_qs)

    if not payment_methods:
        messages.warning(
            request,
            'Belum ada metode pembayaran yang dapat dipilih. Silakan hubungi admin toko.',
        )

    selected_payment_slug = checkout_data.get('payment_method')
    selected_payment_method = None

    if selected_payment_slug:
        selected_payment_method = next(
            (m for m in payment_methods if m.slug.lower() == selected_payment_slug.lower()),
            None,
        )
        if selected_payment_method is None:
            checkout_data.pop('payment_method', None)
            request.session['checkout'] = checkout_data
            request.session.modified = True

    if selected_payment_method is None and payment_methods:
        selected_payment_method = payment_methods[0]

    if request.method == 'POST':
        submitted_slug = (request.POST.get('payment_method') or '').strip()
        chosen_method = (
            payment_methods_qs.filter(slug__iexact=submitted_slug).first()
            if submitted_slug
            else None
        )

        if not chosen_method:
            messages.error(request, 'Pilih metode pembayaran yang tersedia.')
        else:
            checkout_data['payment_method'] = chosen_method.slug
            request.session['checkout'] = checkout_data
            request.session.modified = True
            return redirect('core:checkout_review')

    selected_payment_slug = selected_payment_method.slug if selected_payment_method else None
    shipping_method_label = 'Express' if str(shipping_method).upper() == 'EXP' else 'Reguler'
    eta = checkout_data.get('eta')

    context = {
        'cart': cart,
        'subtotal': subtotal,
        'subtotal_display': _format_rupiah(subtotal),
        'shipping_cost': shipping_cost,
        'shipping_cost_display': _format_rupiah(shipping_cost),
        'total': total,
        'total_display': _format_rupiah(total),
        'shipping_method_label': shipping_method_label,
        'eta': eta,
        'payment_methods': payment_methods,
        'selected_payment_method': selected_payment_slug,
        'selected_payment_method_obj': selected_payment_method,
    }
    return render(request, 'core/checkout_payment.html', context)


@login_required
def checkout_review(request):
    """Checkout step 3 - review order summary before placing order."""
    cart = _get_active_cart(request)

    selected_items_qs = cart.items.filter(is_selected=True).select_related('product')
    if not selected_items_qs.exists():
        messages.error(request, 'Pilih minimal 1 item untuk checkout.')
        return redirect('core:cart')

    checkout_data = request.session.get('checkout', {})
    address_id = checkout_data.get('address_id')

    payment_method_slug = checkout_data.get('payment_method')
    if not payment_method_slug:
        messages.warning(request, 'Silakan pilih metode pembayaran terlebih dahulu.')
        return redirect('core:checkout_payment')

    payment_method = (
        PaymentMethod.objects.filter(slug__iexact=payment_method_slug, is_active=True)
        .order_by('display_order', 'name')
        .first()
    )

    if payment_method is None:
        checkout_data.pop('payment_method', None)
        request.session['checkout'] = checkout_data
        request.session.modified = True
        messages.warning(request, 'Metode pembayaran yang dipilih tidak tersedia. Silakan pilih ulang.')
        return redirect('core:checkout_payment')

    shipping_address = None
    if address_id:
        shipping_address = (
            Address.objects.select_related('district')
            .filter(id=address_id, user=request.user, is_deleted=False)
            .first()
        )

    if not shipping_address:
        messages.warning(request, 'Alamat pengiriman tidak ditemukan. Silakan pilih ulang.')
        return redirect('core:checkout')

    raw_shipping_cost = checkout_data.get('shipping_cost')
    try:
        shipping_cost = Decimal(raw_shipping_cost or 0)
    except (InvalidOperation, TypeError, ValueError):
        shipping_cost = Decimal('0')

    subtotal = Decimal(cart.get_selected_total() or 0)
    checkout_data['subtotal'] = str(subtotal)
    request.session['checkout'] = checkout_data
    request.session.modified = True

    discount_session = request.session.get('discount') or {}
    discount_amount = Decimal('0')
    discount_code = discount_session.get('code')
    discount_type_label = discount_session.get('type_label', '')

    shipping_method = checkout_data.get('shipping_method')
    grand_total = subtotal + shipping_cost

    if discount_code:
        discount_obj = DiscountCode.objects.filter(code__iexact=discount_code).first()
        if discount_obj and discount_obj.is_valid():
            if discount_obj.is_shipping_allowed(shipping_method):
                if grand_total >= discount_obj.get_min_spend():
                    discount_amount = discount_obj.calculate_discount(grand_total)
                    if discount_amount > grand_total:
                        discount_amount = grand_total
                    discount_type_label = discount_obj.get_type_label()
                    request.session['discount'] = {
                        'code': discount_code,
                        'amount': str(discount_amount),
                        'type': discount_obj.discount_type,
                        'type_label': discount_type_label,
                    }
                    request.session.modified = True
                else:
                    request.session.pop('discount', None)
                    request.session.modified = True
                    discount_code = None
                    discount_type_label = ''
            else:
                request.session.pop('discount', None)
                request.session.modified = True
                discount_code = None
                discount_type_label = ''
        else:
            request.session.pop('discount', None)
            request.session.modified = True
            discount_code = None
            discount_amount = Decimal('0')
            discount_type_label = ''

    total = subtotal + shipping_cost - discount_amount
    if total < 0:
        total = Decimal('0')

    selected_items, _ = _prepare_selected_cart_items(selected_items_qs)

    shipping_method = checkout_data.get('shipping_method')
    shipping_method_label = 'Express' if str(shipping_method).upper() == 'EXP' else 'Reguler'

    midtrans_payment_slug = getattr(settings, 'MIDTRANS_PAYMENT_METHOD_SLUG', 'midtrans')
    is_midtrans_payment = payment_method.slug.lower() == (midtrans_payment_slug or '').lower()
    doku_payment_slug = getattr(settings, 'DOKU_PAYMENT_METHOD_SLUG', 'doku')
    is_doku_payment = payment_method.slug.lower() == (doku_payment_slug or '').lower()

    context = {
        'cart': cart,
        'selected_items': selected_items,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'total': total,
        'discount_amount': discount_amount,
        'discount_display': _format_rupiah(discount_amount),
        'discount_type_label': discount_type_label,
        'subtotal_display': _format_rupiah(subtotal),
        'shipping_cost_display': _format_rupiah(shipping_cost),
        'total_display': _format_rupiah(total),
        'payment_method': payment_method.slug,
        'payment_method_display': payment_method.name,
        'payment_method_button_label': payment_method.checkout_button_label,
        'payment_method_additional_info': payment_method.additional_info,
        'is_midtrans_payment': is_midtrans_payment,
        'midtrans_payment_slug': midtrans_payment_slug,
        'is_doku_payment': is_doku_payment,
        'doku_payment_slug': doku_payment_slug,
        'shipping_method_label': shipping_method_label,
        'eta': checkout_data.get('eta'),
        'shipping_address': shipping_address,
        'discount_code': discount_code,
        'subtotal_raw': subtotal,
        'shipping_cost_raw': shipping_cost,
        'discount_amount_raw': discount_amount,
        'total_raw': total,
        'MIDTRANS_CLIENT_KEY': settings.MIDTRANS_CLIENT_KEY,
        'MIDTRANS_SNAP_JS_URL': settings.MIDTRANS_SNAP_JS_URL,
        'payment_create_snap_token_url': reverse('payment:create_snap_token'),
        'payment_finish_url': reverse('payment:finish'),
        'payment_create_doku_checkout_url': reverse('payment:create_doku_checkout'),
        'payment_doku_return_url': reverse('payment:doku_return'),
        'order_complete_url': reverse('core:order_list'),
    }
    return render(request, 'core/checkout_review.html', context)


@login_required
def place_order(request):
    """Process order placement with shipping integration - only selected items"""
    if request.method != 'POST':
        return redirect('core:checkout')

    cart = _get_active_cart(request)

    # Get only selected items
    selected_items_qs = cart.items.filter(is_selected=True).select_related('product')

    if not selected_items_qs.exists():
        messages.error(request, 'Pilih minimal 1 item untuk checkout.')
        return redirect('core:cart')

    selected_items, selected_quantities = _prepare_selected_cart_items(selected_items_qs)

    # Validate stock availability for selected items only
    for item in selected_items:
        quantity = selected_quantities.get(item.pk, item.quantity)
        if item.product.stock < quantity:
            messages.error(request, f'Stok {item.product.name} tidak mencukupi.')
            return redirect('core:cart')

    # Validate shipping data (JANGAN PERCAYA DATA DARI CLIENT!)
    district_id = request.POST.get('district_id')
    service = request.POST.get('shipping_service')  # 'REG' or 'EXP'

    try:
        is_valid, error_message = validate_shipping_data(district_id, service)
        if not is_valid:
            messages.error(request, f'Data pengiriman tidak valid: {error_message}')
            return redirect('core:checkout')

        # Re-lookup shipping cost from database (SERVER-SIDE VALIDATION)
        # Use selected items total only
        subtotal = cart.get_selected_total()
        shipping_cost, eta, district_name = calculate_shipping_cost(
            district_id, service, subtotal
        )

    except Exception as e:
        messages.error(request, f'Terjadi kesalahan dalam perhitungan ongkir: {str(e)}')
        return redirect('core:checkout')

    order_number = f'ORD-{uuid.uuid4().hex[:8].upper()}'
    total = subtotal + shipping_cost
    service_label = 'Express' if str(service).upper() == 'EXP' else 'Reguler'

    with transaction.atomic():
        order = create_order_from_checkout(
            user=request.user,
            cart=cart,
            selected_items=selected_items,
            selected_quantities=selected_quantities,
            order_number=order_number,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            total=total,
            shipping_full_name=request.POST.get('full_name', ''),
            shipping_email=request.POST.get('email', ''),
            shipping_phone=request.POST.get('phone', ''),
            shipping_address_text=request.POST.get('street', ''),
            shipping_city='Makassar',
            shipping_postal_code=request.POST.get('postal_code', ''),
            courier_service=service,
            district_name=district_name,
            eta=eta,
            notes=request.POST.get('notes', ''),
            shipping_service_name=service_label,
        )

    messages.success(request, f'Pesanan berhasil dibuat! Nomor pesanan: {order_number}')
    return redirect('core:order_detail', order_number=order_number)


@login_required
def place_order_from_address(request):
    """Place order from new multi-step checkout"""
    if request.method != 'POST':
        # Get data from POST or sessionStorage
        # For now, redirect to checkout
        return redirect('core:checkout')

    cart = _get_active_cart(request)

    # Get only selected items
    selected_items_qs = cart.items.filter(is_selected=True).select_related('product')

    if not selected_items_qs.exists():
        messages.error(request, 'Pilih minimal 1 item untuk checkout.')
        return redirect('core:cart')

    selected_items, selected_quantities = _prepare_selected_cart_items(selected_items_qs)

    # Validate stock availability for selected items only
    for item in selected_items:
        quantity = selected_quantities.get(item.pk, item.quantity)
        if item.product.stock < quantity:
            messages.error(request, f'Stok {item.product.name} tidak mencukupi.')
            return redirect('core:cart')

    # Get shipping data from POST
    address_id = request.POST.get('address_id')
    service = request.POST.get('courier_service')

    try:
        # Get address
        address = get_object_or_404(
            Address,
            id=address_id,
            user=request.user,
            is_deleted=False,
        )

        # Validate shipping data
        is_valid, error_message = validate_shipping_data(address.district.id, service)
        if not is_valid:
            messages.error(request, f'Data pengiriman tidak valid: {error_message}')
            return redirect('core:checkout')

        # Calculate shipping cost from database
        subtotal = cart.get_selected_total()
        shipping_cost, eta, district_name = calculate_shipping_cost(
            address.district.id, service, subtotal
        )

    except Exception as e:
        messages.error(request, f'Terjadi kesalahan: {str(e)}')
        return redirect('core:checkout')

    order_number = f'ORD-{uuid.uuid4().hex[:8].upper()}'
    total = subtotal + shipping_cost
    service_label = 'Express' if str(service).upper() == 'EXP' else 'Reguler'

    with transaction.atomic():
        order = create_order_from_checkout(
            user=request.user,
            cart=cart,
            selected_items=selected_items,
            selected_quantities=selected_quantities,
            order_number=order_number,
            subtotal=subtotal,
            shipping_cost=shipping_cost,
            total=total,
            shipping_full_name=address.full_name,
            shipping_email=request.user.email,
            shipping_phone=address.phone,
            shipping_address_text=address.get_full_address(),
            shipping_city=address.city,
            shipping_postal_code=address.postal_code,
            courier_service=service,
            district_name=district_name,
            eta=eta,
            notes=request.POST.get('notes', ''),
            shipping_address_obj=address,
            shipping_service_name=service_label,
        )

    messages.success(request, f'Pesanan berhasil dibuat! Nomor pesanan: {order_number}')
    return redirect('core:order_detail', order_number=order_number)


# Order Views
@login_required
def order_list(request):
    """List user's orders"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    orders_qs = Order.objects.filter(user=request.user).order_by('-created_at')
    orders = list(orders_qs)
    expired_orders = [order for order in orders if order.status == 'pending' and order.is_payment_overdue()]

    if expired_orders:
        for order in expired_orders:
            cancel_order_due_to_timeout(order)
        orders = list(Order.objects.filter(user=request.user).order_by('-created_at'))

    context = {
        'profile': profile,
        'orders': orders,
        'active_tab': 'orders',
    }
    return render(request, 'core/order_list.html', context)


@login_required
def order_detail(request, order_number):
    """Order detail page"""
    order = get_object_or_404(
        Order.objects.select_related('shipping_address').prefetch_related('items__product'),
        order_number=order_number,
        user=request.user,
    )

    if cancel_order_due_to_timeout(order):
        order.refresh_from_db()

    order_items = list(order.items.all())
    product_ids = [item.product_id for item in order_items if item.product_id]

    testimonials = Testimonial.objects.filter(
        user=request.user,
        product_id__in=product_ids,
    )
    testimonials_map = {testimonial.product_id: testimonial for testimonial in testimonials}

    for item in order_items:
        item.existing_testimonial = testimonials_map.get(item.product_id)

    payment_is_pending = order.status == 'pending' and bool(order.payment_method)
    payment_is_active = payment_is_pending and not order.is_payment_overdue()
    midtrans_payment_slug = getattr(settings, 'MIDTRANS_PAYMENT_METHOD_SLUG', 'midtrans')
    doku_payment_slug = getattr(settings, 'DOKU_PAYMENT_METHOD_SLUG', 'doku')

    context = {
        'order': order,
        'order_items': order_items,
        'order_can_review': order.status == 'delivered',
        'testimonial_form': TestimonialForm(),
        'show_payment_button': payment_is_active,
        'midtrans_payment_slug': midtrans_payment_slug,
        'doku_payment_slug': doku_payment_slug,
        'payment_finish_url': reverse('payment:finish'),
        'payment_order_midtrans_token_url': reverse(
            'payment:order_create_snap_token', args=[order.order_number]
        ),
        'payment_order_doku_checkout_url': reverse(
            'payment:order_create_doku_checkout', args=[order.order_number]
        ),
        'MIDTRANS_CLIENT_KEY': settings.MIDTRANS_CLIENT_KEY,
        'MIDTRANS_SNAP_JS_URL': settings.MIDTRANS_SNAP_JS_URL,
    }
    return render(request, 'core/order_detail.html', context)


@login_required
def submit_testimonial(request, order_number, item_id):
    """Allow a customer to submit a testimonial for a purchased product."""

    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        order_number=order_number,
        user=request.user,
    )

    order_items_qs = order.items.select_related('product')
    order_item = get_object_or_404(order_items_qs, pk=item_id)

    if request.method != 'POST':
        return redirect('core:order_detail', order_number=order_number)

    if order.status != 'delivered':
        messages.warning(request, 'Penilaian hanya dapat diberikan untuk pesanan yang telah selesai.')
        return redirect('core:order_detail', order_number=order_number)

    if order_item.product is None:
        messages.error(request, 'Produk ini sudah tidak tersedia sehingga tidak dapat dinilai.')
        return redirect('core:order_detail', order_number=order_number)

    if Testimonial.objects.filter(user=request.user, product=order_item.product).exists():
        messages.info(request, 'Anda sudah memberikan penilaian untuk produk ini.')
        return redirect('core:order_detail', order_number=order_number)

    form = TestimonialForm(request.POST, request.FILES)

    if form.is_valid():
        testimonial = form.save(commit=False)
        testimonial.user = request.user
        testimonial.product = order_item.product
        testimonial.is_approved = True
        testimonial.save()
        messages.success(request, 'Terima kasih! Penilaian Anda telah dikirim dan langsung ditampilkan.')
    else:
        error_messages = ' '.join([' '.join(errors) for errors in form.errors.values()])
        if error_messages:
            messages.error(request, f'Gagal mengirim penilaian. {error_messages}')
        else:
            messages.error(request, 'Gagal mengirim penilaian. Silakan coba lagi.')

    return redirect('core:order_detail', order_number=order_number)


# Authentication Views
def register_view(request):
    """User registration with email verification"""
    if request.user.is_authenticated:
        return redirect('catalog:home')

    if request.method == 'POST':
        form = CustomUserRegistrationForm(request.POST)
        if form.is_valid():
            # Save user and profile
            user = form.save()

            # Create verification code
            ip_address = request.META.get('REMOTE_ADDR')
            verification = EmailVerification.create_verification(user, ip_address)

            # Send verification email
            if send_verification_email(user, verification):
                # Store user_id in session for verification step
                request.session['pending_verification_user_id'] = user.id
                request.session['verification_id'] = verification.id
                messages.success(request, f'Akun berhasil dibuat! Kode verifikasi telah dikirim ke {user.email}')
                return redirect('core:verify_email')
            else:
                messages.error(request, 'Gagal mengirim kode verifikasi. Silakan hubungi admin.')
                # Still allow registration to complete
                send_welcome_email(user)
                login(request, user)
                return redirect('catalog:home')
    else:
        form = CustomUserRegistrationForm()

    context = {'form': form}
    return render(request, 'core/register.html', context)


def login_view(request):
    """User login"""
    if request.user.is_authenticated:
        return redirect('catalog:home')

    entered_username = ''
    remember_me = False

    if request.method == 'POST':
        # Try to authenticate with username or email
        username_or_email = request.POST.get('username')
        password = request.POST.get('password')
        username_or_email = (username_or_email or '').strip()
        entered_username = username_or_email
        remember_me = bool(request.POST.get('remember_me'))

        if not username_or_email or not password:
            messages.error(request, 'Silakan masukkan username/email dan password Anda.')
            context = {
                'form': AuthenticationForm(),
                'entered_username': entered_username,
                'remember_me': remember_me,
            }
            return render(request, 'core/login.html', context)

        # Try to find user by username or email
        from django.contrib.auth.models import User
        try:
            if '@' in username_or_email:
                user = User.objects.get(email=username_or_email)
                username = user.username
            else:
                username = username_or_email
        except User.DoesNotExist:
            messages.error(request, 'Username atau email tidak ditemukan.')
            context = {
                'form': AuthenticationForm(),
                'entered_username': entered_username,
                'remember_me': remember_me,
            }
            return render(request, 'core/login.html', context)

        # Authenticate
        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)
            messages.success(request, 'Login Berhasil')
            next_url = request.GET.get('next', 'catalog:home')
            return redirect(next_url)
        else:
            messages.error(request, 'Username/email atau password salah.')

    form = AuthenticationForm()
    context = {
        'form': form,
        'entered_username': entered_username,
        'remember_me': remember_me,
    }
    return render(request, 'core/login.html', context)


def verify_email_view(request):
    """Verify email with OTP code after registration"""
    # Check if there's a pending verification
    user_id = request.session.get('pending_verification_user_id')
    verification_id = request.session.get('verification_id')

    if not user_id or not verification_id:
        messages.error(request, 'Sesi verifikasi tidak valid. Silakan daftar kembali.')
        return redirect('core:register')

    if request.method == 'POST':
        code = request.POST.get('code', '').strip()

        try:
            verification = EmailVerification.objects.get(id=verification_id)

            if verification.is_valid():
                if verification.code == code:
                    # Code is correct, mark as used
                    verification.mark_as_used()

                    # Log the user in
                    from django.contrib.auth.models import User
                    user = User.objects.get(id=user_id)

                    # Send welcome email after successful verification
                    send_welcome_email(user)

                    # Log the user in
                    login(request, user)

                    # Clear session data
                    del request.session['pending_verification_user_id']
                    del request.session['verification_id']

                    messages.success(request, f'Email berhasil diverifikasi! Selamat datang, {user.first_name}!')
                    return redirect('catalog:home')
                else:
                    messages.error(request, 'Kode verifikasi salah. Silakan coba lagi.')
            else:
                messages.error(request, 'Kode verifikasi sudah kadaluarsa. Silakan minta kode baru.')
                # Don't delete session, allow resend

        except EmailVerification.DoesNotExist:
            messages.error(request, 'Verifikasi tidak ditemukan. Silakan daftar kembali.')
            return redirect('core:register')

    # Get user email for display
    from django.contrib.auth.models import User
    user = User.objects.get(id=user_id)
    masked_email = user.email[:3] + '***@' + user.email.split('@')[1]

    context = {
        'masked_email': masked_email,
        'is_registration': True,
    }
    return render(request, 'core/verify_email.html', context)


def resend_verification_code(request):
    """Resend verification code for email verification"""
    user_id = request.session.get('pending_verification_user_id')

    if not user_id:
        messages.error(request, 'Sesi verifikasi tidak valid.')
        return redirect('core:register')

    from django.contrib.auth.models import User
    user = User.objects.get(id=user_id)

    # Create new verification code
    ip_address = request.META.get('REMOTE_ADDR')
    verification = EmailVerification.create_verification(user, ip_address)

    # Send email
    if send_verification_email(user, verification):
        # Update session with new verification_id
        request.session['verification_id'] = verification.id
        messages.success(request, 'Kode verifikasi baru telah dikirim ke email Anda.')
    else:
        messages.error(request, 'Gagal mengirim kode verifikasi. Silakan coba lagi.')

    return redirect('core:verify_email')


@login_required
def logout_view(request):
    """User logout"""
    logout(request)
    messages.success(request, 'Anda berhasil logout.')
    return redirect('catalog:home')


# Profile Views
@login_required
def profile_view(request):
    """User profile page with address information"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    # Get all shipping addresses
    user_addresses = Address.objects.filter(
        user=request.user,
        is_deleted=False,
    ).select_related('district').annotate(
        used_in_orders=Count('order', distinct=True),
    ).order_by('-is_default', '-created_at')

    # Get all districts for the add address modal
    districts = District.objects.filter(is_active=True).order_by('name')

    context = {
        'profile': profile,
        'user': request.user,
        'user_addresses': user_addresses,
        'districts': districts,
        'active_tab': 'profile',
    }
    return render(request, 'core/profile.html', context)


@login_required
def profile_settings(request):
    """User profile settings page"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        # Update user info
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()

        # Handle photo upload
        if request.FILES.get('photo'):
            # Delete old photo if exists
            if profile.photo:
                profile.photo.delete()
            profile.photo = request.FILES['photo']

        # Handle photo removal
        if request.POST.get('remove_photo') == '1':
            if profile.photo:
                profile.photo.delete()
                profile.photo = None

        # Update profile info
        profile.phone = request.POST.get('phone', '')
        profile.address = request.POST.get('address', '')
        profile.city = request.POST.get('city', '')
        profile.postal_code = request.POST.get('postal_code', '')
        profile.gender = request.POST.get('gender', '')

        birth_date = request.POST.get('birth_date', '')
        if birth_date:
            profile.birth_date = birth_date

        profile.save()
        messages.success(request, 'Profil berhasil diperbarui.')
        return redirect('core:profile_settings')

    context = {
        'profile': profile,
        'user': request.user,
        'active_tab': 'settings',
    }
    return render(request, 'core/profile_settings.html', context)


@login_required
def change_password(request):
    """Change user password"""
    from django.contrib.auth import update_session_auth_hash

    if request.method == 'POST':
        old_password = request.POST.get('old_password')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')

        # Check old password
        if not request.user.check_password(old_password):
            messages.error(request, 'Password lama salah.')
            return redirect('core:profile_settings')

        # Check if new passwords match
        if new_password1 != new_password2:
            messages.error(request, 'Password baru tidak cocok.')
            return redirect('core:profile_settings')

        # Check password length
        if len(new_password1) < 8:
            messages.error(request, 'Password baru minimal 8 karakter.')
            return redirect('core:profile_settings')

        # Update password
        request.user.set_password(new_password1)
        request.user.save()

        # Update session to prevent logout
        update_session_auth_hash(request, request.user)

        messages.success(request, 'Password berhasil diubah.')
        return redirect('core:profile_settings')

    return redirect('core:profile_settings')


@login_required
def profile_address_edit(request):
    """Edit primary shipping address for RajaOngkir integration"""
    addr = Address.objects.filter(user=request.user, is_default=True, is_deleted=False).first()
    if not addr:
        addr = Address(
            user=request.user,
            full_name=request.user.get_full_name() or request.user.username
        )

    if request.method == 'POST':
        form = AddressForm(request.POST, instance=addr)
        if form.is_valid():
            obj = form.save(commit=False)
            # Untuk sekarang provinsi kita set manual ke Sulawesi Selatan
            if not obj.province_name:
                obj.province_name = 'Sulawesi Selatan'
            obj.user = request.user
            obj.is_default = True
            obj.save()
            messages.success(request, 'Alamat pengiriman berhasil diperbarui.')
            return redirect('core:profile')
    else:
        form = AddressForm(instance=addr)

    context = {
        'form': form,
        'address': addr,
    }
    return render(request, 'core/profile_address_edit.html', context)


# Watchlist Views
@login_required
def watchlist_view(request):
    """Display user's watchlist"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    watchlist_items = (
        Watchlist.objects.filter(user=request.user)
        .select_related('product')
        .order_by('-added_at')
    )

    context = {
        'profile': profile,
        'watchlist_items': watchlist_items,
        'active_tab': 'watchlist',
    }
    return render(request, 'core/watchlist.html', context)


@login_required
def notifications_view(request):
    """Display user notifications placeholder"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    notifications = []

    context = {
        'profile': profile,
        'notifications': notifications,
        'active_tab': 'notifications',
    }
    return render(request, 'core/notifications.html', context)


@login_required
def add_to_watchlist(request, product_id):
    """Add product to watchlist"""
    product = get_object_or_404(Product, id=product_id)

    watchlist_item, created = Watchlist.objects.get_or_create(
        user=request.user,
        product=product
    )

    if created:
        messages.success(request, f'{product.name} berhasil ditambahkan ke watchlist.')
    else:
        messages.info(request, f'{product.name} sudah ada di watchlist Anda.')

    return redirect(request.META.get('HTTP_REFERER', 'catalog:home'))


@login_required
def remove_from_watchlist(request, watchlist_id):
    """Remove item from watchlist"""
    watchlist_item = get_object_or_404(Watchlist, id=watchlist_id, user=request.user)
    product_name = watchlist_item.product.name
    watchlist_item.delete()
    messages.success(request, f'{product_name} berhasil dihapus dari watchlist.')
    return redirect('core:watchlist')


@login_required
@require_POST
def toggle_watchlist(request, product_id):
    """Toggle the watchlist state for a given product."""
    product = get_object_or_404(Product, id=product_id)
    watchlist_item, created = Watchlist.objects.get_or_create(
        user=request.user,
        product=product
    )

    if created:
        added = True
        message_text = f'{product.name} berhasil ditambahkan ke watchlist.'
    else:
        watchlist_item.delete()
        added = False
        message_text = f'{product.name} dihapus dari watchlist.'

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'added': added,
            'message': message_text,
        })

    if added:
        messages.success(request, message_text)
    else:
        messages.info(request, message_text)

    return redirect(request.META.get('HTTP_REFERER', product.get_absolute_url()))


@login_required
@require_POST
def set_shipping_method(request):
    """Hitung ongkir berdasarkan alamat & simpan pilihan pengguna."""

    def format_rupiah(value: Decimal) -> str:
        value = Decimal(value or 0)
        return f"Rp {number_format(value, decimal_pos=0, force_grouping=True)}"

    try:
        data = json.loads(request.body.decode('utf-8'))
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'message': 'Data tidak valid.'}, status=400)

    method = str(data.get('method', '')).upper()
    address_id = data.get('address_id')

    if method not in {'REG', 'EXP'} or not address_id:
        return JsonResponse({'success': False, 'message': 'Metode atau alamat tidak valid.'}, status=400)

    try:
        address = Address.objects.select_related('district').get(
            id=address_id,
            user=request.user,
            is_deleted=False,
        )
    except Address.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Alamat tidak ditemukan.'}, status=404)

    district = address.district
    if not district or not district.is_active:
        return JsonResponse({'success': False, 'message': 'Kecamatan tidak aktif.'}, status=400)

    if method == 'EXP':
        shipping_cost = Decimal(district.exp_cost or 0)
        eta = district.eta_exp
    else:
        method = 'REG'
        shipping_cost = Decimal(district.reg_cost or 0)
        eta = district.eta_reg

    cart = Cart.objects.filter(user=request.user).first()
    if not cart:
        return JsonResponse({'success': False, 'message': 'Keranjang tidak ditemukan.'}, status=400)

    subtotal = Decimal(cart.get_selected_total() or 0)
    total = subtotal + shipping_cost

    checkout_data = request.session.get('checkout', {})
    checkout_data.update({
        'address_id': address.id,
        'shipping_method': method,
        'shipping_cost': str(shipping_cost),
        'eta': eta,
    })
    request.session['checkout'] = checkout_data
    request.session.modified = True

    return JsonResponse({
        'success': True,
        'method': method,
        'shipping_cost': float(shipping_cost),
        'subtotal': float(subtotal),
        'total': float(total),
        'eta': eta,
        'shipping_cost_display': format_rupiah(shipping_cost),
        'subtotal_display': format_rupiah(subtotal),
        'total_display': format_rupiah(total),
    })
