# custom_throttles.py
from rest_framework.throttling import AnonRateThrottle

class RegistrationCreateThrottle(AnonRateThrottle):
    rate = '5/min'  # Limit to 5 requests per minute for anonymous clients
