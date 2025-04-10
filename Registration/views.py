from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import razorpay
from rest_framework import status, generics
from rest_framework.response import Response
from .models import Registration
from .serializers import PaymentVerificationSerializer, RegistrationSerializer, PaymentStatusSerializer
import hmac
import hashlib
from django.conf import settings
import json
from rest_framework.views import APIView

class RegistrationCreateView(generics.CreateAPIView):
    queryset = Registration.objects.all()
    serializer_class = RegistrationSerializer

    def perform_create(self, serializer):
        # If you need to send an OTP or do any custom logic before save, do it here.
        serializer.save()


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

@csrf_exempt
def razorpay_webhook(request):
    """
    Webhook endpoint to handle Razorpay events.
    It verifies the webhook signature using HMAC-SHA256 and processes the event.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    # Retrieve the raw payload and the signature sent by Razorpay.
    payload = request.body
    webhook_signature = request.META.get('HTTP_X_RAZORPAY_SIGNATURE')
    if not webhook_signature:
        return JsonResponse({'error': 'Signature missing.'}, status=400)

    key_secret = settings.RAZORPAY_WEBHOOK_SECRET.encode()
    generated_signature = hmac.new(key_secret, payload, hashlib.sha256).hexdigest()

    if generated_signature != webhook_signature:
        return JsonResponse({'error': 'Invalid signature.'}, status=400)

    # Parse the webhook JSON payload.
    try:
        event_data = json.loads(payload)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid payload.'}, status=400)

    # Process different event types.
    event = event_data.get('event')
    # Example: Payment Captured Event
    if event == 'payment.captured':
        payment_entity = event_data.get('payload', {}).get('payment', {}).get('entity', {})
        payment_id = payment_entity.get('id')
        order_id = payment_entity.get('order_id')
        try:
            # Retrieve the corresponding registration using the Razorpay order ID.
            registration = Registration.objects.get(order_id=order_id)
        except Registration.DoesNotExist:
            return JsonResponse({'error': 'Registration not found.'}, status=404)
        # Update the registration record.
        registration.payment_status = 'success'
        registration.payment_reference = payment_id
        registration.save()
        return JsonResponse({'message': 'Payment captured and registration updated.'}, status=200)

    # Example: Payment Failed Event.
    elif event == 'payment.failed':
        payment_entity = event_data.get('payload', {}).get('payment', {}).get('entity', {})
        payment_id = payment_entity.get('id')
        order_id = payment_entity.get('order_id')
        try:
            registration = Registration.objects.get(order_id=order_id)
        except Registration.DoesNotExist:
            return JsonResponse({'error': 'Registration not found.'}, status=404)
        registration.payment_status = 'failed'
        registration.payment_reference = payment_id
        registration.save()
        return JsonResponse({'message': 'Payment failed and registration updated.'}, status=200)

    # For other events, optionally log or handle them as needed.
    return JsonResponse({'message': 'Event not processed.'}, status=200)


class PaymentStatusView(generics.RetrieveAPIView):
    queryset = Registration.objects.all()
    serializer_class = PaymentStatusSerializer
    lookup_field = 'id'