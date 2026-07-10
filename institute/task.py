from topteens.celery import app
from communication.com_service import ComService
from institute.models import StudentManagement,Institute,InstituteLog
from users.models import UserProfile
@app.task()
def create_student_and_send_mail(stu_manage_id,email,password,ins_name,image_url):
    sm=StudentManagement.objects.select_related('institute').get(id=stu_manage_id)
    if not sm.institute or not sm.institute.uses_package_psychometric_mode():
        sm.create_student_psychometric_test()
    import time
    time.sleep(20)
    test_link=sm.get_student_test_link()

    print("test_link",test_link)
    # test_link = "http://127.0.0.1:8000/test/home/"
    cs=ComService()
    cs.send_student_create_mail(email,password,ins_name,image_url,test_link)
    print("create_student_and_send_mail")

@app.task()
def update_student_data(ins_id,school):
    ins=Institute.objects.get(id=ins_id)
    sm_list=[u.student for u in StudentManagement.objects.filter(institute=ins)]
    for user in sm_list:
        get,create=UserProfile.objects.get_or_create(user=user,defaults={'schoolname':school})
        if get:
            get.schoolname=school
            get.save()
    print("student profile updated")

@app.task()
def send_institute_mail(email,password):
    cs=ComService()
    cs.send_institute_create_mail(email,password)
    print("counselor created mail successfully")

@app.task()
def send_counselor_mail(email,password):
    cs=ComService()
    cs.send_counselor_create_mail(email,password)
    print("Counselor created mail successfully")

@app.task()
def send_new_student_credential(email,password):
    cs=ComService()
    cs.send_student_change_password(email,password)
    print("send new credentials")

@app.task()
def institute_deletion_request(ins_id,ins_name,reason):
    cs=ComService()
    cs.send_institute_deletion_request(ins_id,ins_name,reason)
    print("send institute deletion request")

@app.task()
def create_institute_log(ins_id,email_list,email_count):
    ins=Institute.objects.get(id=ins_id)
    ins_log=InstituteLog(institute=ins,email=email_list,students_counts=email_count)
    ins_log.save()
    print("Create Institute Log")

@app.task()
def send_institute_group_mail(group_name,email,password):
    cs=ComService()
    cs.send_institute_group_create_mail(group_name,email,password)
    print("institute created mail successfully")