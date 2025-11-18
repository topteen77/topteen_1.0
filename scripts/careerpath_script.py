import csv
cp=None
with open('scripts/draft_all_careers/careerpath.csv', newline='') as csvfile:
	reader = csv.reader(csvfile)
	for row in reader:
		if row[3]=="":
			continue
		career_name=row[1]
		path_name=row[3]
		if career_name!="":
			cp,cp_=CareerPath.objects.get_or_create(name=career_name,career_route_name=career_name+" route")
			career=Career.objects.get(name=career_name)
			career.career_paths.add(cp)
		cps=CareerPathStep.objects.create(name=path_name)
		cp.career_path_steps.add(cps)
		











import csv
cp=None
with open('scripts/draft_all_careers/careerpath.csv', newline='') as csvfile:
	reader = csv.reader(csvfile)
	for row in reader:
		if row[3]=="":
			continue
		career_name=row[1]
		path_name=row[3]
		if career_name!="":
			career=Career.objects.filter(name=career_name).first()
			if career:
				career.career_paths.clear()
				pass
			else:
				print(career_name)