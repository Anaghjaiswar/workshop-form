import random
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import razorpay
import requests
from rest_framework import status, generics
from rest_framework.response import Response

from utils.rsa_utils import rsa_decrypt
from .models import Registration
from .serializers import  RegistrationSerializer, PaymentStatusSerializer, EmailStatusCheckSerializer
import hmac
import hashlib
from django.conf import settings
import json
from rest_framework.views import APIView
import logging
from rest_framework.exceptions import APIException, ValidationError
from django.utils.timezone import now, timedelta
from django.core.mail import send_mail
from django.utils import timezone
from django.db import transaction, IntegrityError
from rest_framework.throttling import AnonRateThrottle
from .custom_throttles import RegistrationCreateThrottle

# RECAPTCHA_SECRET_KEY = settings.RECAPTCHA_SECRET_KEY
# RECAPTCHA_THRESHOLD = settings.RECAPTCHA_THRESHOLD


# def verify_recaptcha(token, action):
#     url = 'https://www.google.com/recaptcha/api/siteverify'
#     data = {
#         'secret': RECAPTCHA_SECRET_KEY,
#         'response': token,
#     }
#     result = requests.post(url, data=data).json()
#     # Check if verification is successful and the action matches
#     if result.get('success') and result.get('action') == action:
#         return result.get('score', 0) >= RECAPTCHA_THRESHOLD
#     return False

logger = logging.getLogger(__name__)

class RegistrationCreateView(generics.CreateAPIView):
    queryset = Registration.objects.all()
    serializer_class = RegistrationSerializer
    throttle_classes = [RegistrationCreateThrottle]

    def generate_otp(self):
        """Generate a random 6-digit OTP."""
        return random.randint(100000, 999999)
    
    def hash_otp(self, otp):
        """Hash the OTP for secure storage."""
        return hashlib.sha256(str(otp).encode()).hexdigest()

    def perform_create(self, serializer):
        # recaptcha_token = self.request.data.get("recaptchaToken")
        # if not recaptcha_token:
        #     raise ValidationError({"recaptcha": "reCAPTCHA token is missing."})
        
        # # Verify the token using your separately defined function.
        # # Make sure the action ("register") matches what you're using on the front end.
        # if not verify_recaptcha(recaptcha_token, "register"):
        #     raise ValidationError({"recaptcha": "reCAPTCHA verification failed."})
        try:
            # Wrap the creation process in a transaction so that we can roll back on error
            with transaction.atomic():
                # Save the instance from serializer
                instance = serializer.save()

                # Generate OTP and set expiration
                otp = self.generate_otp()
                otp_expiry = timezone.localtime(now() + timedelta(minutes=10))

                # Update the instance with OTP and expiration time
                instance.email_otp = str(otp)
                instance.otp_expires_at = otp_expiry
                instance.save()

                # Prepare email message
                plain_message = (
                    f"Dear {instance.full_name},\n\n"
                    f"Your OTP for email verification is: {otp}\n\n"
                    f"This OTP is valid until {otp_expiry.strftime('%Y-%m-%d %H:%M:%S')}.\n\n"
                    "If you did not request this verification, please ignore this email.\n\n"
                    "Sincerely,\nCSI Team"
                )

                # HTML message with inline CSS and CSI logo image
                html_message = f"""
                <html>
                  <body style="margin:0; padding:0; font-family: Arial, sans-serif;">
                    <table align="center" width="600" style="border:1px solid #dddddd; border-radius:4px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                      <tr>
                        <td style="padding:20px; text-align:center; background-color:#f7f7f7;">
                          <img src="https://res.cloudinary.com/dcbla9zbl/image/upload/v1744550174/tnwwrwlomvtgljiobpxg.jpg" alt="CSI Logo" style="width:100px;">
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:20px;">
                          <h2 style="color:#2A7AE2; margin-top:0;">Workshop Verification Code</h2>
                          <p>Dear {instance.full_name},</p>
                          <p>We received a request to verify your email address: <strong>{instance.email}</strong> as part of your workshop registration.</p>
                          <p>Your verification code is:</p>
                          <div style="font-size:24px; font-weight:bold; color:#333; margin: 10px 0;">{otp}</div>
                          <p>This OTP is valid until <strong>{otp_expiry.strftime('%Y-%m-%d %H:%M:%S')}</strong>.</p>
                          <p>If you did not request this verification, please ignore this email.</p>
                          <p>Sincerely,<br>CSI Team</p>
                        </td>
                      </tr>
                    </table>
                  </body>
                </html>
                """

                # Send the email with both plain and HTML content
                send_mail(
                    'Email Verification OTP',
                    plain_message,
                    'jaiswaranagh@gmail.com',  # Replace with your sender email
                    [instance.email],
                    html_message=html_message,
                    fail_silently=False,
                )

        except IntegrityError as ie:
            # If it's a duplicate email, raise a ValidationError (which returns a 400 status code)
            raise ValidationError({"error": "Registration with this email already exists. Please use a different email or login."})

        except Exception as e:
            # Log the error as needed and raise an API exception
            raise APIException("Registration failed due to an error: " + str(e))

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

