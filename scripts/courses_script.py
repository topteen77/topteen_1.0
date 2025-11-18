from math import degrees
from core.models import Country,City,State
from courses.models import Stream,Course,CourseFacts,CourseIntake,CourseMoneyValue,CourseText,Degree
from colleges.models import College
from core import choices
import requests
import json,os
import re
from django.template.defaultfilters import slugify
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
# Give the location of the file
path = 'college_data/college_imported_data/'
print(os.path.isdir(path))
counter =0
for file_name in [file for file in os.listdir(path)]:
		counter+=1
		with open(path+file_name, errors='ignore') as json_file:
				try:
					data = json.load(json_file)
					datalen=len(data)
					rows=[]
					for i in data:
						rows.append(i)  
					# for row in rows[:1]:
					collegename=rows[0]['college_name']
					for row in rows[2:]:
						tutionfee=0
						name=row['course_name']
						college_name=collegename
						coursemode=0
						if row['course_duration']=="2":
							courseduration=24
						if row['course_duration']=="3":
							courseduration=36
						if row['course_duration']=="4":
							courseduration=48
						if row['course_duration']=="5":
							courseduration=60
						if row['course_duration']=="6":
							courseduration=72
						course_level=row['course_level']
						if course_level=="UG":
							course_level=0
						else:
							course_level=1
						fee=row['total_fees']
						if fee!=None:
							fee=fee.split(" ")
							fees=fee[1]
							if "." in fees:
								fees=fees.replace(".","")
								if fees.isnumeric():
									fees=int(fees)
									fees=fees*1000
									tutionfee=fees
							elif ',' in fees:
								fees=fees.replace(",","")
								tutionfee=fees
						degree=row['course_name']
						print(degree)
						if 'in' in degree:
							degree=degree.split(" ")
							if "." in degree[0]:
								degree_couse=degree[0]
							else:
								degree_couse=row['course_name']
						print("degree_course",degree_couse)
						stream=row['stream']
							#fees=int(fees)
						#print(fees)
						#line = re.sub('[0-9]', '', fee)
						#print(fees)
						degre,_= Degree.objects.get_or_create(name=degree_couse)
						print('yes')
						clg,_=College.objects.get_or_create(name=college_name)  
						stream,_=Stream.objects.get_or_create(name=stream)
						slug=slugify(name+""+college_name)
						common_logo="https://i.pinimg.com/736x/0a/28/28/0a2828f9646ecedf432b8911e0c1ff29--building-structure-school-building.jpg"
						course,_=Course.objects.get_or_create(name=name,course_type=coursemode,duration_months=courseduration,program_level=course_level,slug=slug,stream=stream)
						print("It's")
						uition_fee_ug_from,_=CourseMoneyValue.objects.get_or_create(course=course,type=choices.CourseMoneyType.TUITION_FEE,amount=tutionfee)
						saveImages(course, common_logo,field_name='logo')
				except:  # includes simplejson.decoder.JSONDecodeError
						print('Decoding JSON has failed')
	 
				print(counter)

