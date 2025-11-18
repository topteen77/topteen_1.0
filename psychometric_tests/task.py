from topteens.celery import app
from .models import PsychometricTestPayment,CandidateTest,PsychometricTestResult,CentralTestCandidate
from .central_test.centraltest import CentralTestService
from .utils import parse_xml_data
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from core import choices
@app.task()
def create_central_test_candidate(test_payment_id):
    test_payment=PsychometricTestPayment.objects.get(id=test_payment_id)
    test_payment.create_central_test_candidate() 
    print("Pschometric test created") 

@app.task()
def send_pychometric_test_payment_success_mail(test_payment_id):
    test_payment=PsychometricTestPayment.objects.get(id=test_payment_id)
    test_payment.send_payment_mail()
    print("Psychometric test payment mail send")

@app.task()
def central_test_automate():
    ctc=CentralTestCandidate.objects.filter(candidate_test__is_success=choices.YesNoChoices.NO)
    for c in ctc:
        c.last_test_is_success()

@app.task()
def create_pyschometric_assessment_result(candidate_test_id):
    assessment=CandidateTest.objects.get(id=candidate_test_id)
    ct=CentralTestService()
    full_xml_results,error=ct.get_assessment_results(assessment_id=assessment.assessment_id)
    factors_score,error=ct.get_assessment_factors_score(assessment_id=assessment.assessment_id)
    d=parse_xml_data(full_xml_results)
    result,_=PsychometricTestResult.objects.get_or_create(assessment=assessment)
    for f in factors_score:
        factor_name=f.get("factor_name").lower()
        if factor_name == "realistic":
            result.realistic=f.get("factor_score")
        elif factor_name =="investigative":
            result.investigative=f.get("factor_score")
        elif factor_name =="artistic":
            result.artistic=f.get("factor_score")
        elif factor_name =="social":
            result.social=f.get("factor_score")
        elif factor_name =="entrepreneurial":
            result.entrepreneurial=f.get("factor_score")
        elif factor_name =="conventional":
            result.conventional=f.get("factor_score")
    result.about=d.get("description_1")
    result.suggested_trades=d.get("description_2")
    pdf_url="https://app.centraltest.com/assessment{}&outputFormat=pdfTOC".format(d.get("candidate_pdf_key"))
    result.pdf_url=pdf_url
    result.save()
    file_path="media/upload/psychometrictestresult/{0}/psychometrictest_result_{1}.xml".format(result.id,result.id)
    with open(file_path,"w") as f:
        f.writelines(full_xml_results)
    result.xml_file_url=file_path
    result.save()
    print("Assessment results create")
