#-*- coding: utf-8 -*-
import logging
from decimal import Decimal
from hashlib import md5, sha1
from base64 import urlsafe_b64encode as b64encode
import random, string

from django.conf import settings
from django.conf.urls.defaults import patterns, url, include
from django.contrib.sites.models import get_current_site
from django.core.urlresolvers import reverse
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext
from django.views.decorators.csrf import csrf_exempt

from paypal.standard.forms import PayPalPaymentsForm
from paypal.standard.pdt.signals import (
  pdt_successful as success_signal,
  pdt_failed as failed_signal,
)

from shop import order_signals

logger = logging.getLogger('paypal.pdt')


class OffsitePDTPaypalBackend(object):
    backend_name = "Paypal"
    url_namespace = "paypal"

    def __init__(self, shop):
        self.shop = shop
        # Hook the payment was successful listener on the appropriate signal sent
        # by django-paypal (success_signal)
        assert settings.PAYPAL_RECEIVER_EMAIL, "You need to define a PAYPAL_RECEIVER_EMAIL in settings with the money recipient's email addresss"
        assert settings.PAYPAL_CURRENCY_CODE, "You need to define a PAYPAL_CURRENCY_CODE in settings with the currency code"

        success_signal.connect(self.payment_was_successful, weak=False,
          dispatch_uid='django-shop-paypal_offsite_payment-successful')
        failed_signal.connect(self.payment_failed, weak=False,
          dispatch_uid='django-shop-paypal_offsite_payment-unsuccessful')

    def get_urls(self):
        urlpatterns = patterns('',)
        #TODO: build urls

    def get_form(self, request):
        '''
        Configures a paypal form and returns. Allows this code to be reused
        in other views.
        '''
        order = self.shop.get_order(request)
        url_scheme = 'https' if request.is_secure() else 'http'
        # get_current_site requires Django 1.3 - backward compatibility?
        url_domain = get_current_site(request).domain

        #TODO: build form dict

