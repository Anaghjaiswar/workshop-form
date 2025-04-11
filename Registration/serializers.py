# serializers.py

from rest_framework import serializers
from .models import Registration

class RegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Registration
        fields = [
            'id',
            'full_name',
            'student_number',
            'branch',
            'gender',
            'year',
            'phone',
            'email',
            'living_type',
            # Email verification fields if needed:
            'is_email_verified',
            'email_otp',
            'otp_expires_at',
            # Payment fields:
            'payment_status',
            'payment_reference',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['payment_status', 'payment_reference', 'created_at', 'updated_at', 'is_email_verified']


class PaymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Registration
        fields = ['id', 'full_name', 'email', 'payment_status', 'payment_reference']