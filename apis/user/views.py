from core import choices
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions,authentication
from rest_framework import status
from django.shortcuts import get_object_or_404
from careers.models import Career,CareerShortlist
from django.shortcuts import get_object_or_404
from users.models import UserNote,UserFolder,FolderFile
from core.models import Hobbies
from colleges.models import College,CollegeShortlist
from core.models import EntranceTestPrepExam
from users.models import UserResume,UserResumeSkill,UserResumeCertificate,UserResumeInternship,UserResumeActivity,UserResumeVolunteerInvolvement
from django.template.loader import render_to_string
from core.models import Configuration
from skilllab.models import SkilllabCoursePayment,SkillLabCourse
from payments.models import Payment
import json
from skilllab.task import send_skillabcourse_payment_success_mail


class ShortlistCourseAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request):
        career_slug = request.POST.get('careerslug', False)
        data = {}
        
        career= get_object_or_404(Career,slug=career_slug)
        user= request.user
        career_shortlisted,_ = CareerShortlist.objects.get_or_create(user=user,career=career) 
        if _ :
            data['message'] = "Career Shortlisted"
            data['value'] = "Remove Shortlisted"
            return Response(data, status=status.HTTP_200_OK)
        else:
            data['message'] = "Removed Shortlisted"
            data['value'] = "Shortlist Career"
            career_shortlisted.delete()
            return Response(data, status=status.HTTP_200_OK) 

class ShortlistCollegeAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request):
        college_slug = request.POST.get('collegeslug', False)
        data = {}
        
        college= get_object_or_404(College,slug=college_slug)
        user= request.user
        college_shortlisted,_ = CollegeShortlist.objects.get_or_create(user=user,college=college) 
        if _ :
            data['message'] = "College Shortlisted"
            data['value'] = "Remove Shortlisted"
            return Response(data, status=status.HTTP_200_OK)
        else:
            data['message'] = "Removed Shortlisted"
            data['value'] = "Shortlist College"
            college_shortlisted.delete()
            return Response(data, status=status.HTTP_200_OK)

class ShortlistExamAPI(APIView):
    """Bookmark/unbookmark Entrance Test Prep exams (EntranceTestPrepExam)."""
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request):
        exam_id = request.POST.get('examid', False)
        data = {}
        
        if not exam_id:
            return Response({'message': 'Exam ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        exam = get_object_or_404(EntranceTestPrepExam, id=exam_id)
        user = request.user
        
        if exam.shortlist.filter(id=user.id).exists():
            exam.shortlist.remove(user)
            data['message'] = "Exam removed from bookmarks"
            data['success'] = False
            return Response(data, status=status.HTTP_200_OK)
        else:
            exam.shortlist.add(user)
            data['message'] = "Exam bookmarked"
            data['success'] = True
            return Response(data, status=status.HTTP_200_OK) 

class UserNoteSave(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request):
        try:
            id = request.data.get('obj_id',None)
            title = request.data.get('title',None)
            content = request.data.get('content',None)
            if id:    
                note=get_object_or_404(UserNote,id=id,user=request.user)  
                note.title=title
                note.content=content
                note.save()    
                return Response("note save successfully", status=status.HTTP_200_OK)
            else:
                return Response("Something went wrong.try again", status=status.HTTP_400_BAD_REQUEST)      
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            print("aslkahsdf",e)

        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST)  

class UserNoteDelete(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request):
        try:
            id = request.data.get('obj_id', None)
            if id:
                note = get_object_or_404(UserNote, id=id, user=request.user)
                note.delete()
                return Response("note deleted successfully", status=status.HTTP_200_OK)
            return Response("Something went wrong.try again", status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            print("aslkahsdf", e)

        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST)

class DeleteUserHobbie(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]
    def post(self, request):
        try:
            id = request.data.get('hobbie_id',None)
            if id:
                hobbie=get_object_or_404(Hobbies,id=int(id))
                hobbies=request.user.user_profile.hobbies.remove(hobbie)
                return Response("Hobbie remove successfully", status=status.HTTP_200_OK)
            else:
                return Response("Something went wrong.try again", status=status.HTTP_400_BAD_REQUEST)      
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            print("aslkahsdf",e)

        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST)  

class UserResumeAbout(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="All Fields are required"
        about = request.data.get("about")
        if about:
            resume,_ = UserResume.objects.get_or_create(user=request.user)
            resume.about = about
            resume.save()
            data['htmld']=render_to_string("topteenfrontend/includes/resumeaboutd.html",{'resume':resume})
            data['htmlm']=render_to_string("topteenfrontend/includes/resumeaboutm.html",{'resume':resume})
            data['message']="About added successfully"
            return Response(data, status=status.HTTP_200_OK)
        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST)  

