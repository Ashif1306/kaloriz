from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Category, Product


class ProductSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Product.objects.filter(available=True)

    def lastmod(self, obj):
        return obj.updated_at

class CategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Category.objects.all()

    def lastmod(self, obj):
        return obj.updated_at


class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = "monthly"

    def items(self):
        return ["catalog:home", "catalog:product_list", "catalog:about", "catalog:contact"]

    def location(self, item):
        return reverse(item)
