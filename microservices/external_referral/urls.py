from django.urls import path

from microservices.external_referral.modules.referrals import ExternalReferralView



urlpatterns = [
    # Reports URLs
    path('external-referral', ExternalReferralView.as_view(), name='external-referral'),
    path('external-referral/<str:uid>', ExternalReferralView.as_view(), name='external-referral'),

]