class UserResumeSkillAdd(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="All Fields are required"
        title = request.data.get("skilltitle")
        desc = request.data.get('skilldesc')
        profficiency=request.data.get('skillprofficiency')
        if title and desc and profficiency:
            resume,_=UserResume.objects.get_or_create(user=request.user)
            skiill,_=UserResumeSkill.objects.get_or_create(resume=resume,title=title)
            skiill.description=desc
            skiill.profficiency=profficiency
            skiill.save()

            resumeskill=UserResumeSkill.objects.filter(resume=resume)
            data['htmld']=render_to_string("topteenfrontend/includes/resumeskilld.html",{'resumeskill':resumeskill})
            data['htmlm']=render_to_string("topteenfrontend/includes/resumeskillm.html",{'resumeskill':resumeskill})
            data["count"]=resumeskill.count()
            data["message"]="Skill Added successfully"
            return Response(data, status=status.HTTP_200_OK)
        id = request.data.get('id',None)
        if id:
            skiill=get_object_or_404(UserResumeSkill,id=int(id))
            skiill.delete()
            resume,_=UserResume.objects.get_or_create(user=request.user)
            resumeskill=UserResumeSkill.objects.filter(resume=resume)
            data['htmld']=render_to_string("topteenfrontend/includes/resumeskilld.html",{'resumeskill':resumeskill})
            data['htmlm']=render_to_string("topteenfrontend/includes/resumeskillm.html",{'resumeskill':resumeskill})
            data["count"]=resumeskill.count()
            data["message"]="Skill delete successfully"
            return Response(data, status=status.HTTP_200_OK)
        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST)  

class UserResumeCertificationAdd(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="All Fields are required"
        title = request.POST.get("certificatetitle")
        desc = request.POST.get("certificatedescription")
        date = request.POST.get("issuedate")

        if title and desc and date:
            resume,_=UserResume.objects.get_or_create(user=request.user)
            certificate,_=UserResumeCertificate.objects.get_or_create(resume=resume,title=title)
            certificate.description=desc
            certificate.issue_date=date
            certificate.save()
            resumecertificate=UserResumeCertificate.objects.filter(resume=resume)
            data['htmld']=render_to_string("topteenfrontend/includes/resumecertificated.html",{'resumecertificate':resumecertificate})
            data['htmlm']=render_to_string("topteenfrontend/includes/resumecertificatem.html",{'resumecertificate':resumecertificate})
            data['count']=resumecertificate.count()
            data["message"]="Certificate Added successfully"
            return Response(data, status=status.HTTP_200_OK)
        id = request.data.get('id',None)
        if id:
            certificate=get_object_or_404(UserResumeCertificate,id=int(id))
            certificate.delete()
            resume,_=UserResume.objects.get_or_create(user=request.user)
            resumecertificate=UserResumeCertificate.objects.filter(resume=resume)
            data['htmld']=render_to_string("topteenfrontend/includes/resumecertificated.html",{'resumecertificate':resumecertificate})
            data['htmlm']=render_to_string("topteenfrontend/includes/resumecertificatem.html",{'resumecertificate':resumecertificate})
            data['count']=resumecertificate.count()
            data["message"]="Certificate Deleted successfully"
            return Response(data, status=status.HTTP_200_OK)
        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST) 

class UserResumeInternshipAdd(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="All Fields are required"
        provider = request.POST.get("provider")
        role = request.POST.get("role")
        desc = request.POST.get("internshipdescription")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")

        if provider and desc and role and start_date and end_date:
            resume,_=UserResume.objects.get_or_create(user=request.user)
            internship=UserResumeInternship.objects.create(resume=resume)
            internship.provider=provider
            internship.role=role
            internship.description=desc
            internship.start_date=start_date
            internship.end_date=end_date
            internship.save()
            resumeinternship=UserResumeInternship.objects.filter(resume=resume)
            data['htmld']=render_to_string("topteenfrontend/includes/resumeinternshipd.html",{'resumeinternship':resumeinternship})
            data['htmlm']=render_to_string("topteenfrontend/includes/resumeinternshipm.html",{'resumeinternship':resumeinternship})
            data['count']=resumeinternship.count()
            data["message"]="Internship Added successfully"
            return Response(data, status=status.HTTP_200_OK)
        id = request.data.get('id',None)
        if id:
            internship=get_object_or_404(UserResumeInternship,id=int(id))
            internship.delete()
            resume,_=UserResume.objects.get_or_create(user=request.user)
            resumeinternship=UserResumeInternship.objects.filter(resume=resume)
            data['htmld']=render_to_string("topteenfrontend/includes/resumeinternshipd.html",{'resumeinternship':resumeinternship})
            data['htmlm']=render_to_string("topteenfrontend/includes/resumeinternshipm.html",{'resumeinternship':resumeinternship})
            data['count']=resumeinternship.count()
            data["message"]="Internship deleted successfully"
            return Response(data, status=status.HTTP_200_OK)
        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST) 

