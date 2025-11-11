from django.urls import path

from . import views

app_name = "payment"

urlpatterns = [
    path("create-snap-token/", views.payment_create_snap_token, name="create_snap_token"),
    path("finish/", views.payment_finish, name="finish"),
    path("doku/create-checkout/", views.payment_create_doku_checkout, name="create_doku_checkout"),
    path("doku/notification/", views.doku_notification, name="doku_notification"),
    path("doku/return/", views.doku_return, name="doku_return"),
]
