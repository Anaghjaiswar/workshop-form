import random
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import razorpay
from rest_framework import status, generics
from rest_framework.response import Response
from .models import Registration
from .serializers import  RegistrationSerializer, PaymentStatusSerializer
import hmac
import hashlib
from django.conf import settings
import json
from rest_framework.views import APIView
import logging
from django.utils.timezone import now, timedelta
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

class RegistrationCreateView(generics.CreateAPIView):
    queryset = Registration.objects.all()
    serializer_class = RegistrationSerializer

    def generate_otp(self):
        """Generate a random 6-digit OTP."""
        return random.randint(100000, 999999)
    
    def hash_otp(self, otp):
        """Hash the OTP for secure storage."""
        return hashlib.sha256(str(otp).encode()).hexdigest()

    def perform_create(self, serializer):
        instance = serializer.save()

        otp = self.generate_otp()
        otp_expiry = now() + timedelta(minutes=10)

        # Update the instance with OTP and expiration time
        instance.email_otp = str(otp)
        instance.otp_expires_at = otp_expiry
        instance.save()

        # Send OTP via email
        message = f"Dear {instance.full_name},\n\nYour OTP for email verification is: {otp}\n\nThis OTP is valid until {otp_expiry.strftime('%Y-%m-%d %H:%M:%S')}."
        send_mail(
            'Email Verification OTP',
            message,
            'your-email@example.com',  # Replace with your sender email
            [instance.email],
            fail_silently=False,
        )


        serializer.save()

