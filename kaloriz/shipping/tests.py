from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from catalog.models import Category, Product
from core.models import Cart, CartItem, Order
from .models import Address, District


class AddressManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', email='alice@example.com', password='secret123')
        self.district = District.objects.create(
            name='Panakkukang',
            reg_cost=Decimal('10000.00'),
            exp_cost=Decimal('15000.00'),
            eta_reg='2-3 hari',
            eta_exp='1 hari',
            is_active=True,
        )

    def _create_address(self, user, label='Rumah', is_default=False):
        return Address.objects.create(
            user=user,
            full_name='Alice Wonder',
            phone='08123456789',
            province='Sulawesi Selatan',
            city='Makassar',
            district=self.district,
            postal_code='90111',
            street_name='Jl. Contoh No. 1',
            detail='Blok A',
            label=label,
            is_default=is_default,
        )

    def test_delete_address_protected_error_shows_message(self):
        address = self._create_address(self.user, is_default=True)
        Order.objects.create(
            user=self.user,
            order_number='INV-1',
            status='pending',
            full_name='Alice Wonder',
            email='alice@example.com',
            phone='08123456789',
            address='Alamat lama',
            city='Makassar',
            postal_code='90111',
            shipping_address=address,
            subtotal=Decimal('100000.00'),
            shipping_cost=Decimal('10000.00'),
            total=Decimal('110000.00'),
        )

        self.client.login(username='alice', password='secret123')
        response = self.client.post(
            reverse('shipping:delete_address', args=[address.id]),
            follow=True,
        )

        self.assertRedirects(response, reverse('core:profile'))
        self.assertTrue(Address.objects.filter(id=address.id).exists())

        message_texts = [m.message for m in response.context['messages']]
        self.assertTrue(any('tidak bisa dihapus' in msg for msg in message_texts))

    def test_archive_address_hides_from_profile_and_checkout(self):
        address = self._create_address(self.user, is_default=True)

        category = Category.objects.create(name='Suplemen')
        product = Product.objects.create(
            category=category,
            name='Vitamin C',
            slug='vitamin-c',
            description='Tablet vitamin C',
            price=Decimal('25000.00'),
            stock=10,
        )
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=product, quantity=1, is_selected=True)

        self.client.login(username='alice', password='secret123')
        response = self.client.post(
            reverse('shipping:archive_address', args=[address.id]),
            follow=True,
        )

        address.refresh_from_db()
        self.assertTrue(address.is_deleted)
        self.assertFalse(address.is_default)

        profile_messages = [m.message for m in response.context['messages']]
        self.assertTrue(any('Alamat diarsipkan' in msg for msg in profile_messages))

        profile_resp = self.client.get(reverse('core:profile'))
        self.assertNotIn(address, list(profile_resp.context['user_addresses']))

        checkout_resp = self.client.get(reverse('core:checkout'))
        self.assertEqual(checkout_resp.status_code, 200)
        self.assertNotIn(address, list(checkout_resp.context['user_addresses']))
        self.assertIsNone(checkout_resp.context['active_address_id'])
