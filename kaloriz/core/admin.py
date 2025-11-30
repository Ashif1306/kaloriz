from django import forms
from django.contrib import admin
from .models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    PaymentMethod,
    UserProfile,
    Watchlist,
    EmailVerification,
    Notification,
)

admin.site.site_header = "Kaloriz Admin"
admin.site.site_title = "Kaloriz Admin"
admin.site.index_title = "Dashboard"


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'service_status', 'is_active', 'display_order', 'updated_at']
    list_editable = ['service_status', 'is_active', 'display_order']
    search_fields = ['name', 'slug', 'description']
    list_filter = ['service_status', 'is_active']
    readonly_fields = ['created_at', 'updated_at']
    prepopulated_fields = {'slug': ('name',)}

    fieldsets = (
        (
            'Informasi Utama',
            {
                'fields': (
                    'name',
                    'slug',
                    'tagline',
                    'description',
                    'additional_info',
                    'service_status',
                )
            },
        ),
        (
            'Tampilan',
            {
                'fields': (
                    'logo',
                    'button_label',
                    'display_order',
                    'is_active',
                )
            },
        ),
        (
            'Metadata',
            {
                'classes': ('collapse',),
                'fields': ('created_at', 'updated_at'),
            },
        ),
    )


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'added_at']


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'updated_at', 'get_total_items']
    list_filter = ['created_at']
    search_fields = ['user__username', 'user__email']
    inlines = [CartItemInline]
    readonly_fields = ['created_at', 'updated_at']

    def get_total_items(self, obj):
        return obj.get_total_items()
    get_total_items.short_description = 'Total Items'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'product_name', 'product_price', 'quantity', 'subtotal']


class OrderAdminForm(forms.ModelForm):
    shipping_provider = forms.ChoiceField(required=False, label="Kurir Pengiriman")

    class Meta:
        model = Order
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        service_label = (self.instance.selected_service_name or '').strip().lower()
        if not service_label:
            courier_code = (self.instance.selected_courier or '').strip().lower()
            if courier_code in {'exp', 'express'}:
                service_label = 'express'
        if service_label == 'express':
            choices = list(Order.EXPRESS_COURIERS)
        else:
            choices = list(Order.REGULAR_COURIERS)

        current_value = self.instance.shipping_provider
        choice_map = dict(Order.SHIPPING_PROVIDER_CHOICES)
        existing_values = {value for value, _ in choices}
        if current_value and current_value not in existing_values:
            choices.append((current_value, choice_map.get(current_value, current_value)))

        self.fields['shipping_provider'].choices = [('', '---------')] + choices


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = ['order_number', 'user', 'full_name', 'status', 'total', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['order_number', 'user__username', 'full_name', 'email', 'phone']
    readonly_fields = ['order_number', 'created_at', 'updated_at', 'selected_courier', 'selected_service_name']
    inlines = [OrderItemInline]
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Informasi Pesanan', {
            'fields': ('order_number', 'user', 'status')
        }),
        ('Informasi Pengiriman', {
            'fields': (
                'full_name',
                'email',
                'phone',
                'address',
                'city',
                'postal_code',
                'selected_service_name',
                'selected_courier',
                'shipping_provider',
                'tracking_number',
                'tracking_url',
            )
        }),
        ('Total', {
            'fields': ('subtotal', 'shipping_cost', 'total')
        }),
        ('Catatan', {
            'fields': ('notes',)
        }),
        ('Timestamp', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'city', 'gender', 'birth_date', 'created_at']
    search_fields = ['user__username', 'user__email', 'phone']
    readonly_fields = ['created_at', 'updated_at']
    list_filter = ['gender', 'created_at']


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'added_at']
    list_filter = ['added_at']
    search_fields = ['user__username', 'product__name']
    readonly_fields = ['added_at']
    date_hierarchy = 'added_at'


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'code', 'created_at', 'expires_at', 'is_used', 'ip_address']
    list_filter = ['is_used', 'created_at']
    search_fields = ['user__username', 'user__email', 'code']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
    search_fields = ['title', 'message', 'user__username', 'user__email']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
