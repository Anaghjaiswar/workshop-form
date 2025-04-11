from django.contrib import admin
from .models import Registration


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    # Fields to display in the list view
    list_display = ('id','full_name', 'student_number', 'branch', 'year', 'gender', 'email', 'payment_status', 'is_email_verified', 'created_at')
    
    # Fields to add links to the detail view
    list_display_links = ('full_name', 'student_number')
    
    # Fields to filter the list view
    list_filter = ('branch', 'year', 'gender', 'living_type', 'payment_status', 'is_email_verified')
    
    # Fields to enable search functionality
    search_fields = ('full_name', 'student_number', 'email', 'phone')
    
    # Read-only fields for non-editable data
    readonly_fields = ('created_at', 'updated_at', 'payment_reference', 'order_id', 'payment_signature', 'email_otp', 'otp_expires_at')
    
    # Sections to organize the fields in the admin detail view
    fieldsets = (
        ("Personal Details", {
            'fields': ('full_name', 'student_number', 'branch', 'gender', 'year')
        }),
        ("Contact Details", {
            'fields': ('phone', 'email', 'living_type', 'is_email_verified')
        }),
        ("Email Verification", {
            'fields': ('email_otp', 'otp_expires_at')
        }),
        ("Payment Details", {
            'fields': ('payment_status', 'payment_reference', 'order_id', 'payment_signature')
        }),
        ("Timestamps", {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    # Custom actions
    actions = ['mark_payment_success', 'mark_email_verified']

    # Admin methods to perform bulk updates
    @admin.action(description="Mark selected registrations as Payment Success")
    def mark_payment_success(self, request, queryset):
        queryset.update(payment_status='success')
        self.message_user(request, "Selected registrations marked as Payment Success.")

    @admin.action(description="Mark selected registrations as Email Verified")
    def mark_email_verified(self, request, queryset):
        queryset.update(is_email_verified=True)
        self.message_user(request, "Selected registrations marked as Email Verified.")
