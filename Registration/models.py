from django.db import models
from django.core.validators import RegexValidator
from django.utils.timezone import now
from django.core.exceptions import ValidationError


def validate_akgec_email(value):
        if not value.endswith('@akgec.ac.in'):
            raise ValidationError("Email must end with '@akgec.ac.in'.")

# Create your models here.
class Registration(models.Model):
    BRANCH_CHOICES = [
        ('CSE', 'CSE'),
        ('CS', 'CS'),
        ('CS-IT', 'CS-IT'),
        ('CSE-DS', 'CSE-DS'),
        ('CS-HINDI', 'CS-HINDI'),
        ('CSE-AIML', 'CSE-AIML'),
        ('IT', 'IT'),
        ('AIML', 'AIML'),
        ('ECE', 'ECE'),
        ('ME', 'ME'),
        ('EN', 'EN'),
        ('CIVIL', 'CIVIL'),
    ]

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]

    YEAR_CHOICES = [
        ('1st', '1st Year'),
        ('2nd', '2nd Year'),
        ('3rd', '3rd Year'),
        ('4th', '4th Year'),
    ]

    LIVING_CHOICES = [
        ('hosteller', 'Hosteller'),
        ('day scholar', 'Day Scholar')
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    # PERSONAL DETAILS
    full_name = models.CharField(max_length=100)
    student_number = models.CharField(max_length=10)
    branch = models.CharField(max_length=10, choices=BRANCH_CHOICES)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    year = models.CharField(max_length=10, choices=YEAR_CHOICES)

    # CONTACT DETAILS
    phone = models.CharField(
        max_length=12,
        validators=[
            RegexValidator(
                regex=r'^\d{10,12}$',
                message='Phone number must be 10-12 digits'
            )
        ]
    )
    email = models.EmailField(unique=True, validators=[validate_akgec_email])
    living_type = models.CharField(max_length=20, choices=LIVING_CHOICES)

    # E-MAIL VERIFICATION FIELDS
    is_email_verified = models.BooleanField(default=False)
    email_otp = models.CharField(max_length=6, blank=True, null=True)  
    otp_expires_at = models.DateTimeField(blank=True, null=True)  
    
    # PAYMENT DETAILS
    payment_status = models.CharField(max_length=20, default='pending')
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    order_id = models.CharField(max_length=100, blank=True, null=True) 
    payment_signature = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} ({self.student_number}) - {self.payment_status.capitalize()}"
    
    def is_otp_valid(self):
        return self.otp_expires_at and self.otp_expires_at > now()