class UserResumeActivitiesAdd(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="All Fields are required"
        title = request.POST.get("activity")
        desc = request.POST.get("activity_description")
        issue_date = request.POST.get("particiopation_date")

        if title and desc and issue_date:
            resume,_=UserResume.objects.get_or_create(user=request.user)
            activity,_=UserResumeActivity.objects.get_or_create(resume=resume,title=title)
            activity.description=desc
            activity.issue_date=issue_date
            activity.save()
            resumeactivity=UserResumeActivity.objects.filter(resume=resume)
            data['htmld']=render_to_string("topteenfrontend/includes/resumeactivityd.html",{'resumeactivity':resumeactivity})
            data['htmlm']=render_to_string("topteenfrontend/includes/resumeactivitym.html",{'resumeactivity':resumeactivity})
            data['count']=resumeactivity.count()
            data["message"]="Activity Added successfully"
            return Response(data, status=status.HTTP_200_OK)
        id = request.data.get('id',None)
        if id:
            activity=get_object_or_404(UserResumeActivity,id=int(id))
            activity.delete()
            resume,_=UserResume.objects.get_or_create(user=request.user)
            resumeactivity=UserResumeActivity.objects.filter(resume=resume)
            data['htmld']=render_to_string("topteenfrontend/includes/resumeactivityd.html",{'resumeactivity':resumeactivity})
            data['htmlm']=render_to_string("topteenfrontend/includes/resumeactivitym.html",{'resumeactivity':resumeactivity})
            data['count']=resumeactivity.count()
            data["message"]="Activity Added successfully"
            return Response(data, status=status.HTTP_200_OK)
        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST)

class UserResumeVolunteering(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="All Fields are required"
        title = request.POST.get("volunteertitle")
        role = request.POST.get("volunteerrole")
        desc = request.POST.get("volunteerdescription")
        start_date = request.POST.get("volunteer_start_date")
        end_date = request.POST.get("volunteer_end_date")

        if title and desc and role and start_date and end_date:
            resume,_=UserResume.objects.get_or_create(user=request.user)
            volunteer,_=UserResumeVolunteerInvolvement.objects.get_or_create(resume=resume,title=title)
            volunteer.title=title
            volunteer.role=role
            volunteer.description=desc
            volunteer.start_date=start_date
            volunteer.end_date=end_date
            volunteer.save()
            resumevolunteer=UserResumeVolunteerInvolvement.objects.filter(resume=resume)
            data['htmld']=render_to_string("topteenfrontend/includes/resumevolunteerd.html",{'resumevolunteer':resumevolunteer})
            data['htmlm']=render_to_string("topteenfrontend/includes/resumevolunteerm.html",{'resumevolunteer':resumevolunteer})
            data['count']=resumevolunteer.count()
            data["message"]="Add Volunteer Certificate successfully"
            return Response(data, status=status.HTTP_200_OK)
        id = request.data.get('id',None)
        if id:
            volunteer=get_object_or_404(UserResumeVolunteerInvolvement,id=int(id))
            volunteer.delete()
            resume,_=UserResume.objects.get_or_create(user=request.user)
            resumevolunteer=UserResumeVolunteerInvolvement.objects.filter(resume=resume)
            data['htmld']=render_to_string("topteenfrontend/includes/resumevolunteerd.html",{'resumevolunteer':resumevolunteer})
            data['htmlm']=render_to_string("topteenfrontend/includes/resumevolunteerm.html",{'resumevolunteer':resumevolunteer})
            data['count']=resumevolunteer.count()
            data["message"]="Add Volunteer Certificate successfully"
            return Response(data, status=status.HTTP_200_OK)
        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST) 

