from django.urls import path,include
from . import views

app_name="psychometrictests"
urlpatterns = [    
    path("stream-sorter",views.PsychometricTest.as_view(),name="psychometrictest"),
    path("career-direction",views.PsychometricTest12.as_view(),name="PsychometricTest12"),
    path("test-template/preview/",views.ModernTestTemplatePreview.as_view(),name="test_template_preview"),
    path("create-psychometric-test-payment",views.CreatePsychometricTestPayment.as_view(),name="createpsychomerticttestpayment"),
    path("create-psychometric-test-payment-eazypay",views.CreatePsychometricTestPaymentWithEazyPay.as_view(),name="createpsychomerticttestpaymenteazypay"),
    path("create-demo-psychometric-test-payment-eazypay",views.CreateDemoPsychometricTestPaymentWithEazyPay.as_view(),name="createdemopsychomerticttestpaymenteazypay"),
    path("delete-demo-psychometric-test-payment-eazypay",views.DeleteDemoPsychometricTestPaymentWithEazyPay.as_view(),name="deletedemopsychomerticttestpaymenteazypay"),
    path("update-psychometric-test-payment",views.UpdatePsychometricTestPayment.as_view(),name="psychomerticttestpaymentupdate"),
    path("update-psychometric-test-payment-eazypay",views.UpdatePsychometricTestPaymentWithEazyPay.as_view(),name="updatepsychomerticttestpaymenteazypay"),
    path("create-central-test-candidate",views.CreateCentralTestCandidate.as_view(),name="createcentraltestcandidate"),
    path('pychometrictest-payment-success/<str:enc_id>',views.UserPyschometricTestPaymentSuccess.as_view(),name="pyschometrictestpaymentsuccess"),
    path('pychometrictest-payment-fail/<str:enc_id>',views.UserPyschometricTestPaymentFail.as_view(),name="pyschometrictestpaymentfail"),
    path('pychometrictest-report/<int:id>',views.PyschometricTestResult.as_view(),name="pyschometrictestreport"),
    path("psychometrictest-update",views.UpdateCentralTest.as_view(),name="psychometrictestupdate"),
    path("fetch-candidate-test-link/<str:enc_id>",views.FetchCandidateTestLink.as_view(),name="fetchcandidatetestlink")
]