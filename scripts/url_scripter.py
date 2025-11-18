import requests
import json
from colleges.models import College,CollegeImages,CollegeFlatText,CollegeFacts,CollegeText,CollegeMoneyValue,Stream,Facility,CollegeFacility    
from core.models import Country,BaseMoneyModel,State,City
from users.models import User
from core import choices
from django.utils.text import slugify
from courses.models import Stream,Course,CourseFacts,CourseIntake,CourseMoneyValue,CourseText,Degree
from django.db.models import Model
from typing import TYPE_CHECKING,Type,Union

def saveImages(your_model, url,field_name):
    from django.core import files
    from io import BytesIO
    resp = requests.get(url)
    print(url)
    if resp.status_code != requests.codes.ok:
        print('')
        #  Error handling here

    fp = BytesIO()
    fp.write(resp.content)
    file_name = url.split("/")[-1]  # There's probably a better way of doing this but this is just a quick example
    getattr(your_model,field_name).save(file_name, files.File(fp))


def generate_unique_slug(
    instance: Type[Model],
    slugable_value: str,
    slug_field_name: str = "slug",
) -> str:
    """Create unique slug for model instance.

    The function uses `django.utils.text.slugify` to generate a slug from
    the `slugable_value` of model field. If the slug already exists it adds
    a numeric suffix and increments it until a unique value is found.

    Args:
        instance: model instance for which slug is created
        slugable_value: value used to create slug
        slug_field_name: name of slug field in instance model

    """
    slug = slugify(slugable_value, allow_unicode=True)
    unique_slug: Union["SafeText", str] = slug

    ModelClass = instance.__class__
    extension = 1

    search_field = f"{slug_field_name}__iregex"
    pattern = rf"{slug}-\d+$|{slug}$"
    slug_values = (
        ModelClass._default_manager.filter(**{search_field: pattern})  # type: ignore
        .exclude(pk=instance.pk)
        .values_list(slug_field_name, flat=True)
    )

    while unique_slug in slug_values:
        extension += 1
        unique_slug = f"{slug}-{extension}"

    return unique_slug