class VerifyEmailView(generics.UpdateAPIView):
    queryset = Registration.objects.all()
    serializer_class = RegistrationSerializer

    def update(self, request, *args, **kwargs):
        otp = request.data.get('otp')
        email = request.data.get('email')

        try:
            registration = Registration.objects.get(email=email)
        except Registration.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not registration.is_otp_valid():
            return Response({'error': 'OTP has expired.'}, status=status.HTTP_400_BAD_REQUEST)

        if str(registration.email_otp) == otp:
            registration.is_email_verified = True
            registration.email_otp = None  # Clear OTP
            registration.otp_expires_at = None
            registration.save()
            return Response({'success': 'Email verified successfully!'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

class ResendOTPView(APIView):
    """
    API endpoint to resend the OTP to a user's email.
    """
    def generate_otp(self):
        """Generate a random 6-digit OTP."""
        return random.randint(100000, 999999)

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            registration = Registration.objects.get(email=email)
        except Registration.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Generate a new OTP and update the instance with expiry time (e.g., 10 minutes from now)
        otp = self.generate_otp()
        otp_expiry = now() + timedelta(minutes=10)
        registration.email_otp = str(otp)
        registration.otp_expires_at = otp_expiry
        registration.save()

        # Prepare the email message and send it
        message = (
            f"Dear {registration.full_name},\n\n"
            f"Your new OTP for email verification is: {otp}\n\n"
            f"This OTP is valid until {otp_expiry.strftime('%Y-%m-%d %H:%M:%S')}."
        )
        send_mail(
            'Resend Email Verification OTP',
            message,
            'your-email@example.com',  # Replace with your sender email
            [registration.email],
            fail_silently=False,
        )

        return Response({'success': 'OTP resent successfully.'}, status=status.HTTP_200_OK)

class PaymentInitiationView(APIView):

    def post(self, request, *args, **kwargs):
        # Extract data from the request
        reg_id = request.data.get('registration_id')
        if not reg_id:
            return Response({'error': 'Registration ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            registration = Registration.objects.get(id=reg_id)
        except Registration.DoesNotExist:
            return Response({'error': 'Registration not found.'}, status=status.HTTP_404_NOT_FOUND)
        

        if not registration.is_email_verified:
            return Response({'error': 'Email is not verified. Please verify your email before proceeding.'}, 
                            status=status.HTTP_400_BAD_REQUEST)

        if registration.payment_status == 'success':
            return Response({'error': 'Payment already completed.'}, status=status.HTTP_400_BAD_REQUEST)

        # Razorpay client initialization
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY, settings.RAZORPAY_SECRET))

        # Create an order
        order_data = {
            "amount": 50000, 
            "currency": "INR",
            "receipt": f"receipt_{reg_id}",
            "payment_capture": 1 
        }

        try:
            order = client.order.create(data=order_data)
            order_id = order['id']

            # Save the order_id to the registration model
            registration.order_id = order_id
            registration.payment_reference = order_id  # Temporary use order_id as reference
            registration.save()

            # Send order details to the frontend
            return Response({
                "order_id": order_id,
                "amount": order_data['amount'],
                "currency": order_data['currency'],
                "razorpay_key": settings.RAZORPAY_KEY,
                "name": registration.full_name,
                "email": registration.email,
                "contact": registration.phone
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': 'Failed to create Razorpay order.', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

import json
import hmac
import hashlib
import logging
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Ensure logger configuration is set to capture DEBUG/INFO-level logs during testing.
logger = logging.getLogger(__name__)

@csrf_exempt
def razorpay_webhook(request):
    """
    Webhook endpoint to handle Razorpay events.
    It verifies the webhook signature using HMAC-SHA256 and processes the event.
    """
    logger.info(f"Webhook request received: {request.method}")
    if request.method != 'POST':
        logger.error("Invalid request method. Expected POST.")
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    payload = request.body
    print("Raw Payload:", payload)

    webhook_signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE', '')
    print("Webhook signature from header:", webhook_signature)
    if not webhook_signature:
        logger.error("Signature missing in request headers.")
        return JsonResponse({'error': 'Signature missing.'}, status=400)

    key_secret = settings.RAZORPAY_WEBHOOK_SECRET
    print("Key secret used:", key_secret)
    generated_signature = hmac.new(
        key_secret.encode('utf-8'), 
        payload, 
        hashlib.sha256
    ).hexdigest()
    print("Generated signature:", generated_signature)
    
    if not hmac.compare_digest(webhook_signature, generated_signature):
        logger.error("Signature mismatch: received signature does not match generated signature.")
        return JsonResponse({'error': 'Invalid signature.'}, status=400)

    try:
        event_data = json.loads(payload)
        print("Parsed Event Data:", event_data)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e} with payload: {payload}")
        return JsonResponse({'error': 'Invalid payload.'}, status=400)

    event = event_data.get('event')
    print("Event type received:", event)

    if event == 'payment.captured':
        payment_entity = event_data.get('payload', {}).get('payment', {}).get('entity', {})
        payment_id = payment_entity.get('id')
        order_id = payment_entity.get('order_id')
        print("Payment entity received:", payment_entity)
        print("Extracted order_id:", order_id)
        
        # Attempt to find the registration record.
        try:
            registration = Registration.objects.get(order_id=order_id)
            print(f"Registration found: {registration}")
        except Registration.DoesNotExist:
            print(f"Registration not found for order_id: {order_id}")
            logger.error(f"Registration not found for order_id: {order_id}")
            return JsonResponse({'error': 'Registration not found.'}, status=404)
        except Exception as ex:
            print("Unexpected exception when fetching Registration:", ex)
            logger.exception("Unexpected error fetching Registration record:")
            return JsonResponse({'error': 'Server error.'}, status=500)

        # Update the registration record.
        registration.payment_status = 'success'
        registration.payment_reference = payment_id
        registration.save()
        print(f"Registration updated: {registration}")
        logger.info(f"Payment captured and registration updated for order_id: {order_id}")
        return JsonResponse({'message': 'Payment captured and registration updated.'}, status=200)

    elif event == 'payment.failed':
        payment_entity = event_data.get('payload', {}).get('payment', {}).get('entity', {})
        payment_id = payment_entity.get('id')
        order_id = payment_entity.get('order_id')
        print("Processing payment.failed event for order_id:", order_id)
        
        try:
            registration = Registration.objects.get(order_id=order_id)
            print("Registration found for payment.failed:", registration)
        except Registration.DoesNotExist:
            print(f"Registration not found for order_id: {order_id} (payment.failed)")
            logger.error(f"Registration not found for order_id: {order_id} (payment.failed)")
            return JsonResponse({'error': 'Registration not found.'}, status=404)
        except Exception as ex:
            print("Unexpected exception when fetching Registration:", ex)
            logger.exception("Unexpected error fetching Registration record:")
            return JsonResponse({'error': 'Server error.'}, status=500)

        registration.payment_status = 'failed'
        registration.payment_reference = payment_id
        registration.save()
        print(f"Registration updated (failed): {registration}")
        logger.info(f"Payment failed and registration updated for order_id: {order_id}")
        return JsonResponse({'message': 'Payment failed and registration updated.'}, status=200)

    else:
        logger.warning(f"Unhandled event type received: {event}")
        print("Event not processed, unhandled event type:", event)
        return JsonResponse({'message': 'Event not processed.'}, status=200)



class PaymentStatusView(generics.RetrieveAPIView):
    queryset = Registration.objects.all()
    serializer_class = PaymentStatusSerializer
    lookup_field = 'id'
