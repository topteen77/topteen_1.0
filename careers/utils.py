def career_media_directory(instance, filename):
    return 'upload/career/media/{0}/{1}'.format(instance.id, filename)

def get_formated_currency(amount,country_code=91):
    return "{sal}LPA".format(sal=(round(int(amount)/100000,2)))

def career_cluster_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/career/careercluster/{0}'.format(filename)