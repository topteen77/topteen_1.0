from django.conf import settings 
from datetime import datetime,timedelta
import requests
import json
from core.models import APILog

class CentralTestService:
    def __init__(self):
        self.__TOKEN = ""

    def _hit_api(self,url,params={},method="POST"):
        headers = {
            "Content-Type":"application/json",
            "WWW-Authenticate": self.__TOKEN
        }
        response = requests.request(method,url,headers=headers,params=params)

        if response.status_code == 200:
            return json.loads(response.text),False
        else:
            self.create_api_error_log(url,params,response)
            return json.loads(response.text),True

    def _hit_api_xml(self,url,params={},method="POST"):
        headers = {
            "Content-Type":"application/xml",
            "WWW-Authenticate": self.__TOKEN
        }
        response = requests.request(method,url,headers=headers,params=params)
        if response.status_code == 200:
            return response.text,False
        else:
            self.create_api_error_log(url,params,response)
            return response.text,True

    def create_api_error_log(self,url,params,response):
        APILog.objects.create(api_name=self.__class__.__name__,url=url,
            request=params,
            response=response.text,
            status_code=response.status_code)
        
    def _get_token(self):
        url="https://app.centraltest.com/customer/REST/connect/JSON"
        params={}
        params['login'] = settings.CENTRAL_TEST_API_USERNAME
        params['password']=settings.CENTRAL_TEST_API_PASSWORD
        response,error = self._hit_api(url,params=params)
        self.__TOKEN = response.get('token')

    def get_titles_list(self,user):
        if not self.__TOKEN:
            self._get_token()
        url = "https://app.centraltest.com/customer/REST/list/title/JSON"
        params={}
        response,error = self._hit_api(url=url,params=params)
        # response data = [{'id': '1', 'label': 'Mr'}, {'id': '2', 'label': 'Ms'}]
        return response[0].get("id")

    def get_test(self,candidate):
        if not self.__TOKEN:
            self._get_token()
        url = "https://app.centraltest.com/customer/REST/list/test/JSON"
        params={}
        response,error = self._hit_api(url=url,params=params)
        for d in response:
            if d.get("label")=="Career Interest Assessment":
                return d.get("id")

    def get_tests_language(self,candidate):
        if not self.__TOKEN:
            self._get_token()
        url = "https://app.centraltest.com/customer/REST/list/testLanguage/JSON"
        params={}
        response,error = self._hit_api(url=url,params=params)
        # response data [{'id': '1', 'code': 'en_US', 'label': 'English (US)', 'default': 1}, {'id': '2', 'code': 'fr_FR', 'label': 'Français (FR)', 'default': 0}, {'id': '3', 'code': 'es_ES', 'label': 'Español (ES)', 'default': 0}, {'id': '7', 'code': 'ru_RU', 'label': 'Русский (RU)', 'default': 0}, {'id': '9', 'code': 'ar_MA', 'label': 'العربية (MA)', 'default': 0}]
        for d in response:
            if d.get("code")=="en_US":
                return d.get("id")

    def get_user_name(self,user):
        d={}
        try:
            if user.name:
                lst=user.name.split()
                d['first_name']=lst[0]
                d['last_name']=lst[len(lst)-1]
            else:
                d['first_name']=user.email.split("@")[0]
                d['last_name']=user.email.split("@")[0]
        except Exception as e:
            d['first_name']=user.name
            d['last_name']=user.name
        return d

    def create_candidate(self,user):
        username=self.get_user_name(user)
        if not self.__TOKEN:
            self._get_token()
        url = "https://app.centraltest.com/customer/REST/create/candidate/JSON"
        params={}
        params["password"]="12345678"
        params["firstname"]=username["first_name"]
        params["lastname"]=username["last_name"]
        params["title_id"]=self.get_titles_list(user)
        params["country_code"]="IND"
        params["email"]=user.email
        response,error = self._hit_api(url=url,params=params)
        return response,error

    def invite_candidate_take_test(self,candidate):
        if not self.__TOKEN:
            self._get_token()
        # url="https://app.centraltest.com/customer/REST/candidate/invite/JSON"
        url="https://app.centraltest.com/customer/REST/candidate/invite/JSON"
        params={}
        if candidate.candidate_id:
            params["id"]=candidate.candidate_id 
        else:
            params["email"]=candidate.email
        params["test_id"]=settings.CAREER_INTEREST_ASSESSMENTT_TEST_ID
        params["test_language_id"]=settings.CAREER_INTEREST_ASSESSMENTT_TEST_LANGUAGE_ID
        
        response,error = self._hit_api(url=url,params=params)
        # response data={'error': {'code': 403, 'messages': ["you don't have enough credits"]}}
        # {"error":{"code":406,"messages":["such invitation already exists"]}}
        if error and response.get("error").get("code") == 406 and response.get("error").get("messages")[0] == "such invitation already exists":
            response,error = self.get_candidate_pending_assessments(candidate)
            response=response[0]
        return response,error

    def get_candidate_pending_assessments(self,candidate):
        if not self.__TOKEN:
            self._get_token()
        url="https://app.centraltest.com/customer/REST/assessment/pending/JSON"
        params={}
        params["candidate_id"]=candidate.candidate_id 
        response,error = self._hit_api(url=url,params=params)
        return response,error


    def check_test_pending_or_complete(self,candidate_id):
        if not self.__TOKEN:
            self._get_token()
        url="https://app.centraltest.com/customer/REST/assessment/pending/JSON"
        params={}
        params["candidate_id"]=candidate_id
        response,error = self._hit_api(url=url,params=params)
        
        return response,error

    def get_complete_test(self,assessment_id,candidate_id):
        if not self.__TOKEN:
            self._get_token()
        url="https://app.centraltest.com/customer/REST/assessment/completed/JSON"
        params={}
        params["assessment_id"]=assessment_id
        params["candidate_id"]=candidate_id
        response,error = self._hit_api(url=url,params=params)
        
        return response,error

    def get_assessment_results(self,assessment_id):
        if not self.__TOKEN:
            self._get_token()
        url="https://app.centraltest.com/customer/REST/assessment/result/XML"
        params={}
        params["id"]=assessment_id
        response,error = self._hit_api_xml(url=url,params=params)
        return response,error

    def get_assessment_factors_score(self,assessment_id):
        if not self.__TOKEN:
            self._get_token()
        url="https://app.centraltest.com/customer/REST/report/factors_scores/JSON"
        params={}
        params["assessment_id"]=assessment_id
        response,error = self._hit_api(url=url,params=params)
        return response,error