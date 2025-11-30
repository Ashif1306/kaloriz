from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views

app_name = 'core'

urlpatterns = [
    # Cart URLs
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('flash-sale/buy/<slug:slug>/', views.flash_sale_buy_now, name='flash_sale_buy_now'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    path('cart/toggle-select/<int:item_id>/', views.toggle_cart_item_selection, name='toggle_cart_item_selection'),
    path('cart/delete-selected/', views.delete_selected_cart_items, name='delete_selected_cart_items'),

    # Checkout URLs
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/payment/', views.checkout_payment, name='checkout_payment'),
    path('checkout/review/', views.checkout_review, name='checkout_review'),
    path('order/place/', views.place_order, name='place_order'),
    path('order/place-from-address/', views.place_order_from_address, name='place_order_from_address'),
    path('checkout/shipping-quote/', views.set_shipping_method, name='set_shipping_method'),
    # Order URLs
    path('orders/', views.order_list, name='order_list'),
    path('order/<str:order_number>/', views.order_detail, name='order_detail'),
    path('order/item/<int:order_item_id>/review/', views.create_review, name='create_review'),

    # Auth URLs
    path('register/', views.register_view, name='register'),
    path('register/verify/', views.verify_email_view, name='verify_email'),
    path('register/resend/', views.resend_verification_code, name='resend_verification'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Password reset URLs
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='core/password_reset_form.html',
            email_template_name='core/emails/password_reset_email.txt',
            subject_template_name='core/emails/password_reset_subject.txt',
            success_url=reverse_lazy('core:password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='core/password_reset_done.html'
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='core/password_reset_confirm.html',
            success_url=reverse_lazy('core:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='core/password_reset_complete.html'
        ),
        name='password_reset_complete',
    ),

    # Profile URLs
    path('profile/', views.profile_view, name='profile'),
    path('profile/settings/', views.profile_settings, name='profile_settings'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/address/edit/', views.profile_address_edit, name='profile_address_edit'),
    path('profile/notifications/', views.notifications_view, name='notifications'),
    path(
        'profile/notifications/<int:notification_id>/read/',
        views.mark_notification_as_read,
        name='notification_mark_read',
    ),

    # Watchlist URLs
    path('watchlist/', views.watchlist_view, name='watchlist'),
    path('watchlist/add/<int:product_id>/', views.add_to_watchlist, name='add_to_watchlist'),
    path('watchlist/remove/<int:watchlist_id>/', views.remove_from_watchlist, name='remove_from_watchlist'),
    path('watchlist/toggle/<int:product_id>/', views.toggle_watchlist, name='toggle_watchlist'),
    
]
