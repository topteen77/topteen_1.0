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


def _user_resume_for_request(request):
    """
    Resolve the target UserResume from resume_id (JSON/form) or the user's most recently
    modified resume, creating a default row only when they have none yet.
    """
    user = request.user
    rid = None
    if getattr(request, "data", None) is not None:
        rid = request.data.get("resume_id")
    if rid in (None, "", b"") and request.POST:
        rid = request.POST.get("resume_id")
    if rid not in (None, "", b""):
        try:
            pk = int(rid)
        except (TypeError, ValueError):
            pk = None
        if pk:
            return get_object_or_404(UserResume, pk=pk, user=user)

    existing = UserResume.objects.filter(user=user).order_by("-modified").first()
    if existing:
        return existing
    return UserResume.objects.create(user=user, title="My resume")


def _resume_ui_template20(request):
    v = (request.POST.get("resume_ui") or "").strip().lower()
    if not v and getattr(request, "data", None) is not None:
        try:
            v = (request.data.get("resume_ui") or "").strip().lower()
        except Exception:
            v = ""
    return v in ("template20", "t20", "1")


def _attach_resume_editor_payload(request, resume, data):
    if _resume_ui_template20(request):
        try:
            from users.resume_payload import resume_editor_payload

            data["resume_editor_payload"] = resume_editor_payload(resume)
        except Exception:
            pass


class ShortlistCourseAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request):
        career_slug = request.POST.get('careerslug', False)
        career = get_object_or_404(Career, slug=career_slug)
        user = request.user

        if getattr(user, "user_type", None) == choices.UserType.PARENT:
            from users.career_interests import toggle_parent_career_bookmark

            student_id = request.POST.get("student_id")
            try:
                sid = int(student_id) if student_id not in (None, "", b"") else None
            except (TypeError, ValueError):
                sid = None
            data = toggle_parent_career_bookmark(user, career, student_id=sid)
            return Response(data, status=status.HTTP_200_OK)

        career_shortlisted, created = CareerShortlist.objects.get_or_create(user=user, career=career)
        if created:
            data = {"message": "Career Shortlisted", "value": "Remove Shortlisted"}
            return Response(data, status=status.HTTP_200_OK)
        career_shortlisted.delete()
        data = {"message": "Removed Shortlisted", "value": "Shortlist Career"}
        return Response(data, status=status.HTTP_200_OK)


class ParentCareerReactionAPI(APIView):
    """Student likes or dislikes a parent-recommended career."""
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request):
        from core import choices
        from users.career_interests import set_parent_career_reaction

        if getattr(request.user, "user_type", None) != choices.UserType.STUDENT:
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        bookmark_id = request.POST.get("bookmark_id") or request.data.get("bookmark_id")
        reaction = request.POST.get("reaction") or request.data.get("reaction") or ""
        try:
            bookmark_id = int(bookmark_id)
        except (TypeError, ValueError):
            return Response({"message": "bookmark_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        result = set_parent_career_reaction(
            student=request.user,
            bookmark_id=bookmark_id,
            reaction=reaction,
        )
        status_code = status.HTTP_200_OK if result.get("success") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=status_code)


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
                note.title = (title or "").strip() or None
                note.content = content
                from django.utils.html import strip_tags
                body = strip_tags(content or "").replace("\xa0", " ").strip()
                if not (note.title or body):
                    note.delete()
                else:
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
            resume = _user_resume_for_request(request)
            resume.about = about
            resume.save()
            if _resume_ui_template20(request):
                td = "template20/user/includes/resume_builder_about_d.html"
                tm = "template20/user/includes/resume_builder_about_m.html"
            else:
                td = "topteenfrontend/includes/resumeaboutd.html"
                tm = "topteenfrontend/includes/resumeaboutm.html"
            data["htmld"] = render_to_string(td, {"resume": resume})
            data["htmlm"] = render_to_string(tm, {"resume": resume})
            data['message']="About added successfully"
            return Response(data, status=status.HTTP_200_OK)
        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST)  

