# urls.py

from django.urls import path
from .views import RegistrationCreateView, PaymentInitiationView, razorpay_webhook

urlpatterns = [
    path('registrations/', RegistrationCreateView.as_view(), name='registration-create'),
    path('payment-initiation/', PaymentInitiationView.as_view(), name='payment-initiation'),
    path('razorpay-webhook/', razorpay_webhook, name='razorpay-webhook'), 
]
