import json,os
from re import search
import re
from core import choices
from unicodedata import name
from colleges.models import College,CollegeImages,CollegeFlatText,CollegeFacts,CollegeText,CollegeMoneyValue,Stream,Facility,CollegeFacility    
from core.models import Country,BaseMoneyModel,State,City
#from courses.models import Stream,Course,CourseMoneyValue,CourseText,CourseFacts,CourseIntake,CourseEnglighRequirements
import requests
from users.models import User
from django.template.defaultfilters import slugify


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

path = 'college_data/college_imported_data/'
print(os.path.isdir(path))

for file_name in [file for file in os.listdir(path)]:
    with open(path+file_name, 'r',errors='ignore',encoding='utf-8') as json_file:
        try:
            data = json.load(json_file)
            college_detail=data[0]
            if college_detail !="" or college_detail != None:
                college_name = college_detail['college_name']
                total_students=college_detail['total_students']
                pattern = r'[^\.a-z0-9]'
                if total_students != None:
                    if total_students.startswith('UG'):
                        total_students=0
                    elif re.search(r'[a-z\.]',total_students):
                        total_students=0
                    else:
                        total_students=total_students.replace(",","")
                else:
                    total_students=0

                logo = college_detail['college_logo']
                website = college_detail['website']
                location=college_detail['location']
                country=Country.objects.get(name="India")
                cstate=None
                if location != None:
                    if "," not in location:
                        pass
                    else:
                        loc=location.split(",")
                        city=loc[0]
                        state=loc[1]
                        cstate,_=State.objects.get_or_create(name=state,country=country)
                        ccity,_=City.objects.get_or_create(state=cstate,name=city)
                
                
                yeartype=college_detail['year']
                if yeartype !=None:
                    yeartype=yeartype.split(" ")
                    year = yeartype[0]
                    if year.isnumeric():
                        year=year
                    else:
                        year=0
                else:
                    year=0
                
                banner=college_detail['banner']
                facilities=college_detail['facility']
                new_logo = logo
                new_banner=banner
                user = User.objects.filter(is_superuser=True).first()
                college,_ = College.objects.get_or_create(name=college_name,created_by=user,country=country)
                if cstate:
                    college.city=ccity
                    college.state=cstate
                    college.save()
                
                for facility in facilities:
                    fac,_=Facility.objects.get_or_create(name=facility)
                    colllegefacility,_=CollegeFacility.objects.get_or_create(college=college,facility=fac)


                if new_logo !=None:
                    saveImages(college, new_logo,field_name='logo')
                if new_banner !=None:
                    saveImages(college, new_banner,field_name='banner')
                print("THis is the college name",college)
                year_of_est,_ = CollegeFacts.objects.get_or_create(college=college,type=choices.CollegeFactType.YEAR_OF_EST,value=year)
                total_students,_ = CollegeFacts.objects.get_or_create(college=college,type=choices.CollegeFactType.TOTAL_STUD,value=total_students)
                    
                        
                        #add,_ = CollegeFlatText.objects.get_or_create(college=college,type=choices.FlatTextType.LOCATION,value=address)
        except ValueError:  # includes simplejson.decoder.JSONDecodeError
            print('Decoding JSON has failed')