class UserResumeSkillAdd(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="All Fields are required"
        resume = _user_resume_for_request(request)
        title = request.data.get("skilltitle")
        desc = request.data.get("skilldesc") or ""
        profficiency = request.data.get("skillprofficiency")
        skill_id = request.data.get("skill_id") or request.data.get("skillid")

        if skill_id and title and profficiency:
            skiill = get_object_or_404(UserResumeSkill, id=int(skill_id), resume=resume)
            skiill.title = title
            skiill.description = desc
            skiill.profficiency = int(profficiency)
            skiill.save()
            resumeskill = UserResumeSkill.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_skill_d.html",
                    "template20/user/includes/resume_builder_skill_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumeskilld.html", "topteenfrontend/includes/resumeskillm.html"
            data["htmld"] = render_to_string(td, {"resumeskill": resumeskill})
            data["htmlm"] = render_to_string(tm, {"resumeskill": resumeskill})
            data["count"] = resumeskill.count()
            data["message"] = "Skill updated successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)

        if title and profficiency:
            skiill, _ = UserResumeSkill.objects.get_or_create(resume=resume, title=title)
            skiill.description = desc
            skiill.profficiency = profficiency
            skiill.save()

            resumeskill=UserResumeSkill.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_skill_d.html",
                    "template20/user/includes/resume_builder_skill_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumeskilld.html", "topteenfrontend/includes/resumeskillm.html"
            data['htmld']=render_to_string(td,{'resumeskill':resumeskill})
            data['htmlm']=render_to_string(tm,{'resumeskill':resumeskill})
            data["count"]=resumeskill.count()
            data["message"]="Skill Added successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)
        id = request.data.get('id',None)
        if id:
            skiill=get_object_or_404(UserResumeSkill,id=int(id))
            skiill.delete()
            resume=_user_resume_for_request(request)
            resumeskill=UserResumeSkill.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_skill_d.html",
                    "template20/user/includes/resume_builder_skill_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumeskilld.html", "topteenfrontend/includes/resumeskillm.html"
            data['htmld']=render_to_string(td,{'resumeskill':resumeskill})
            data['htmlm']=render_to_string(tm,{'resumeskill':resumeskill})
            data["count"]=resumeskill.count()
            data["message"]="Skill delete successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)
        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST)  

class UserResumeCertificationAdd(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="All Fields are required"
        resume = _user_resume_for_request(request)
        title = request.POST.get("certificatetitle")
        desc = request.POST.get("certificatedescription")
        date = request.POST.get("issuedate")
        cert_id = request.POST.get("certificate_id") or request.data.get("certificate_id")

        if cert_id and title and desc and date:
            certificate = get_object_or_404(UserResumeCertificate, id=int(cert_id), resume=resume)
            certificate.title = title
            certificate.description = desc
            certificate.issue_date = date
            certificate.save()
            resumecertificate = UserResumeCertificate.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_certificate_d.html",
                    "template20/user/includes/resume_builder_certificate_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumecertificated.html", "topteenfrontend/includes/resumecertificatem.html"
            data['htmld'] = render_to_string(td, {'resumecertificate': resumecertificate})
            data['htmlm'] = render_to_string(tm, {'resumecertificate': resumecertificate})
            data['count'] = resumecertificate.count()
            data["message"] = "Certificate updated successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)

        if title and desc and date:
            certificate,_=UserResumeCertificate.objects.get_or_create(resume=resume,title=title)
            certificate.description=desc
            certificate.issue_date=date
            certificate.save()
            resumecertificate=UserResumeCertificate.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_certificate_d.html",
                    "template20/user/includes/resume_builder_certificate_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumecertificated.html", "topteenfrontend/includes/resumecertificatem.html"
            data['htmld']=render_to_string(td,{'resumecertificate':resumecertificate})
            data['htmlm']=render_to_string(tm,{'resumecertificate':resumecertificate})
            data['count']=resumecertificate.count()
            data["message"]="Certificate Added successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)
        id = request.data.get('id',None)
        if id:
            certificate=get_object_or_404(UserResumeCertificate,id=int(id))
            certificate.delete()
            resume=_user_resume_for_request(request)
            resumecertificate=UserResumeCertificate.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_certificate_d.html",
                    "template20/user/includes/resume_builder_certificate_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumecertificated.html", "topteenfrontend/includes/resumecertificatem.html"
            data['htmld']=render_to_string(td,{'resumecertificate':resumecertificate})
            data['htmlm']=render_to_string(tm,{'resumecertificate':resumecertificate})
            data['count']=resumecertificate.count()
            data["message"]="Certificate Deleted successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)
        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST) 

