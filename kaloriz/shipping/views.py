from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models.deletion import ProtectedError
from decimal import Decimal
from .models import District, Address


def format_currency(amount):
    """Format Decimal to Indonesian Rupiah string."""
    value = Decimal(amount or 0)
    normalized = value.quantize(Decimal('1')) if value == value.to_integral() else value
    return f"Rp {normalized:,.0f}".replace(',', '.')


@require_GET
def get_districts(request):
    """
    JSON endpoint untuk mendapatkan daftar kecamatan aktif

    GET /shipping/districts/

    Response:
    {
        "success": true,
        "districts": [
            {"id": 1, "name": "Panakkukang"},
            ...
        ]
    }
    """
    try:
        districts = District.objects.filter(is_active=True).values('id', 'name')

        return JsonResponse({
            'success': True,
            'districts': list(districts)
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_GET
def get_shipping_quotes(request):
    """
    JSON endpoint untuk mendapatkan tarif pengiriman berdasarkan kecamatan

    GET /shipping/quotes/?district_id=1

    Response:
    {
        "success": true,
        "quotes": [
            {
                "service": "REG",
                "label": "Reguler",
                "cost": 10000.00,
                "cost_formatted": "Rp 10.000",
                "eta": "2-3 hari kerja"
            },
            {
                "service": "EXP",
                "label": "Express",
                "cost": 18000.00,
                "cost_formatted": "Rp 18.000",
                "eta": "1 hari kerja"
            }
        ]
    }
    """
    district_id = request.GET.get('district_id')

    if not district_id:
        return JsonResponse({
            'success': False,
            'error': 'Parameter district_id diperlukan'
        }, status=400)

    try:
        district = District.objects.get(id=district_id, is_active=True)

        # Build response dengan 2 opsi: Reguler & Express
        quotes = [
            {
                'service': 'REG',
                'label': 'Reguler',
                'cost': float(district.reg_cost or 0),
                'cost_formatted': format_currency(district.reg_cost),
                'eta': district.eta_reg
            },
            {
                'service': 'EXP',
                'label': 'Express',
                'cost': float(district.exp_cost or 0),
                'cost_formatted': format_currency(district.exp_cost),
                'eta': district.eta_exp
            }
        ]

        return JsonResponse({
            'success': True,
            'district_name': district.name,
            'quotes': quotes
        })

    except District.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Kecamatan tidak ditemukan'
        }, status=404)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def calculate_shipping_cost(district_id, service, subtotal=Decimal('0')):
    """
    Helper function untuk menghitung biaya pengiriman
    Server-side validation: JANGAN PERCAYA ANGKA DARI CLIENT!

    Args:
        district_id: ID kecamatan tujuan
        service: 'REG' atau 'EXP'
        subtotal: Subtotal order untuk promo gratis ongkir

    Returns:
        tuple: (cost, eta, district_name) atau (None, None, None) jika error
    """
    try:
        # Re-lookup tarif dari database (PENTING: validasi server-side)
        district = District.objects.get(id=district_id, is_active=True)

        # Pilih tarif berdasarkan service
        if service == 'REG':
            cost = district.reg_cost
            eta = district.eta_reg
        elif service == 'EXP':
            cost = district.exp_cost
            eta = district.eta_exp
        else:
            return None, None, None

        # PROMO: Gratis ongkir jika subtotal >= 100.000
        # Uncomment baris berikut untuk mengaktifkan promo:
        # if subtotal >= Decimal('100000'):
        #     cost = Decimal('0')
        #     eta = f"{eta} (GRATIS ONGKIR!)"

        return cost, eta, district.name

    except District.DoesNotExist:
        return None, None, None
    except Exception:
        return None, None, None


def validate_shipping_data(district_id, service):
    """
    Validasi data pengiriman dari form

    Returns:
        tuple: (is_valid, error_message)
    """
    if not district_id:
        return False, 'Kecamatan harus dipilih'

    if service not in ['REG', 'EXP']:
        return False, 'Metode pengiriman tidak valid'

    # Check if district exists and active
    try:
        district = District.objects.get(id=district_id, is_active=True)
    except District.DoesNotExist:
        return False, 'Kecamatan tidak ditemukan'

    return True, None


