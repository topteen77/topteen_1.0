import csv
from careers.models import Career,RIASECCareer
from django.template.defaultfilters import slugify
from core import choices

file = open('scripts/draft_all_careers/draft_all_career.csv')

csvreader= csv.reader(file)

next(csvreader)

for row in csvreader:
    slug=slugify(row[3])
    career,_=Career.objects.get_or_create(name=row[3],defaults={'slug':slug,'publish_status':choices.PublishStatus.DRAFT})

    print("Career create successfully")

    raisec_career,_=RIASECCareer.objects.get_or_create(key=row[0]) 

    print("Riasec career create ")

    if not raisec_career.careers.contains(career):
        raisec_career.careers.add(career)
        raisec_career.save()
        print("Riasec career inside career add")





