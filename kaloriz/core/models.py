from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from catalog.models import Product
from decimal import Decimal
import random
from datetime import timedelta
from django.utils import timezone
from django.utils.text import slugify
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce


class PaymentMethod(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nama Metode")
    slug = models.SlugField(max_length=100, unique=True, verbose_name="Slug")
    SERVICE_STATUS_CHOICES = [
        ("available", "Tersedia"),
        ("disrupted", "Sedang Gangguan"),
    ]

    tagline = models.CharField(max_length=150, blank=True, verbose_name="Tagline")
    description = models.TextField(blank=True, verbose_name="Deskripsi")
    additional_info = models.TextField(blank=True, verbose_name="Informasi Tambahan")
    service_status = models.CharField(
        max_length=20,
        choices=SERVICE_STATUS_CHOICES,
        default="available",
        verbose_name="Status Layanan",
        help_text="Gunakan 'Sedang Gangguan' untuk menampilkan notifikasi masalah di halaman checkout.",
    )
    button_label = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Teks Tombol Checkout",
        help_text="Kosongkan untuk menggunakan teks default 'Checkout'",
    )
    logo = models.ImageField(
        upload_to='payment_methods/',
        blank=True,
        null=True,
        verbose_name="Logo",
        help_text="Opsional, tampilkan logo di daftar metode pembayaran",
    )
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    display_order = models.PositiveIntegerField(
        default=0,
        verbose_name="Urutan Tampil",
        help_text="Metode dengan angka lebih kecil akan tampil lebih dulu",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui")

    class Meta:
        verbose_name = "Metode Pembayaran"
        verbose_name_plural = "Metode Pembayaran"
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def checkout_button_label(self):
        return self.button_label or 'Checkout'

    @property
    def is_available(self):
        return self.service_status == "available"


class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carts', verbose_name="Pengguna")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Keranjang"
        verbose_name_plural = "Keranjang"

    def __str__(self):
        return f"Keranjang - {self.user.username}"

    def get_total(self):
        """Calculate total price of all items in cart"""
        return sum(item.get_subtotal() for item in self.items.all())

    def get_selected_total(self):
        """Calculate total price of selected items only"""
        price_expression = Coalesce('product__discount_price', 'product__price')
        line_total = ExpressionWrapper(
            F('quantity') * price_expression,
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        total = self.items.filter(is_selected=True).aggregate(total=Sum(line_total))['total']
        return total or Decimal('0')

    def get_total_items(self):
        """Get total number of items in cart"""
        return sum(item.quantity for item in self.items.all())

    def get_selected_items_count(self):
        """Get count of selected items"""
        return self.items.filter(is_selected=True).count()

    def get_selected_items_quantity(self):
        """Get total quantity for selected cart items"""
        total = self.items.filter(is_selected=True).aggregate(total=Sum('quantity'))['total']
        return total or 0


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items', verbose_name="Keranjang")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Produk")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Jumlah")
    is_selected = models.BooleanField(default=True, verbose_name="Dipilih untuk Checkout")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Item Keranjang"
        verbose_name_plural = "Item Keranjang"
        unique_together = ['cart', 'product']

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"

    def get_subtotal(self):
        """Calculate subtotal for this item"""
        return self.product.get_display_price() * self.quantity


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Menunggu Pembayaran'),
        ('paid', 'Dibayar'),
        ('processing', 'Diproses'),
        ('shipped', 'Dikirim'),
        ('delivered', 'Selesai'),
        ('cancelled', 'Dibatalkan'),
    ]

    REGULAR_COURIERS = [
        ('JNE', 'JNE'),
        ('JNT', 'J&T Express'),
        ('SICEPAT', 'SiCepat Ekspres'),
        ('POS', 'Pos Indonesia'),
        ('TIKI', 'TIKI'),
        ('LION', 'Lion Parcel'),
        ('ANTERAJA', 'Anteraja'),
        ('SAPX', 'SAPX Express'),
    ]
    EXPRESS_COURIERS = [
        ('GOSEND', 'Gosend'),
        ('GRAB', 'GrabExpress'),
    ]
    SHIPPING_PROVIDER_CHOICES = REGULAR_COURIERS + EXPRESS_COURIERS

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', verbose_name="Pengguna")
    order_number = models.CharField(max_length=100, unique=True, verbose_name="Nomor Pesanan")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    payment_method = models.CharField(max_length=100, blank=True, verbose_name="Metode Pembayaran")
    payment_method_display = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Nama Metode Pembayaran",
        help_text="Label yang ditampilkan kepada pengguna",
    )

    # Shipping information (legacy fields)
    full_name = models.CharField(max_length=200, verbose_name="Nama Lengkap")
    email = models.EmailField(verbose_name="Email")
    phone = models.CharField(max_length=20, verbose_name="Nomor Telepon")
    address = models.TextField(verbose_name="Alamat")
    city = models.CharField(max_length=100, verbose_name="Kota")
    postal_code = models.CharField(max_length=10, verbose_name="Kode Pos")

    # === FIELD PENGIRIMAN UNTUK RAJAONGKIR ===
    shipping_address = models.ForeignKey(
        'shipping.Address',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Alamat Pengiriman",
        help_text="Alamat tujuan pengiriman"
    )
    selected_courier = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Kurir Dipilih",
        help_text="jne/jnt/sicepat/tiki/pos/anteraja"
    )
    selected_service_name = models.CharField(
        max_length=80,
        blank=True,
        verbose_name="Layanan Kurir",
        help_text="REG/YES/OKE/etc"
    )
    shipping_provider = models.CharField(
        max_length=20,
        choices=SHIPPING_PROVIDER_CHOICES,
        blank=True,
        verbose_name="Kurir Pengiriman",
        help_text="Pilih kurir berdasarkan layanan pengiriman",
    )
    total_weight_gram = models.PositiveIntegerField(
        default=1000,
        verbose_name="Total Berat (gram)",
        help_text="Total berat pesanan dalam gram"
    )

    # Order totals
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Subtotal")
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Ongkir")
    total = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Total")

    # Additional info
    notes = models.TextField(blank=True, verbose_name="Catatan")
    tracking_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Nomor Resi",
        help_text="Masukkan nomor resi pengiriman",
    )
    tracking_url = models.URLField(
        blank=True,
        verbose_name="Link Pelacakan",
        help_text="Masukkan URL pelacakan dari kurir",
    )

    payment_deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Batas Pembayaran",
        help_text="Waktu terakhir pembayaran sebelum pesanan dibatalkan otomatis",
    )
    midtrans_token = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Midtrans Snap Token",
        help_text="Token Snap terakhir yang diterbitkan untuk pesanan ini",
    )
    midtrans_order_id = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="Midtrans Order ID",
        help_text="ID unik yang digunakan untuk transaksi Midtrans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pesanan"
        verbose_name_plural = "Pesanan"
        ordering = ['-created_at']

    PAYMENT_TIMEOUT_HOURS = 1
    MIDTRANS_ORDER_ID_PREFIX = "KALORIZ"
    MIDTRANS_RETRY_SEPARATOR = "::retry::"

    def __str__(self):
        return f"Pesanan #{self.order_number}"

    def save(self, *args, **kwargs):
        if self.payment_deadline is None:
            reference_time = self.created_at or timezone.now()
            self.payment_deadline = reference_time + timedelta(hours=self.PAYMENT_TIMEOUT_HOURS)
        super().save(*args, **kwargs)

    def get_status_display_class(self):
        """Return CSS class for status badge"""
        status_classes = {
            'pending': 'warning',
            'paid': 'success',
            'processing': 'info',
            'shipped': 'primary',
            'delivered': 'success',
            'cancelled': 'danger',
        }
        return status_classes.get(self.status, 'secondary')

    def _build_midtrans_order_id_value(self) -> str:
        if not self.pk:
            raise ValueError("Order belum disimpan sehingga tidak memiliki ID Midtrans.")

        prefix = getattr(settings, "MIDTRANS_ORDER_ID_PREFIX", self.MIDTRANS_ORDER_ID_PREFIX)
        prefix = (prefix or self.MIDTRANS_ORDER_ID_PREFIX or "ORDER").strip()
        pk_str = str(self.pk)
        max_length = self._meta.get_field("midtrans_order_id").max_length
        remaining = max_length - len(pk_str) - 1

        if remaining <= 0:
            return pk_str[-max_length:]

        trimmed_prefix = prefix[:remaining]
        candidate = f"{trimmed_prefix}-{pk_str}" if trimmed_prefix else pk_str[-max_length:]
        return candidate[:max_length]

    def ensure_midtrans_order_id(self) -> str:
        """Ensure the order has a stable Midtrans order ID."""

        if self.midtrans_order_id:
            return self.midtrans_order_id

        midtrans_order_id = self._build_midtrans_order_id_value()
        self.midtrans_order_id = midtrans_order_id
        self.save(update_fields=["midtrans_order_id"])
        return midtrans_order_id

    def _extract_midtrans_retry_state(self) -> tuple[str, int]:
        separator = self.MIDTRANS_RETRY_SEPARATOR or ""
        current_id = self.midtrans_order_id or ""
        if separator and separator in current_id:
            base, suffix = current_id.split(separator, 1)
            try:
                retry = int(suffix)
            except (TypeError, ValueError):
                retry = 0
            return base or self._build_midtrans_order_id_value(), retry
        return current_id or self._build_midtrans_order_id_value(), 0

    def _build_midtrans_retry_candidate(self, base_id: str, retry: int) -> str:
        separator = self.MIDTRANS_RETRY_SEPARATOR or ""
        if retry <= 0 or not separator:
            return base_id
        suffix = f"{separator}{retry}"
        field = self._meta.get_field("midtrans_order_id")
        max_length = getattr(field, "max_length", 50)
        if len(suffix) >= max_length:
            return suffix[-max_length:]
        allowed_base_length = max_length - len(suffix)
        trimmed_base = (base_id or "")[:allowed_base_length]
        if not trimmed_base:
            pk_str = str(self.pk or "")
            trimmed_base = pk_str[-allowed_base_length:]
        return f"{trimmed_base}{suffix}"

    def regenerate_midtrans_order_id(self) -> str:
        """Generate a new Midtrans order_id for retry scenarios."""

        base_id, current_retry = self._extract_midtrans_retry_state()
        next_retry = current_retry + 1
        candidate = self._build_midtrans_retry_candidate(base_id, next_retry)

        order_model = self.__class__
        while (
            order_model.objects.exclude(pk=self.pk)
            .filter(midtrans_order_id=candidate)
            .exists()
        ):
            next_retry += 1
            candidate = self._build_midtrans_retry_candidate(base_id, next_retry)

        self.midtrans_order_id = candidate
        self.midtrans_token = ""
        self.save(update_fields=["midtrans_order_id", "midtrans_token"])
        return candidate

    def clear_midtrans_token(self):
        if not self.midtrans_token:
            return
        self.midtrans_token = ""
        self.save(update_fields=["midtrans_token"])

    def get_payment_deadline(self):
        if self.payment_deadline:
            return self.payment_deadline
        if not self.created_at:
            return None
        return self.created_at + timedelta(hours=self.PAYMENT_TIMEOUT_HOURS)

    def is_payment_overdue(self):
        deadline = self.get_payment_deadline()
        if not deadline:
            return False
        return timezone.now() >= deadline


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Pesanan")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, verbose_name="Produk")
    product_name = models.CharField(max_length=200, verbose_name="Nama Produk")
    product_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Harga Produk")
    quantity = models.PositiveIntegerField(verbose_name="Jumlah")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Subtotal")

    class Meta:
        verbose_name = "Item Pesanan"
        verbose_name_plural = "Item Pesanan"

    def __str__(self):
        return f"{self.quantity}x {self.product_name}"


