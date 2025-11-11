from django.db import migrations, models


def set_existing_coupons_to_flat(apps, schema_editor):
    DiscountCode = apps.get_model('catalog', 'DiscountCode')
    DiscountCode.objects.all().update(discount_type='flat')


def reverse_set_coupons(apps, schema_editor):
    # No-op reverse; original data assumed flat discounts
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_discountcode'),
    ]

    operations = [
        migrations.RenameField(
            model_name='discountcode',
            old_name='discount_amount',
            new_name='flat_amount',
        ),
        migrations.RenameField(
            model_name='discountcode',
            old_name='is_active',
            new_name='active',
        ),
        migrations.RenameField(
            model_name='discountcode',
            old_name='expiry_date',
            new_name='valid_to',
        ),
        migrations.AddField(
            model_name='discountcode',
            name='allowed_shipping',
            field=models.CharField(
                choices=[('reguler', 'Reguler'), ('express', 'Express'), ('both', 'Reguler & Express')],
                default='both',
                max_length=10,
                verbose_name='Kurir yang Diizinkan',
            ),
        ),
        migrations.AddField(
            model_name='discountcode',
            name='discount_type',
            field=models.CharField(
                choices=[('flat', 'Flat'), ('percent', 'Percent')],
                default='percent',
                max_length=10,
                verbose_name='Tipe Diskon',
            ),
        ),
        migrations.AddField(
            model_name='discountcode',
            name='max_discount',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Batas maksimum potongan untuk tipe persen. Isi 0 untuk tanpa batas.',
                max_digits=12,
                verbose_name='Batas Maksimum Diskon',
            ),
        ),
        migrations.AddField(
            model_name='discountcode',
            name='min_spend',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Minimal total belanja (subtotal + ongkir) agar kupon berlaku.',
                max_digits=12,
                verbose_name='Minimal Belanja',
            ),
        ),
        migrations.AddField(
            model_name='discountcode',
            name='percent',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Persentase potongan (0-100). Gunakan untuk tipe persen.',
                max_digits=5,
                verbose_name='Persentase',
            ),
        ),
        migrations.AddField(
            model_name='discountcode',
            name='valid_from',
            field=models.DateTimeField(blank=True, help_text='Biarkan kosong jika langsung aktif.', null=True, verbose_name='Berlaku Mulai'),
        ),
        migrations.AlterField(
            model_name='discountcode',
            name='active',
            field=models.BooleanField(default=True, verbose_name='Aktif'),
        ),
        migrations.AlterField(
            model_name='discountcode',
            name='flat_amount',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Nilai potongan untuk tipe flat.',
                max_digits=12,
                verbose_name='Nominal Flat',
            ),
        ),
        migrations.AlterField(
            model_name='discountcode',
            name='valid_to',
            field=models.DateTimeField(
                blank=True,
                help_text='Biarkan kosong jika tanpa batas waktu.',
                null=True,
                verbose_name='Berlaku Sampai',
            ),
        ),
        migrations.RunPython(set_existing_coupons_to_flat, reverse_set_coupons),
    ]
