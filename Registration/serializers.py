# serializers.py

from rest_framework import serializers
from .models import Registration
from django.core.validators import RegexValidator
from .models import validate_akgec_email

class RegistrationSerializer(serializers.ModelSerializer):

    full_name = serializers.CharField(
        max_length=100,
        validators=[
            RegexValidator(
                regex=r'^[A-Za-z\s]+$',
                message="Full name must contain only letters and spaces."
            )
        ]
    )
    student_number = serializers.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r'^\d+$',
                message="Student number must be numeric."
            )
        ]
    )
    phone = serializers.CharField(
        max_length=12,
        validators=[
            RegexValidator(
                regex=r'^\d{10,12}$',
                message="Phone number must be 10-12 digits."
            )
        ]
    )

    email = serializers.EmailField(validators=[validate_akgec_email])
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
            # 'email_otp',
            # 'otp_expires_at',
            # Payment fields:
            # 'payment_status',
            # 'payment_reference',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['payment_status', 'payment_reference', 'created_at', 'updated_at', 'is_email_verified']


class PaymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Registration
        fields = ['id', 'full_name', 'email', 'payment_status', 'payment_reference']

class EmailStatusCheckSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not value.endswith('@akgec.ac.in'):
            raise serializers.ValidationError("Email must end with '@akgec.ac.in'.")
        return value
    

class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Registration
        fields = ['full_name', 'payment_status', 'phone', 'email', 'created_at']