from django.http import Http404, HttpResponseRedirect
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.eazypay_callback import process_eazypay_callback


class UpdateEazyPayPayment(APIView):
    """ICICI EazyPay browser return URL. Unauthenticated (gateway redirects the customer here)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        _payment, _payment_status, redirect_url, err = process_eazypay_callback(request)
        if err == 'payment_not_found':
            raise Http404('Payment not found')
        if err:
            return Response({'detail': err}, status=status.HTTP_400_BAD_REQUEST)

        is_api = request.GET.get('is_api')
        if is_api:
            return Response(status=status.HTTP_200_OK)
        if not redirect_url:
            return HttpResponseRedirect('/')
        return HttpResponseRedirect(redirect_url)