class UserResumeMailSend(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="Resume mail send successfully"
        return Response(data, status=status.HTTP_200_OK)

class CreateUserFolder(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="All Fields are required"
        folder_name = request.POST.get("foldername")

        if folder_name:
            folder,_ = UserFolder.objects.get_or_create(user=request.user,title=folder_name)
            user_folders=UserFolder.objects.filter(user=request.user)
            data['html']=render_to_string("topteenfrontend/includes/foldername.html",{'folders':user_folders})
            data["message"]="Add folder successfully"
            return Response(data, status=status.HTTP_200_OK)
        
        id = request.data.get('id',None)
        if id:
            folder=get_object_or_404(UserFolder,id=int(id))
            folder.delete()
            user_folders=UserFolder.objects.filter(user=request.user)
            data["message"]="Delete folder successfully"
            return Response(data, status=status.HTTP_200_OK)
        
        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST) 
    
class CreateUserFolderFile(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="All Fields are required"
        folder_id=request.data.get("folderid")
        file_title = request.data.get("filename")
        file =request.data.get("file")

        if file_title and folder_id and file:
            folder = get_object_or_404(UserFolder,id=folder_id)
            file = FolderFile.objects.get_or_create(folder=folder,title=file_title,file=file)
            folder_files=folder.folder_files.all()
            data["message"]="Add file successfully"
            return Response(data, status=status.HTTP_200_OK)
        
        id = request.data.get('id',None)
        del_folder_id=request.data.get('delfolderid',None)
        if id and del_folder_id:
            folder = get_object_or_404(UserFolder,id=del_folder_id)
            file=get_object_or_404(FolderFile,id=int(id),folder=folder)
            file.delete()
            data["message"]="Delete file successfully"
            return Response(data, status=status.HTTP_200_OK)
        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST) 
    
class CreateSkillabCoursePayment(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request):
        user = request.user
        skillabcourse_slug = request.data.get('skilllabcourse',False)
        if skillabcourse_slug:
            skillab_course=get_object_or_404(SkillLabCourse,slug=skillabcourse_slug)
            gateway_receipt="Skilllab_course_receipt_{}".format(request.user.id)
            amount=Configuration.get('SKILLAB_COURSE_AMOUNT',1000,editable=True)
            sp,_=SkilllabCoursePayment.objects.get_or_create(user=user,skilllab_course=skillab_course,gateway_receipt=gateway_receipt,is_success=choices.YesNoChoices.NO,amount=amount,currency=choices.Currency.IND)
            payment,_=Payment.objects.get_or_create(user=user,gateway_receipt=sp.gateway_receipt,is_success=choices.YesNoChoices.NO,obj_id=sp.id,obj_type=choices.PaymentObjectType.SKILLLABCOURSE,amount=sp.amount,currency=sp.currency)
            url=sp.get_payment_success_fail_url()
            data={}
            data['sp_id'] = sp.id
            data['pay_id'] = payment.id
            data['payment_info'] = json.loads(payment.get_payment_info())
            data['success_url']=url.get("success_url")
            data['fail_url']=url.get("fail_url")
            return Response(data, status=status.HTTP_200_OK)   
        return Response("Something went very wrong. Try again", status=status.HTTP_400_BAD_REQUEST)  
    
class UpdateSkilllabCoursePayment(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request):
        try:
            sp_id = request.data.get('sp_id',False)
            payment_id=request.data.get('payment_id',False)
            gateway_order_id = request.data.get('gateway_order_id',False)
            gateway_payment_id = request.data.get('gateway_payment_id',False)
            gateway_signature = request.data.get('gateway_signature',False)
            gateway_receipt="Skilllab_course_receipt_{}".format(request.user.id)

            sp = SkilllabCoursePayment.objects.filter(id=sp_id,user=request.user,gateway_receipt=gateway_receipt,is_success=choices.YesNoChoices.NO,currency=choices.Currency.IND).last()

            if sp and gateway_payment_id and gateway_order_id and gateway_signature and payment_id:
                payment = Payment.objects.filter(id=payment_id,user=request.user,gateway_receipt=sp.gateway_receipt,is_success=choices.YesNoChoices.NO,obj_id=sp.id,obj_type=choices.PaymentObjectType.SKILLLABCOURSE,amount=sp.amount,currency=sp.currency).last()
                if payment:
                    payment_status=payment.update_payment(gateway_payment_id,gateway_order_id,gateway_signature)
                    if payment_status:
                        sp.is_success=choices.YesNoChoices.YES
                        sp.save()
                        send_skillabcourse_payment_success_mail.delay(sp.id)
                        return Response("Skilllabcourse payment successfull", status=status.HTTP_200_OK)
                    else:
                        return Response("Payment Failed.", status=status.HTTP_400_BAD_REQUEST) 
                else:
                    return Response("Payment Failed.", status=status.HTTP_400_BAD_REQUEST) 
            else:
                return Response("Payment Failed.", status=status.HTTP_400_BAD_REQUEST)      
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            print("aslkahsdf",e)

        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST)  