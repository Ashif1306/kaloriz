from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product, Testimonial, DiscountCode

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']
    list_filter = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'favorite_star',
        'is_featured',
        'name',
        'category',
        'price',
        'discount_price',
        'flash_sale_price',
        'is_flash_sale',
        'stock',
        'weight_gram',
        'is_fragile',
        'is_perishable',
        'available',
        'created_at'
    ]
    list_filter = ['available', 'is_featured', 'is_flash_sale', 'is_fragile', 'is_perishable', 'category', 'created_at']
    list_editable = ['price', 'discount_price', 'flash_sale_price', 'stock', 'available', 'is_featured', 'is_flash_sale']
    readonly_fields = ['flash_sale_end']
    list_display_links = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name', 'description']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    fieldsets = (
        ('Informasi Dasar', {
            'fields': ('category', 'name', 'slug', 'description')
        }),
        ('Harga & Stok', {
            'fields': (
                'price', 'discount_price', 'stock', 'available',
                'weight_gram', 'length_cm', 'width_cm', 'height_cm',
                'is_fragile', 'is_perishable',
            )
        }),
        ('Flash Sale', {
            'fields': (
                'is_flash_sale', 'flash_sale_price', 'flash_sale_start',
                'flash_sale_duration_hours', 'flash_sale_end'
            )
        }),
        ('Label', {
            'fields': ('is_featured',),
        }),
        ('Informasi Nutrisi', {
            'fields': (
                'calories', 'protein', 'fat', 'carbohydrates', 'vitamins', 'fiber'
            )
        }),
        ('Media', {
            'fields': ('image',)
        }),
    )

    @admin.display(description='Favorit', ordering='is_featured')
    def favorite_star(self, obj):
        star_color = '#f7c32e' if obj.is_featured else '#d6d6d6'
        star_icon = '★' if obj.is_featured else '☆'
        return format_html(
            '<span style="color: {}; font-size: 18px;" aria-label="{}">{}</span>',
            star_color,
            'Favorit' if obj.is_featured else 'Bukan favorit',
            star_icon,
        )


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'order', 'rating', 'is_approved', 'created_at']
    list_filter = ['is_approved', 'rating', 'created_at']
    search_fields = ['user__username', 'product__name', 'order__order_number', 'review']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_approved']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Informasi Testimoni', {
            'fields': ('product', 'order', 'user', 'rating', 'review', 'photo', 'is_approved')
        }),
        ('Timestamp', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = [
        'code',
        'discount_overview',
        'min_spend',
        'allowed_shipping',
        'active',
        'valid_from',
        'valid_to',
        'created_at',
    ]
    list_filter = ['discount_type', 'allowed_shipping', 'active', 'valid_from', 'valid_to', 'created_at']
    search_fields = ['code']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {
            'fields': ('code', 'active', 'valid_from', 'valid_to')
        }),
        ('Pengaturan Diskon', {
            'fields': (
                'discount_type',
                'percent',
                'flat_amount',
                'max_discount',
                'min_spend',
                'allowed_shipping',
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    @admin.display(description='Detail Diskon')
    def discount_overview(self, obj):
        return obj.get_type_label()
