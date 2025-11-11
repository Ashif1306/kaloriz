"""
Management command untuk mengisi data 15 kecamatan di Makassar
dengan tarif pengiriman dari UNM (Jl. AP Pettarani) sebagai origin point.

Usage:
    python manage.py seed_makassar_shipping
"""

from django.core.management.base import BaseCommand
from shipping.models import District


class Command(BaseCommand):
    help = 'Seed 15 kecamatan Makassar dengan tarif pengiriman dari UNM'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Seeding data kecamatan Makassar...'))

        # Data 15 kecamatan di Makassar dengan tarif dari UNM
        # Tarif berdasarkan jarak estimasi dari Universitas Negeri Makassar (UNM)
        # UNM berlokasi di Jl. AP Pettarani (dekat dengan pusat kota)
        districts_data = [
            {
                'name': 'Biringkanaya',
                'reg_cost': 15000.00,
                'exp_cost': 25000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Bontoala',
                'reg_cost': 12000.00,
                'exp_cost': 20000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Makassar',
                'reg_cost': 10000.00,
                'exp_cost': 18000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Mamajang',
                'reg_cost': 10000.00,
                'exp_cost': 18000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Manggala',
                'reg_cost': 12000.00,
                'exp_cost': 20000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Mariso',
                'reg_cost': 10000.00,
                'exp_cost': 18000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Panakkukang',
                'reg_cost': 8000.00,  # Terdekat dengan UNM
                'exp_cost': 15000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Rappocini',
                'reg_cost': 10000.00,
                'exp_cost': 18000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Tamalanrea',
                'reg_cost': 18000.00,  # Terjauh
                'exp_cost': 30000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Tallo',
                'reg_cost': 15000.00,
                'exp_cost': 25000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Tamalate',
                'reg_cost': 12000.00,
                'exp_cost': 20000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Ujung Pandang',
                'reg_cost': 10000.00,
                'exp_cost': 18000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Ujung Tanah',
                'reg_cost': 12000.00,
                'exp_cost': 20000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Wajo',
                'reg_cost': 10000.00,
                'exp_cost': 18000.00,
                'eta_reg': '2-3 hari kerja',
                'eta_exp': '1 hari kerja',
            },
            {
                'name': 'Kepulauan Sangkarrang',
                'reg_cost': 25000.00,  # Kepulauan, lebih mahal
                'exp_cost': 40000.00,
                'eta_reg': '3-4 hari kerja',
                'eta_exp': '1-2 hari kerja',
            },
        ]

        created_count = 0
        updated_count = 0

        for district_data in districts_data:
            district, created = District.objects.update_or_create(
                name=district_data['name'],
                defaults={
                    'reg_cost': district_data['reg_cost'],
                    'exp_cost': district_data['exp_cost'],
                    'eta_reg': district_data['eta_reg'],
                    'eta_exp': district_data['eta_exp'],
                    'is_active': True,
                }
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Created: {district.name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'  ↻ Updated: {district.name}')
                )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Seeding complete!'))
        self.stdout.write(self.style.SUCCESS(f'  Created: {created_count} districts'))
        self.stdout.write(self.style.SUCCESS(f'  Updated: {updated_count} districts'))
        self.stdout.write(self.style.SUCCESS(f'  Total: {District.objects.count()} districts'))
