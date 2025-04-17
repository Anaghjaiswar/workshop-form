# urls.py

from django.urls import path
from .views import RegistrationCreateView, PaymentInitiationView, razorpay_webhook, PaymentStatusView, VerifyEmailView, CheckEmailStatusView,RegistrationListView

urlpatterns = [
    path('registrations/', RegistrationCreateView.as_view(), name='registration-create'),
    path('payment-initiation/', PaymentInitiationView.as_view(), name='payment-initiation'),
    path('razorpay-webhook/', razorpay_webhook, name='razorpay-webhook'), 
    path('payment-status/<int:id>/', PaymentStatusView.as_view(), name='payment-status'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    # path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('check-email-status/', CheckEmailStatusView.as_view(), name='check-email-status'),
    path('registration-list/', RegistrationListView.as_view(), name='registration-list'),
]