class APIService1:
    def hit_api(self,url,payload={},method="POST"):
        data=json.dumps(payload)
        response=requests.request(method=method,url=url,data=data)
        return json.loads(response.text)

    def fetch_data(self,url):
        data=self.hit_api(url)
        self.insert_data(data=data.get("success").get("data"))
        if data.get("success").get("next_page_url"):
            self.fetch_data(data.get("success").get("next_page_url"))
    
    def insert_data(self,data):
        for  d in data:
            # self.create_college(d)
            try:
                self.create_college(d)
            except Exception as e:
                print("%"*30,e)

    
    def create_college(self,college):
        country=Country.objects.get(name="India")
        user = User.objects.filter(is_superuser=True).first()
        state=college.get("p_name")
        cstate,_=State.objects.get_or_create(name=state,country=country)
        city=college.get("u_city")
        ccity,_=City.objects.get_or_create(state=cstate,name=city)
        college_name = college.get('u_name')
        slug=slugify(college_name,allow_unicode=True)
        ccollege,_ = College.objects.get_or_create(name=college_name,created_by=user,country=country)
        ccollege.city=ccity
        ccollege.state=cstate
        ccollege.save()
        self.create_college_flat_text(ccollege,college)
        self.create_college_text(ccollege,college)
        self.create_college_fact_type(ccollege,college)
        self.get_program_data(data=college,college=ccollege)

    def create_college_flat_text(self,college,data):
        cflattext,_=CollegeFlatText.objects.get_or_create(college=college,type=choices.FlatTextType.WEBSITE,value=data.get("u_link"))

    def create_college_text(self,college,data):
        ctext,_=CollegeText.objects.get_or_create(college=college,type=choices.CollegeTextType.ABOUT,value=data.get("about"))
        ctext,_=CollegeText.objects.get_or_create(college=college,type=choices.CollegeTextType.ENTRY_REQUIREMENTS,value=data.get("uni_entry_requirements"))
        ctext,_=CollegeText.objects.get_or_create(college=college,type=choices.CollegeTextType.SCHOLARSHIPS,value=data.get("uni_scholarships"))

    def create_college_fact_type(self,college,data):
        cfacts,_=CollegeFacts.objects.get_or_create(college=college,type=choices.CollegeFactType.TOTAL_STUD,value=data.get("total_students"))
        cfacts,_=CollegeFacts.objects.get_or_create(college=college,type=choices.CollegeFactType.VIEWS,value=data.get("views"))

    def create_college_money_value(self,college,data):
        # cmoney,_=CollegeMoneyValue.objects.get_or_create(college,type=choices.CollegeMoneyType.AVG_COST_OF_LIVING,amount="")
        # cmoney,_=CollegeMoneyValue.objects.get_or_create(college,type=choices.CollegeMoneyType.AVG_TUITION_FEE_PA_MIN,amount=data.get("tuition_fee_ug_can"))
        # cmoney,_=CollegeMoneyValue.objects.get_or_create(college,type=choices.CollegeMoneyType.AVG_TUITION_FEE_PA_MAX,amount=data.get("tuition_fee_pg_can"))
        cmoney,_=CollegeMoneyValue.objects.get_or_create(college,type=choices.CollegeMoneyType.TUITION_FEE_UG_FROM,amount=data.get("tuition_fee_ug_int_from"))
        cmoney,_=CollegeMoneyValue.objects.get_or_create(college,type=choices.CollegeMoneyType.TUITION_FEE_UG_TO,amount="tuition_fee_ug_int_to")
        cmoney,_=CollegeMoneyValue.objects.get_or_create(college,type=choices.CollegeMoneyType.TUITION_FEE_PG_FROM,amount="tuition_fee_pg_int_from")
        cmoney,_=CollegeMoneyValue.objects.get_or_create(college,type=choices.CollegeMoneyType.TUITION_FEE_PG_TO,amount="tuition_fee_pg_int_to")
        

    def get_program_data(self,data,college):
        url="https://webapi.kaunsacollege.com/api/searchprograms?uni_id={}".format(data.get("u_id"))
        data=self.hit_api(url)
        if data.get("success"):
            self.insert_data_prgm(data.get("success"),college)

    def insert_data_prgm(self,data,college):
        for d in data[:1]:
            self.update_college(college=college,data=d)
            self.get_college_prgm(college=college,data=d)

    def update_college(self,college,data):
        if data.get("uni_img_path") and data.get("uni_img_path") != "":
            saveImages(college, data.get("uni_img_path"),field_name='logo')
        if data.get("uni_banner_path") and data.get("uni_banner_path") !="":
            saveImages(college,data.get("uni_banner_path"),field_name='banner')

    def get_college_prgm(self,college,data):
        for prgm in data.get("program_data"):
            self.create_course(college=college,data=prgm)

    def create_course(self,college,data):
        course_name=data.get("prgm_name")
        course_duration=data.get("prgm_duration")
        college_name=data.get("u_name")
        if course_duration == " ":
            course_duration=0
        # stream,_=Stream.objects.get_or_create(name=data.get("stream"))
        if data.get("level_heading_name") == "Postgraduate":
            course_level=choices.ProgramLevel.PG
        else:
            course_level=choices.ProgramLevel.UG
        slug=slugify(course_name,allow_unicode=True)
        if len(slug) > 140:
            slug=slug[:140]
            print("#"*30)
            print("Slug data so long Split slug")
            print(slug)
            print("#"*30)
        course,_=Course.objects.get_or_create(college=college,name=course_name,course_type=0,duration_months=course_duration,program_level=course_level,slug=slug)
        self.create_course_fact(course=course,data=data)
        self.create_course_text(course=course,data=data)
        self.create_course_money(course=course,data=data)

    def create_course_text(self,course,data):
        course_text,_=CourseText.objects.get_or_create(course=course,type=choices.CourseTextType.OVERVIEW,value=data.get("pg_desc"))

    def create_course_fact(self,course,data):
        coursefact,_=CourseFacts.objects.get_or_create(course=course,type=choices.CourseFactType.APPLICATION_PROCESSING_DAYS,value=data.get("process_time"))

    def create_course_money(self,course,data):
        amount=data.get("tuition_fee").replace(",","")
        cmoney,_=CourseMoneyValue.objects.get_or_create(course=course,type=choices.CourseMoneyType.TUITION_FEE,amount=amount)


        

a=APIService1()
a.fetch_data("https://webapi.kaunsacollege.com/api/universities")


# class APIService2:
#     def hit_api(self,url,payload={},method="POST"):
#         data=json.dumps(payload)
#         response=requests.request(method=method,url=url,data=data)
#         return json.loads(response.text)

#     def fetch_data(self,url,page_no=1):
#         data=self.hit_api(url)
#         if data.get("success"):
#             self.insert_data(data.get("success"))
#             url=url.split("?")[0]
#             url=url+"?page={}".format(page_no+1)
#             # self.fetch_data(url,page_no=page_no+1)

#     def insert_data(self,data):
#         for d in data[:1]:
#             print("#"*30)
#             print(d)
#             print("#"*30)

# a=APIService2()
# a.fetch_data("https://webapi.kaunsacollege.com/api/searchprograms")