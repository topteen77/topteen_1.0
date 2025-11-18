import re
import csv
from core.models import Country,City,State
from colleges.models import College, CollegeFacts,CollegeFlatText, CollegeText,CollegeMoneyValue, Stream,CollegeCategory
from core import choices
import requests
import codecs


def saveImages(your_model, url,field_name):
    from django.core import files
    from io import BytesIO
    resp = requests.get(url)
    print(url)
    if resp.status_code != requests.codes.ok:
        print('error')
        #  Error handling here

    fp = BytesIO()
    fp.write(resp.content)
    file_name = url.split("/")[-1]  # There's probably a better way of doing this but this is just a quick example
    getattr(your_model,field_name).save(file_name, files.File(fp))



file = codecs.open('scripts/colleges_data/sheet.csv', "r",encoding='utf-8', errors='ignore')
#file = open('college_data/courses/Engineering1.csv','rb')

csvreader=csv.reader(file)
header=[]
header = next(csvreader)

rows=[]
for row in csvreader:
    rows.append(row)
for row in rows:
    stream=row[1]
    cetegory=row[2]
    state=row[3]
    city=row[4]
    contact_num=row[12]
    
    college_name=row[9]
    mail=row[13]
    if row[5]=='university':
        college_type=2
    else:
        college_type=1
    location=row[11]
    if row[17] !='':
        year=row[17]
    else:
        year=1998
    u_link=row[20]
    
        
    if row[18] !='':
        total_students=int(row[18])
    else:
        total_students=0
    tuition_fee_ug_int_from=row[27]
    if tuition_fee_ug_int_from == '':
        tuition_fee_ug_int_from=0
    else:
        tuition_fee_ug_int_from=int(row[27])
    
    print(tuition_fee_ug_int_from)
    tuition_fee_ug_int_to=row[28]
    if tuition_fee_ug_int_to =='':
        tuition_fee_ug_int_to=0
    else:
        tuition_fee_ug_int_to=int(row[28])
    
    tuition_fee_pg_int_from=row[29]
    if tuition_fee_pg_int_from == '':
        tuition_fee_pg_int_from=0
    else:
        tuition_fee_pg_int_from=int(row[29])

    tuition_fee_pg_int_to=row[30]
    if tuition_fee_pg_int_to == '':
        tuition_fee_pg_int_to=0
        
    else:
        tuition_fee_pg_int_to=int(row[30])

    entry_req=row[35]
    
    common_logo="https://i.pinimg.com/736x/0a/28/28/0a2828f9646ecedf432b8911e0c1ff29--building-structure-school-building.jpg"

    print(entry_req)
    country=Country.objects.get(name="India")
    cstate,_=State.objects.get_or_create(name=state,country=country)
    ccity,_=City.objects.get_or_create(state=cstate,name=city)
    
    stream,_=Stream.objects.get_or_create(name=stream)
    category,_=CollegeCategory.objects.get_or_create(name=cetegory)

    college,_=College.objects.get_or_create(name=college_name,country=country,state=cstate,city=ccity,college_type=college_type,stream=stream,category=category)
    saveImages(college, common_logo,field_name='logo')


    email,_=CollegeFlatText.objects.get_or_create(college=college,type=choices.FlatTextType.EMAIL,value=mail)
    website,_=CollegeFlatText.objects.get_or_create(college=college,type=choices.FlatTextType.WEBSITE,value=u_link)
    loc,_=CollegeFlatText.objects.get_or_create(college=college,type=choices.FlatTextType.LOCATION,value=location)


    founded,_=CollegeFacts.objects.get_or_create(college=college,type=choices.CollegeFactType.YEAR_OF_EST,value=year)
    total_stud,_=CollegeFacts.objects.get_or_create(college=college,type=choices.CollegeFactType.TOTAL_STUD,value=total_students)

    entry_reqs,_=CollegeText.objects.get_or_create(college=college,type=choices.CollegeTextType.ENTRY_REQUIREMENTS,value=entry_req)
    print(tuition_fee_ug_int_from)
    print(tuition_fee_ug_int_to)
    print(tuition_fee_pg_int_from)
    print(tuition_fee_pg_int_to)
    

    tuition_fee_ug_from,_=CollegeMoneyValue.objects.get_or_create(college=college,type=choices.CollegeMoneyType.TUITION_FEE_PG_FROM,amount=tuition_fee_ug_int_from)
    tuition_fee_ug_to,_=CollegeMoneyValue.objects.get_or_create(college=college,type=choices.CollegeMoneyType.TUITION_FEE_UG_TO,amount=tuition_fee_ug_int_to)
    tuition_fee_pg_from,_=CollegeMoneyValue.objects.get_or_create(college=college,type=choices.CollegeMoneyType.TUITION_FEE_PG_FROM,amount=tuition_fee_pg_int_from)
    tuition_fee_pg_to,_=CollegeMoneyValue.objects.get_or_create(college=college,type=choices.CollegeMoneyType.TUITION_FEE_PG_TO,amount=tuition_fee_pg_int_to)