class ResendOTPThrottle(AnonRateThrottle):
    rate = '3/min'


class ResendOTPView(APIView):
    """
    API endpoint to resend the OTP to a user's email.
    """
    throttle_classes = [ResendOTPThrottle]
    
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
        otp_expiry = timezone.localtime(now() + timedelta(minutes=10))
        registration.email_otp = str(otp)
        registration.otp_expires_at = otp_expiry
        registration.save()

        plain_message = (
            f"Dear {registration.full_name},\n\n"
            f"Your OTP for email verification is: {otp}\n\n"
            f"This OTP is valid until {otp_expiry.strftime('%Y-%m-%d %H:%M:%S')}.\n\n"
            "If you did not request this verification, please ignore this email.\n\n"
            "Sincerely,\nCSI Team"
        )

        html_message = f"""
<html>
  <body style="margin:0; padding:0; font-family: Arial, sans-serif;">
    <table align="center" width="600" style="border:1px solid #dddddd; border-radius:4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); background-color:#ffffff;">
      <tr>
        <td style="padding:20px; text-align:center; background-color:#ffffff; border-bottom: 2px solid #eeeeee;">
          <img src="https://res.cloudinary.com/doctqxch9/image/upload/v1744829056/logocsiCenter_Background_Removed_qu85rk.png" alt="CSI Logo" style="width:100px; height:auto;">
        </td>
      </tr>
      <tr>
        <td style="padding:20px;">
          <h2 style="color:#333333; text-align:center;">Render 3.0 Verification Code</h2>
          <p>Dear <span style="font-weight:bold; color:#0078d4;">{registration.full_name}</span>,</p>
          <p>We received a request to verify your email address as part of your registration.</p>
          <div style="margin:20px 0; text-align:center; font-size:24px; font-weight:bold; color:#333333; border:2px dashed #555555; padding:15px; border-radius:8px; background-color:#f9f9f9;">
            {otp}
          </div>
          <p>This OTP is valid until <span style="font-weight:bold; color:#0078d4;">{otp_expiry.strftime('%Y-%m-%d %H:%M:%S')} IST</span>.</p>
          <p>If you did not request this verification, please ignore this email.</p>
          <p>Best regards,<br><strong>CSI Team</strong></p>
        </td>
      </tr>
      <tr>
        <td style="padding:10px; text-align:center; background-color:#f4f4f4; font-size:14px; color:#555555;">
          © 2025 CSI. All rights reserved.
        </td>
      </tr>
    </table>
  </body>
</html>
"""


        # Send the email with both plain and HTML content
        send_mail(
            'Email Verification OTP',
            plain_message,
            'jaiswaranagh@gmail.com',  # Replace with your sender email
            [registration.email],
            html_message=html_message,
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
            "amount": 10000, 
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
    # print("Key secret used:", key_secret)
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
        subject = "Workshop Registration - Payment Successful"
        plain_message = (
            f"Dear {registration.full_name},\n\n"
            "Your payment was successful. Thank you for registering!"
        )
        html_message = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif;">
            <h2 style="color: #2A7AE2;">Workshop Registration - Payment Successful</h2>
            <p>Dear {registration.full_name},</p>
            <p>Your payment of <strong>₹{payment_entity.get('amount', 'N/A')/100:.2f}</strong> for the workshop has been successfully received.</p>
            <p>Your Payment ID is: <strong>{payment_id}</strong></p>
            <p>We are excited to have you join us!</p>
            <p><img src="https://res.cloudinary.com/dcbla9zbl/image/upload/v1744550174/tnwwrwlomvtgljiobpxg.jpg" alt="Your Logo" style="width:150px;"></p>
            <p>Thank you for registering.</p>
            <p>Best regards,<br>Workshop Team</p>
            </div>
        </body>
        </html>
        """

        send_mail(
            subject,
            plain_message,
            'jaiswarnagh@gmail.com',  # Replace with your sender email
            [registration.email],
            html_message=html_message,
            fail_silently=False,
        )
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
        subject = "Workshop Registration - Payment Failed"
        payment_amount = payment_entity.get("amount", 0)
        plain_message = (
            f"Dear {registration.full_name},\n\n"
            f"Unfortunately, your payment of ₹{payment_amount/100:.2f} for the workshop has failed.\n"
            f"Payment ID: {payment_id}\n\n"
            "Please retry the payment or contact support if you need assistance.\n\n"
            "Best regards,\nWorkshop Team"
        )
        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; margin:0; padding:0;">
            <table align="center" width="600" style="border:1px solid #dddddd; border-radius:4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <tr>
                <td style="padding:20px; text-align:center; background-color:#f7f7f7;">
                    <img src="https://res.cloudinary.com/dcbla9zbl/image/upload/v1744550174/tnwwrwlomvtgljiobpxg.jpg" alt="CSI Logo" style="width:100px;">
                </td>
                </tr>
                <tr>
                <td style="padding:20px;">
                    <h2 style="color:#D9534F; margin-top:0;">Payment Failed</h2>
                    <p>Dear {registration.full_name},</p>
                    <p>Unfortunately, your payment of <strong>₹{payment_amount/100:.2f}</strong> for the workshop has failed.</p>
                    <p>Your Payment ID is: <strong>{payment_id}</strong></p>
                    <p>Please retry your payment or contact our support if you need assistance.</p>
                    <p>Best regards,<br>Workshop Team</p>
                </td>
                </tr>
            </table>
            </body>
        </html>
        """

        send_mail(
            subject,
            plain_message,
            'jaiswarnagh@gmail.com', 
            [registration.email],
            html_message=html_message,
            fail_silently=False,
        )
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


class CheckEmailStatusThrottle(AnonRateThrottle):
    rate = '10/min'

class CheckEmailStatusView(APIView):
    throttle_classes = [CheckEmailStatusThrottle]
    def post(self, request, *args, **kwargs):
        serializer = EmailStatusCheckSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                # Check if the email exists in the database
                registration = Registration.objects.get(email=email)

                # If email is not verified, send OTP and ask for verification
                if not registration.is_email_verified:
                    # Generate OTP
                    otp = str(random.randint(100000, 999999))
                    registration.email_otp = otp
                    otp_expiry = registration.otp_expires_at = timezone.localtime(now() + timedelta(minutes=10))
                    registration.save()

                    # Send OTP to email
                    plain_message = (
                        f"Dear {registration.full_name},\n\n"
                        f"Your OTP for email verification is: {otp}\n"
                        f"This OTP is valid until {otp_expiry.strftime('%Y-%m-%d %H:%M:%S')} IST.\n\n"
                        "If you did not request this verification, please ignore this email.\n\n"
                        "Sincerely,\nWorkshop Team"
                    )


                    html_message = f"""
                    <html>
                      <body style="margin:0; padding:0; font-family: Arial, sans-serif;">
                        <table align="center" width="600" style="border:1px solid #dddddd; border-radius:4px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">
                          <tr>
                            <td style="padding:20px; text-align:center; background-color:#f7f7f7;">
                              <img src="https://res.cloudinary.com/dcbla9zbl/image/upload/v1744550174/tnwwrwlomvtgljiobpxg.jpg" alt="CSI Logo" style="width:100px;">
                            </td>
                          </tr>
                          <tr>
                            <td style="padding:20px;">
                              <h2 style="color:#2A7AE2; margin-top:0;">Workshop OTP Verification</h2>
                              <p>Dear {registration.full_name},</p>
                              <p>We received a request to verify your email address: <strong>{registration.email}</strong> as part of your workshop registration.</p>
                              <p>Your OTP is:</p>
                              <div style="font-size:24px; font-weight:bold; color:#333; margin: 10px 0;">{otp}</div>
                              <p>This OTP is valid until <strong>{otp_expiry.strftime('%Y-%m-%d %H:%M:%S')} IST</strong>.</p>
                              <p>If you did not request this, please ignore this email.</p>
                              <p>Sincerely,<br>Workshop Team</p>
                            </td>
                          </tr>
                        </table>
                      </body>
                    </html>
                    """

                    send_mail(
                        subject="OTP Verification",
                        message=plain_message,
                        from_email="jaiswaranagh@gmail.com", 
                        recipient_list=[email],
                        html_message=html_message,
                        fail_silently=False,
                    )

                    return Response({
                        "user_exists": True,
                        "message": "Email is registered but not verified. OTP has been sent.",
                        "redirect_to_otp_verification": True,
                        "registration_id": registration.id,
                        "email": email
                    }, status=status.HTTP_200_OK)

                # If email is verified, check payment status
                if registration.payment_status in ['pending', 'failed']:
                    return Response({
                        "user_exists": True,
                        "message": f"Payment status is {registration.payment_status}. Redirecting to payment page.",
                        "redirect_to_payment": True,
                        "registration_id": registration.id
                    }, status=status.HTTP_200_OK)

                # If payment is successful
                return Response({
                    "user_exists": True,
                    "message": "You have already successfully registered for the workshop.",
                    "redirect_to_payment": False,
                }, status=status.HTTP_200_OK)

            except Registration.DoesNotExist:
                # Email does not exist, continue normal flow
                return Response({
                    "user_exists": False,
                    "message": "Email does not exist. Continue with registration.",
                }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