class UserProfile(models.Model):
    GENDER_CHOICES = [
        ('M', 'Laki-laki'),
        ('F', 'Perempuan'),
        ('O', 'Lainnya'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name="Pengguna")
    photo = models.ImageField(
        upload_to='profile_photos/',
        blank=True,
        null=True,
        verbose_name="Foto Profil",
        help_text="Upload foto profil Anda"
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name="Nomor Telepon")
    address = models.TextField(blank=True, verbose_name="Alamat")
    city = models.CharField(max_length=100, blank=True, verbose_name="Kota")
    postal_code = models.CharField(max_length=10, blank=True, verbose_name="Kode Pos")
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, verbose_name="Jenis Kelamin")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Tanggal Lahir")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profil Pengguna"
        verbose_name_plural = "Profil Pengguna"

    def __str__(self):
        return f"Profil - {self.user.username}"

    def get_photo_url(self):
        """Return profile photo URL or default avatar"""
        if self.photo and hasattr(self.photo, 'url'):
            return self.photo.url
        return '/static/images/default-avatar.png'


class Watchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watchlists', verbose_name="Pengguna")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='watchlisted_by', verbose_name="Produk")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Watchlist"
        verbose_name_plural = "Watchlist"
        unique_together = ['user', 'product']
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"


class EmailVerification(models.Model):
    """Model to store email verification codes for login"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='email_verifications', verbose_name="Pengguna")
    code = models.CharField(max_length=6, verbose_name="Kode Verifikasi")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name="Kadaluarsa")
    is_used = models.BooleanField(default=False, verbose_name="Sudah Digunakan")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Alamat IP")

    class Meta:
        verbose_name = "Verifikasi Email"
        verbose_name_plural = "Verifikasi Email"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.code}"

    @classmethod
    def generate_code(cls):
        """Generate random 6-digit verification code"""
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])

    @classmethod
    def create_verification(cls, user, ip_address=None):
        """Create a new verification code for user"""
        code = cls.generate_code()
        expires_at = timezone.now() + timedelta(minutes=10)  # Code expires in 10 minutes

        verification = cls.objects.create(
            user=user,
            code=code,
            expires_at=expires_at,
            ip_address=ip_address
        )

        return verification

    def is_valid(self):
        """Check if verification code is still valid"""
        return not self.is_used and timezone.now() < self.expires_at

    def mark_as_used(self):
        """Mark verification code as used"""
        self.is_used = True
        self.save()
