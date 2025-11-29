from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.formats import number_format
from decimal import Decimal, InvalidOperation

class Category(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name="Nama Kategori")
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True, verbose_name="Deskripsi")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Kategori"
        verbose_name_plural = "Kategori"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('catalog:category_detail', args=[self.slug])


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products', verbose_name="Kategori")
    name = models.CharField(max_length=200, verbose_name="Nama Produk")
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(verbose_name="Deskripsi")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Harga")
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Harga Diskon")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Gambar")
    stock = models.PositiveIntegerField(default=0, verbose_name="Stok")
    available = models.BooleanField(default=True, verbose_name="Tersedia")

    # === INFORMASI NUTRISI ===
    calories = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Kalori (kcal)",
        help_text="Total kalori per porsi (opsional)",
    )
    protein = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Protein (g)",
        help_text="Jumlah protein per porsi dalam gram (opsional)",
    )
    fat = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Lemak (g)",
        help_text="Jumlah lemak per porsi dalam gram (opsional)",
    )
    carbohydrates = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Karbohidrat (g)",
        help_text="Jumlah karbohidrat per porsi dalam gram (opsional)",
    )
    vitamins = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Vitamin",
        help_text="Daftar vitamin utama (opsional)",
    )
    fiber = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Serat (g)",
        help_text="Jumlah serat per porsi dalam gram (opsional)",
    )

    # === FIELD PENGIRIMAN ===
    weight_gram = models.PositiveIntegerField(
        default=1000,
        verbose_name="Berat (gram)",
        help_text="Berat per unit (gram). Minimal 1000 gram untuk ongkir."
    )
    length_cm = models.PositiveIntegerField(
        default=0,
        blank=True,
        verbose_name="Panjang (cm)",
        help_text="Panjang (cm) – opsional"
    )
    width_cm = models.PositiveIntegerField(
        default=0,
        blank=True,
        verbose_name="Lebar (cm)",
        help_text="Lebar (cm) – opsional"
    )
    height_cm = models.PositiveIntegerField(
        default=0,
        blank=True,
        verbose_name="Tinggi (cm)",
        help_text="Tinggi (cm) – opsional"
    )
    is_fragile = models.BooleanField(
        default=False,
        verbose_name="Mudah Pecah",
        help_text="Mudah pecah (opsional)"
    )
    is_perishable = models.BooleanField(
        default=False,
        verbose_name="Mudah Rusak",
        help_text="Mudah rusak (opsional)"
    )

    is_featured = models.BooleanField(
        default=False,
        verbose_name="Favorit",
        help_text="Tampilkan produk ini sebagai produk unggulan di beranda",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produk"
        verbose_name_plural = "Produk"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['-created_at']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            unique_slug = base_slug
            counter = 1
            while Product.objects.filter(slug=unique_slug).exclude(pk=self.pk).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('catalog:product_detail', args=[self.slug])

    def get_display_price(self):
        """Return discount price if available, otherwise regular price"""
        return self.discount_price if self.discount_price else self.price

    def is_on_sale(self):
        """Check if product has a discount"""
        return self.discount_price is not None and self.discount_price < self.price

    def get_discount_percentage(self):
        """Calculate discount percentage"""
        if self.is_on_sale():
            return int(((self.price - self.discount_price) / self.price) * 100)
        return 0

    def has_nutrition_info(self):
        """Return True if at least one nutrition field contains a value."""
        nutrition_fields = [
            self.calories,
            self.protein,
            self.fat,
            self.carbohydrates,
            self.vitamins,
            self.fiber,
        ]
        return any(value not in (None, "") for value in nutrition_fields)


class Testimonial(models.Model):
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]

    order = models.ForeignKey(
        'core.Order',
        on_delete=models.CASCADE,
        related_name='testimonials',
        verbose_name="Pesanan",
        null=True,
        blank=True,
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='testimonials', verbose_name="Produk")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='testimonials', verbose_name="Pengguna")
    rating = models.IntegerField(choices=RATING_CHOICES, verbose_name="Rating")
    review = models.TextField(verbose_name="Ulasan")
    photo = models.ImageField(upload_to='testimonials/', blank=True, null=True, verbose_name="Foto")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_approved = models.BooleanField(default=True, verbose_name="Disetujui")

    class Meta:
        verbose_name = "Testimoni"
        verbose_name_plural = "Testimoni"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'product', 'user'],
                name='unique_testimonial_per_order_product_user',
                condition=Q(order__isnull=False),
            )
        ]

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"