# Address Management Views
@login_required
def add_address(request):
    """Add new shipping address"""
    if request.method == 'POST':
        # Manual processing
        full_name = request.POST.get('full_name')
        phone = request.POST.get('phone')
        province = request.POST.get('province', 'Sulawesi Selatan')
        city = request.POST.get('city', 'Makassar')
        district_id = request.POST.get('district_id')
        postal_code = request.POST.get('postal_code')
        street_name = request.POST.get('street_name')
        detail = request.POST.get('detail', '')
        label = request.POST.get('label', 'Rumah')
        is_default = request.POST.get('is_default') == 'on'

        try:
            district = District.objects.get(id=district_id, is_active=True)

            # Create address
            address = Address.objects.create(
                user=request.user,
                full_name=full_name,
                phone=phone,
                province=province,
                city=city,
                district=district,
                postal_code=postal_code,
                street_name=street_name,
                detail=detail,
                label=label,
                is_default=is_default
            )

            # If this is set as default, unset other defaults
            if is_default:
                Address.objects.filter(
                    user=request.user,
                    is_default=True,
                    is_deleted=False
                ).exclude(id=address.id).update(is_default=False)

            messages.success(request, 'Alamat berhasil ditambahkan.')
        except District.DoesNotExist:
            messages.error(request, 'Kecamatan tidak valid.')
        except Exception as e:
            messages.error(request, f'Gagal menambahkan alamat: {str(e)}')

    # Redirect back to where user came from
    referer = request.META.get('HTTP_REFERER', '')
    if 'profile' in referer:
        return redirect('core:profile')
    else:
        return redirect('core:checkout')


@login_required
def edit_address(request, address_id):
    """Edit shipping address"""
    address = get_object_or_404(
        Address,
        id=address_id,
        user=request.user,
        is_deleted=False,
    )

    if request.method == 'POST':
        # Manual processing instead of using form
        address.full_name = request.POST.get('full_name')
        address.phone = request.POST.get('phone')
        address.province = request.POST.get('province', 'Sulawesi Selatan')
        address.city = request.POST.get('city', 'Makassar')

        district_id = request.POST.get('district_id')
        if district_id:
            try:
                address.district = District.objects.get(id=district_id, is_active=True)
            except District.DoesNotExist:
                messages.error(request, 'Kecamatan tidak valid.')
                return redirect(request.META.get('HTTP_REFERER', 'core:profile'))

        address.postal_code = request.POST.get('postal_code')
        address.street_name = request.POST.get('street_name')
        address.detail = request.POST.get('detail', '')
        address.label = request.POST.get('label', 'Rumah')

        # Handle default address
        is_default = request.POST.get('is_default') == 'on'
        if is_default:
            Address.objects.filter(
                user=request.user,
                is_default=True,
                is_deleted=False
            ).exclude(id=address_id).update(is_default=False)
            address.is_default = True
        else:
            address.is_default = False

        address.save()
        messages.success(request, 'Alamat berhasil diperbarui.')
        return redirect('core:profile')

    districts = District.objects.filter(is_active=True).order_by('name')
    context = {
        'address': address,
        'districts': districts,
    }
    return render(request, 'shipping/edit_address.html', context)


@login_required
def delete_address(request, address_id):
    """Delete shipping address"""
    if request.method == 'POST':
        address = get_object_or_404(
            Address,
            id=address_id,
            user=request.user,
            is_deleted=False,
        )
        try:
            address.delete()
        except ProtectedError:
            messages.error(
                request,
                'Alamat tidak bisa dihapus karena dipakai pada pesanan. Anda dapat mengarsipkannya agar tidak muncul di daftar.',
            )
        else:
            messages.success(request, 'Alamat berhasil dihapus.')

    return redirect('core:profile')


@login_required
def archive_address(request, address_id):
    """Soft delete shipping address by marking it as archived."""
    if request.method == 'POST':
        address = get_object_or_404(
            Address,
            id=address_id,
            user=request.user,
            is_deleted=False,
        )
        address.is_default = False
        address.is_deleted = True
        address.save(update_fields=['is_default', 'is_deleted', 'updated_at'])

        checkout_data = request.session.get('checkout', {})
        if checkout_data.get('address_id') == address.id:
            for key in ['address_id', 'shipping_method', 'shipping_cost', 'eta']:
                checkout_data.pop(key, None)
            request.session['checkout'] = checkout_data
            request.session.modified = True

        messages.success(request, 'Alamat diarsipkan. Alamat ini tidak akan tampil saat checkout.')

    return redirect('core:profile')


@login_required
def set_default_address(request, address_id):
    """Set address as default"""
    if request.method == 'POST':
        address = get_object_or_404(
            Address,
            id=address_id,
            user=request.user,
            is_deleted=False,
        )

        # Unset other defaults
        Address.objects.filter(
            user=request.user,
            is_default=True,
            is_deleted=False
        ).exclude(id=address_id).update(is_default=False)

        # Set this as default
        address.is_default = True
        address.save(update_fields=['is_default', 'updated_at'])

        messages.success(request, 'Alamat utama berhasil diubah.')

    return redirect(request.META.get('HTTP_REFERER', 'core:profile'))
