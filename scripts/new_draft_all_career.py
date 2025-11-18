import csv
from careers.models import Career,RIASECCareer
from django.template.defaultfilters import slugify
from core import choices
import pandas 

content = pandas.read_excel("scripts/draft_all_careers/draft_all_career (1).xlsx")


for i in range(len(content)):
    name=content.iloc[i]["Occupation"]
    code=content.iloc[i]["Interest Code"]
    slug=slugify(name)
    career,_=Career.objects.get_or_create(name=name,defaults={'slug':slug,'publish_status':choices.PublishStatus.DRAFT})

    print("Career create successfully",_)

    raisec_career,_=RIASECCareer.objects.get_or_create(key=code) 

    print("Riasec career create",_)

    if not raisec_career.careers.contains(career):
        raisec_career.careers.add(career)
        raisec_career.save()
        print("Riasec career inside career add")