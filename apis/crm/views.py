from core import choices
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions,authentication
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from crm.models import Lead

class LeadsAPI(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [authentication.SessionAuthentication, authentication.TokenAuthentication]

    def post(self, request):
        data = {}
        data["message"] = "All Fields Required"
        action = request.data.get("lead_action")
        user = request.user
        if action and user:
            lead,_=Lead.objects.get_or_create(user=user,action=action,status=choices.LeadStatus.FRESH)
            # data["message"]="lead submit successfully"
            data["message"]="Thank you, we will get back soon."
            return Response(data, status=status.HTTP_200_OK) 
        return Response(data, status=status.HTTP_400_BAD_REQUEST) 