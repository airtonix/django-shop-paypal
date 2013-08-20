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
from paypal.standard.ipn.signals import (
  payment_was_successful as success_signal,
  payment_was_flagged as flagged_signal,
  subscription_cancel as subscription_cancel_signal,
  subscription_eot as subscription_eot_signal,
  subscription_modify as subscription_modify_signal,
  subscription_signup as subscription_signup_signal,
  recurring_create as recurring_create_signal,
  recurring_payment as recurring_payment_signal,
  recurring_cancel as recurring_cancel_signal,
)

from shop import order_signals

logger = logging.getLogger('paypal.ipn')

IPN_RETURN_URLBASE = getattr(settings, "SHOP_PAYPAL_IPN_RETURN_URLBASE", "something-something-something-darkside")


class OffsiteIPNPaypalBackend(object):
    '''
    Glue code to let django-SHOP talk to django-paypal's.

    The django-paypal package already defines an IPN view, that logs everything
    to the database (desirable), and fires up a signal.
    It is therefore more convenient to listen to the signal instead of rewriting
    the ipn view (and necessary tests)
    '''

    backend_name = "Paypal"
    url_namespace = "paypal"

    #===========================================================================
    # Defined by the backends API
    #===========================================================================

    def __init__(self, shop):
        self.shop = shop
        # Hook the payment was successful listener on the appropriate signal sent
        # by django-paypal (success_signal)
        assert settings.PAYPAL_RECEIVER_EMAIL, "You need to define a PAYPAL_RECEIVER_EMAIL in settings with the money recipient's email addresss"
        assert settings.PAYPAL_CURRENCY_CODE, "You need to define a PAYPAL_CURRENCY_CODE in settings with the currency code"
        success_signal.connect(self.payment_was_successful, weak=False)
        flagged_signal.connect(self.payment_was_flagged, weak=False)
        subscription_cancel_signal.connect(self.subscription_cancelled, weak=False)
        subscription_eot_signal.connect(self.subscription_expired, weak=False)
        subscription_modify_signal.connect(self.subscription_modified, weak=False)
        subscription_signup_signal.connect(self.subscription_signup_success, weak=False)
        recurring_create_signal.connect(self.recurring_created, weak=False)
        recurring_payment_signal.connect(self.recurring_payment, weak=False)
        recurring_cancel_signal.connect(self.recurring_cancelled, weak=False)

    def get_urls(self):
        urlpatterns = patterns('',
            url(r'^$', self.view_that_asks_for_money, name='paypal'),
            url(r'^success/$', self.paypal_successful_return_view, name='paypal_success'),
            url(r'^{0}/ipn/$'.format(IPN_RETURN_URLBASE), include('paypal.standard.ipn.urls')),
        )
        return urlpatterns

    def get_form(self, request):
        '''
        Configures a paypal form and returns. Allows this code to be reused
        in other views.
        '''
        order = self.shop.get_order(request)
        url_scheme = 'https' if request.is_secure() else 'http'
        # get_current_site requires Django 1.3 - backward compatibility?
        url_domain = get_current_site(request).domain
        paypal_dict = {
        "business": settings.PAYPAL_RECEIVER_EMAIL,
        "currency_code": settings.PAYPAL_CURRENCY_CODE,
        "amount": self.shop.get_order_total(order),
        "item_name": self.shop.get_order_short_name(order),
        "invoice": self.shop.get_order_unique_id(order),
        "notify_url": '%s://%s%s' % (url_scheme,
            url_domain, reverse('paypal-ipn')),  # defined by django-paypal
        "return_url": '%s://%s%s' % (url_scheme,
            url_domain, reverse('paypal_success')),  # That's this classe's view
        "cancel_return": '%s://%s%s' % (url_scheme,
            url_domain, self.shop.get_cancel_url()),  # A generic one
        }
        if hasattr(settings, 'PAYPAL_LC'):
            paypal_dict['lc'] = settings.PAYPAL_LC

        # Create the instance.
        form = PayPalPaymentsForm(initial=paypal_dict)
        return form

    #===========================================================================
    # Views
    #===========================================================================

    def view_that_asks_for_money(self, request):
        '''
        We need this to be a method and not a function, since we need to have
        a reference to the shop interface
        '''
        form = self.get_form(request)
        context = {"form": form}
        rc = RequestContext(request, context)
        order = self.shop.get_order(request)
        order_signals.confirmed.send(sender=self, order=order, request=request)
        return render_to_response("shop_paypal/payment.html", rc)

    @csrf_exempt
    def paypal_successful_return_view(self, request):
        order = self.shop.get_order(request)
        order_signals.completed.send(sender=self, order=order, request=request)
        rc = RequestContext(request, {})
        return render_to_response("shop_paypal/success.html", rc)

    #===========================================================================
    # Signal listeners
    #===========================================================================
    def recurring_payment(self, sender, **kwargs):
        ''' '''
        logger.info("Recurring Payment Made : transaction_id: {transaction_id}, Sender: {sender}, OrderID {order_id}, Total: {total}".format(
          transaction_id=transaction_id,
          sender = sender,
          order_id = order_id,
          total = total))

    def recurring_created(self, sender, **kwargs):
        ''' '''
        logger.info("Recurring Payment Created : transaction_id: {transaction_id}, Sender: {sender}, OrderID {order_id}, Total: {total}".format(
          transaction_id=transaction_id,
          sender = sender,
          order_id = order_id,
          total = total))

    def recurring_cancelled(self, sender, **kwargs):
        ''' '''
        logger.info("Recurring Payment Cancelled : transaction_id: {transaction_id}, Sender: {sender}, OrderID {order_id}, Total: {total}".format(
          transaction_id=transaction_id,
          sender = sender,
          order_id = order_id,
          total = total))


    def subscription_cancelled(self, sender, **kwargs):
        ''' '''
        logger.info("Subscription Cancelled : transaction_id: {transaction_id}, Sender: {sender}, OrderID {order_id}, Total: {total}".format(
          transaction_id=transaction_id,
          sender = sender,
          order_id = order_id,
          total = total))

    def subscription_expired(self, sender, **kwargs):
        ''' '''
        logger.info("Subscription Expired : transaction_id: {transaction_id}, Sender: {sender}, OrderID {order_id}, Total: {total}".format(
          transaction_id=transaction_id,
          sender = sender,
          order_id = order_id,
          total = total))

    def subscription_modified(self, sender, **kwargs):
        ''' '''
        logger.info("Subscription Modified : transaction_id: {transaction_id}, Sender: {sender}, OrderID {order_id}, Total: {total}".format(
          transaction_id=transaction_id,
          sender = sender,
          order_id = order_id,
          total = total))

    def subscription_signup_success(self, sender, **kwargs):
        ''' '''
        logger.info("Subscription Signup : transaction_id: {transaction_id}, Sender: {sender}, OrderID {order_id}, Total: {total}".format(
          transaction_id=transaction_id,
          sender = sender,
          order_id = order_id,
          total = total))

    def payment_was_flagged(self, sender, **kwargs):
        '''payment_was_flagged
        '''
        logger.info("Payment Flagged : transaction_id: {transaction_id}, Sender: {sender}, OrderID {order_id}, Total: {total}".format(
          transaction_id=transaction_id,
          sender = sender,
          order_id = order_id,
          total = total))

    def payment_was_successful(self, sender, **kwargs):
        '''
        This listens to the signal emitted by django-paypal's IPN view and in turn
        asks the shop system to record a successful payment.
        '''
        ipn_obj = sender
        order_id = ipn_obj.invoice  # That's the "invoice ID we passed to paypal
        amount = Decimal(ipn_obj.mc_gross)
        transaction_id = ipn_obj.txn_id

        logger.info("Successful payment : transaction_id: {transaction_id}, Sender: {sender}, OrderID {order_id}, Total: {total}".format(
          transaction_id=transaction_id,
          sender = sender,
          order_id = order_id,
          total = total))

        # The actual request to the shop system
        self.shop.confirm_payment(self.shop.get_order_for_id(order_id), amount, transaction_id, self.backend_name)