class UserResumeInternshipAdd(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="All Fields are required"
        resume = _user_resume_for_request(request)
        provider = request.POST.get("provider")
        role = request.POST.get("role")
        desc = request.POST.get("internshipdescription")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        iid = request.POST.get("internship_id") or request.data.get("internship_id")

        if iid and provider and desc and role and start_date and end_date:
            internship = get_object_or_404(UserResumeInternship, id=int(iid), resume=resume)
            internship.provider = provider
            internship.role = role
            internship.description = desc
            internship.start_date = start_date
            internship.end_date = end_date
            internship.save()
            resumeinternship = UserResumeInternship.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_internship_d.html",
                    "template20/user/includes/resume_builder_internship_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumeinternshipd.html", "topteenfrontend/includes/resumeinternshipm.html"
            data['htmld'] = render_to_string(td, {'resumeinternship': resumeinternship})
            data['htmlm'] = render_to_string(tm, {'resumeinternship': resumeinternship})
            data['count'] = resumeinternship.count()
            data["message"] = "Internship updated successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)

        if provider and desc and role and start_date and end_date:
            internship=UserResumeInternship.objects.create(resume=resume)
            internship.provider=provider
            internship.role=role
            internship.description=desc
            internship.start_date=start_date
            internship.end_date=end_date
            internship.save()
            resumeinternship=UserResumeInternship.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_internship_d.html",
                    "template20/user/includes/resume_builder_internship_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumeinternshipd.html", "topteenfrontend/includes/resumeinternshipm.html"
            data['htmld']=render_to_string(td,{'resumeinternship':resumeinternship})
            data['htmlm']=render_to_string(tm,{'resumeinternship':resumeinternship})
            data['count']=resumeinternship.count()
            data["message"]="Internship Added successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)
        id = request.data.get('id',None)
        if id:
            internship=get_object_or_404(UserResumeInternship,id=int(id))
            internship.delete()
            resume=_user_resume_for_request(request)
            resumeinternship=UserResumeInternship.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_internship_d.html",
                    "template20/user/includes/resume_builder_internship_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumeinternshipd.html", "topteenfrontend/includes/resumeinternshipm.html"
            data['htmld']=render_to_string(td,{'resumeinternship':resumeinternship})
            data['htmlm']=render_to_string(tm,{'resumeinternship':resumeinternship})
            data['count']=resumeinternship.count()
            data["message"]="Internship deleted successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)
        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST) 