class DiscountCode(models.Model):
    TYPE_FLAT = 'flat'
    TYPE_PERCENT = 'percent'
    DISCOUNT_TYPE_CHOICES = [
        (TYPE_FLAT, 'Flat'),
        (TYPE_PERCENT, 'Percent'),
    ]

    SHIPPING_REGULER = 'reguler'
    SHIPPING_EXPRESS = 'express'
    SHIPPING_BOTH = 'both'
    ALLOWED_SHIPPING_CHOICES = [
        (SHIPPING_REGULER, 'Reguler'),
        (SHIPPING_EXPRESS, 'Express'),
        (SHIPPING_BOTH, 'Reguler & Express'),
    ]

    code = models.CharField(max_length=50, unique=True, verbose_name="Kode")
    discount_type = models.CharField(
        max_length=10,
        choices=DISCOUNT_TYPE_CHOICES,
        default=TYPE_PERCENT,
        verbose_name="Tipe Diskon",
    )
    percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Persentase",
        help_text="Persentase potongan (0-100). Gunakan untuk tipe persen.",
    )
    flat_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Nominal Flat",
        help_text="Nilai potongan untuk tipe flat.",
    )
    max_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Batas Maksimum Diskon",
        help_text="Batas maksimum potongan untuk tipe persen. Isi 0 untuk tanpa batas.",
    )
    min_spend = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Minimal Belanja",
        help_text="Minimal total belanja (subtotal + ongkir) agar kupon berlaku.",
    )
    allowed_shipping = models.CharField(
        max_length=10,
        choices=ALLOWED_SHIPPING_CHOICES,
        default=SHIPPING_BOTH,
        verbose_name="Kurir yang Diizinkan",
    )
    active = models.BooleanField(default=True, verbose_name="Aktif")
    valid_from = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Berlaku Mulai",
        help_text="Biarkan kosong jika langsung aktif.",
    )
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Berlaku Sampai",
        help_text="Biarkan kosong jika tanpa batas waktu.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Kode Diskon"
        verbose_name_plural = "Kode Diskon"
        ordering = ['-created_at']

    def __str__(self):
        return self.code.upper()

    def is_valid(self, now=None):
        if not self.active:
            return False
        now = now or timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        return True

    def _calculate_percent_discount(self, grand_total: Decimal) -> Decimal:
        percent_value = Decimal(self.percent or 0)
        if percent_value <= 0:
            return Decimal('0')
        discount = (grand_total * percent_value) / Decimal('100')
        max_cap = Decimal(self.max_discount or 0)
        if max_cap > 0 and discount > max_cap:
            discount = max_cap
        return discount

    def _calculate_flat_discount(self, grand_total: Decimal) -> Decimal:
        amount = Decimal(self.flat_amount or 0)
        if amount <= 0:
            return Decimal('0')
        return min(amount, grand_total)

    def calculate_discount(self, grand_total: Decimal) -> Decimal:
        if grand_total <= 0:
            return Decimal('0')
        if self.discount_type == self.TYPE_FLAT:
            return self._calculate_flat_discount(grand_total)
        return self._calculate_percent_discount(grand_total)

    def is_shipping_allowed(self, selected_method: str) -> bool:
        if not selected_method:
            return False
        selected_method = str(selected_method or '').upper()
        if self.allowed_shipping == self.SHIPPING_BOTH:
            return True
        if self.allowed_shipping == self.SHIPPING_EXPRESS:
            return selected_method == 'EXP'
        if self.allowed_shipping == self.SHIPPING_REGULER:
            return selected_method == 'REG'
        return False

    def get_min_spend(self) -> Decimal:
        return Decimal(self.min_spend or 0)

    def get_type_label(self) -> str:
        if self.discount_type == self.TYPE_FLAT:
            return f"Flat { _format_currency(self.flat_amount) }"
        percent_value = Decimal(self.percent or 0)
        percent_display = _format_percentage(percent_value)
        cap_display = _format_currency(self.max_discount) if self.max_discount else "tanpa batas"
        return f"{percent_display} cap {cap_display}"


def _format_currency(value) -> str:
    try:
        amount = Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal('0')
    return f"Rp {number_format(amount, decimal_pos=0, force_grouping=True)}"


def _format_percentage(value: Decimal) -> str:
    if value == value.to_integral():
        return f"{int(value)}%"
    return f"{value.normalize():f}%"
