from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator


class District(models.Model):
    """
    Model untuk kecamatan di Makassar dengan tarif pengiriman.
    Origin: Universitas Negeri Makassar (UNM), Jl. AP Pettarani
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Nama Kecamatan")

    # Tarif Reguler (2-3 hari)
    reg_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Tarif Reguler (Rp)",
        help_text="Estimasi 2-3 hari kerja"
    )

    # Tarif Express (1 hari)
    exp_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Tarif Express (Rp)",
        help_text="Estimasi 1 hari kerja"
    )

    # Estimasi waktu pengiriman
    eta_reg = models.CharField(
        max_length=50,
        default="2-3 hari kerja",
        verbose_name="ETA Reguler"
    )
    eta_exp = models.CharField(
        max_length=50,
        default="1 hari kerja",
        verbose_name="ETA Express"
    )

    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Kecamatan"
        verbose_name_plural = "Kecamatan"
        ordering = ['name']
        indexes = [
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name


class Address(models.Model):
    """
    Model untuk alamat pengiriman pelanggan - Standard address fields
    """
    # Validator nomor HP Indonesia
    phone_validator = RegexValidator(
        regex=r'^(\+62|62|0)[0-9]{9,12}$',
        message="Nomor telepon harus berformat Indonesia (contoh: 08123456789 atau +628123456789)"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='addresses',
        verbose_name="Pengguna"
    )

    # Basic address information
    label = models.CharField(
        max_length=50,
        default="Rumah",
        verbose_name="Label Alamat",
        help_text="Contoh: Rumah, Kantor, Apartemen"
    )
    full_name = models.CharField(max_length=120, verbose_name="Nama Lengkap")
    phone = models.CharField(
        max_length=30,
        validators=[phone_validator],
        verbose_name="Nomor Telepon"
    )

    # Detailed address fields
    province = models.CharField(
        max_length=100,
        default="Sulawesi Selatan",
        verbose_name="Provinsi"
    )
    city = models.CharField(
        max_length=100,
        default="Makassar",
        verbose_name="Kota"
    )
    district = models.ForeignKey(
        District,
        on_delete=models.PROTECT,
        verbose_name="Kecamatan",
        help_text="Pilih kecamatan untuk perhitungan ongkir"
    )
    postal_code = models.CharField(max_length=10, verbose_name="Kode Pos")
    street_name = models.CharField(max_length=255, verbose_name="Nama Jalan")
    detail = models.TextField(
        blank=True,
        verbose_name="Detail Lainnya",
        help_text="Contoh: Blok, nomor rumah, patokan, warna cat, dll"
    )

    # Map coordinates (optional)
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name="Latitude",
        help_text="Koordinat latitude (opsional)"
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name="Longitude",
        help_text="Koordinat longitude (opsional)"
    )

    is_default = models.BooleanField(default=False, verbose_name="Alamat Utama")
    # Penanda soft delete agar alamat bisa diarsipkan tanpa menghapus permanen.
    is_deleted = models.BooleanField(default=False, verbose_name="Diarsipkan")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Alamat"
        verbose_name_plural = "Alamat"
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_default']),
        ]

    def __str__(self):
        return f"{self.label} - {self.full_name} ({self.district.name})"

    def get_full_address(self):
        """Return formatted full address"""
        parts = [
            self.street_name,
            self.detail,
            self.district.name,
            self.city,
            self.province,
            self.postal_code
        ]
        return ", ".join([p for p in parts if p])

    def save(self, *args, **kwargs):
        """
        Pastikan hanya ada satu alamat default per user
        """
        if self.is_default:
            # Set semua alamat user lain jadi non-default
            Address.objects.filter(
                user=self.user,
                is_default=True,
                is_deleted=False
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)


class Shipment(models.Model):
    """
    Model untuk data pengiriman di setiap order
    """
    SERVICE_CHOICES = [
        ('REG', 'Reguler'),
        ('EXP', 'Express'),
    ]

    order = models.OneToOneField(
        'core.Order',  # Relasi ke Order model yang sudah ada
        on_delete=models.CASCADE,
        related_name='shipment',
        verbose_name="Pesanan"
    )

    # Data alamat (snapshot saat order dibuat)
    full_name = models.CharField(max_length=200, verbose_name="Nama Penerima")
    phone = models.CharField(max_length=20, verbose_name="Telepon")
    street = models.TextField(verbose_name="Alamat")
    district_name = models.CharField(max_length=100, verbose_name="Kecamatan")
    postal_code = models.CharField(max_length=10, verbose_name="Kode Pos")

    # Service dan biaya (snapshot saat order)
    service = models.CharField(
        max_length=3,
        choices=SERVICE_CHOICES,
        verbose_name="Layanan Pengiriman"
    )
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Biaya Pengiriman"
    )
    eta = models.CharField(max_length=50, verbose_name="Estimasi Pengiriman")

    # Tracking
    tracking_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Nomor Resi"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pengiriman"
        verbose_name_plural = "Pengiriman"
        ordering = ['-created_at']

    def __str__(self):
        return f"Pengiriman #{self.order.order_number} - {self.get_service_display()}"

    def get_service_label(self):
        """Return label untuk display"""
        return self.get_service_display()
