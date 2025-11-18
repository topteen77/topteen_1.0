from django.urls.base import reverse, reverse_lazy
from django.apps import apps

def build_admin_breadcrumb(list_of_dict):
    lst = []
    home={}
    home['title']="Home"
    try:
        home['url'] = reverse('topteenadmin:topteendashboard')
    except Exception:
        home['url'] = '/topteenadmin/'
    home['text'] = "Home"
    lst.append(home)
    lst.extend(list_of_dict)
    return lst

def check_permissions(user,path):
    '''
    #0 is app, 1 is model, 2 is action, 3 is id 
    #eg users/user/edit/4 or users/user/add
    '''
    paths = path.split('/')
    obj=None
    if len(paths)==4 and paths[2] != 'list' and paths[2] != 'add' :
        class_name=apps.get_model(paths[0], paths[1])
        obj=class_name.objects.get(pk=paths[3])
    perm='{0}.{2}_{1}'.format(*paths)
    obj=None
    return user.has_perm(perm,obj)