class UserResumeActivitiesAdd(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="All Fields are required"
        resume = _user_resume_for_request(request)
        title = request.POST.get("activity")
        desc = request.POST.get("activity_description")
        issue_date = request.POST.get("particiopation_date")
        aid = request.POST.get("activity_id") or request.data.get("activity_id")

        if aid and title and desc and issue_date:
            activity = get_object_or_404(UserResumeActivity, id=int(aid), resume=resume)
            activity.title = title
            activity.description = desc
            activity.issue_date = issue_date
            activity.save()
            resumeactivity = UserResumeActivity.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_activity_d.html",
                    "template20/user/includes/resume_builder_activity_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumeactivityd.html", "topteenfrontend/includes/resumeactivitym.html"
            data['htmld'] = render_to_string(td, {'resumeactivity': resumeactivity})
            data['htmlm'] = render_to_string(tm, {'resumeactivity': resumeactivity})
            data['count'] = resumeactivity.count()
            data["message"] = "Activity updated successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)

        if title and desc and issue_date:
            activity,_=UserResumeActivity.objects.get_or_create(resume=resume,title=title)
            activity.description=desc
            activity.issue_date=issue_date
            activity.save()
            resumeactivity=UserResumeActivity.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_activity_d.html",
                    "template20/user/includes/resume_builder_activity_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumeactivityd.html", "topteenfrontend/includes/resumeactivitym.html"
            data['htmld']=render_to_string(td,{'resumeactivity':resumeactivity})
            data['htmlm']=render_to_string(tm,{'resumeactivity':resumeactivity})
            data['count']=resumeactivity.count()
            data["message"]="Activity Added successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)
        id = request.data.get('id',None)
        if id:
            activity=get_object_or_404(UserResumeActivity,id=int(id))
            activity.delete()
            resume=_user_resume_for_request(request)
            resumeactivity=UserResumeActivity.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_activity_d.html",
                    "template20/user/includes/resume_builder_activity_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumeactivityd.html", "topteenfrontend/includes/resumeactivitym.html"
            data['htmld']=render_to_string(td,{'resumeactivity':resumeactivity})
            data['htmlm']=render_to_string(tm,{'resumeactivity':resumeactivity})
            data['count']=resumeactivity.count()
            data["message"]="Activity Added successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)
        return Response("Request rejected.", status=status.HTTP_400_BAD_REQUEST)

class UserResumeVolunteering(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request): 
        data={}
        data["message"]="All Fields are required"
        resume = _user_resume_for_request(request)
        title = request.POST.get("volunteertitle")
        role = request.POST.get("volunteerrole")
        desc = request.POST.get("volunteerdescription")
        start_date = request.POST.get("volunteer_start_date")
        end_date = request.POST.get("volunteer_end_date")
        vid = request.POST.get("volunteer_id") or request.data.get("volunteer_id")

        if vid and title and desc and role and start_date and end_date:
            volunteer = get_object_or_404(UserResumeVolunteerInvolvement, id=int(vid), resume=resume)
            volunteer.title = title
            volunteer.role = role
            volunteer.description = desc
            volunteer.start_date = start_date
            volunteer.end_date = end_date
            volunteer.save()
            resumevolunteer = UserResumeVolunteerInvolvement.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_volunteer_d.html",
                    "template20/user/includes/resume_builder_volunteer_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumevolunteerd.html", "topteenfrontend/includes/resumevolunteerm.html"
            data['htmld'] = render_to_string(td, {'resumevolunteer': resumevolunteer})
            data['htmlm'] = render_to_string(tm, {'resumevolunteer': resumevolunteer})
            data['count'] = resumevolunteer.count()
            data["message"] = "Volunteering updated successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)

        if title and desc and role and start_date and end_date:
            volunteer,_=UserResumeVolunteerInvolvement.objects.get_or_create(resume=resume,title=title)
            volunteer.title=title
            volunteer.role=role
            volunteer.description=desc
            volunteer.start_date=start_date
            volunteer.end_date=end_date
            volunteer.save()
            resumevolunteer=UserResumeVolunteerInvolvement.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_volunteer_d.html",
                    "template20/user/includes/resume_builder_volunteer_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumevolunteerd.html", "topteenfrontend/includes/resumevolunteerm.html"
            data['htmld']=render_to_string(td,{'resumevolunteer':resumevolunteer})
            data['htmlm']=render_to_string(tm,{'resumevolunteer':resumevolunteer})
            data['count']=resumevolunteer.count()
            data["message"]="Add Volunteer Certificate successfully"
            _attach_resume_editor_payload(request, resume, data)
            return Response(data, status=status.HTTP_200_OK)
        id = request.data.get('id',None)
        if id:
            volunteer=get_object_or_404(UserResumeVolunteerInvolvement,id=int(id))
            volunteer.delete()
            resume=_user_resume_for_request(request)
            resumevolunteer=UserResumeVolunteerInvolvement.objects.filter(resume=resume)
            if _resume_ui_template20(request):
                td, tm = (
                    "template20/user/includes/resume_builder_volunteer_d.html",
                    "template20/user/includes/resume_builder_volunteer_m.html",
                )
            else:
                td, tm = "topteenfrontend/includes/resumevolunteerd.html", "topteenfrontend/includes/resumevolunteerm.html"
            data['htmld']=render_to_string(td,{'resumevolunteer':resumevolunteer})
            data['htmlm']=render_to_string(tm,{'resumevolunteer':resumevolunteer})
            data['count']=resumevolunteer.count()
            data["message"]="Add Volunteer Certificate successfully"
            _attach_resume_editor_payload(request, resume, data)
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