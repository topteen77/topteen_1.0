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

def check_permissions(user, path):
    '''
    #0 is app, 1 is model, 2 is action, 3 is id
    #eg users/user/edit/4 or users/user/add
    '''
    paths = [p for p in path.split('/') if p]
    # Related careers admin lives under careers/related-careers/… but uses Career permissions
    if len(paths) >= 2 and paths[0] == 'careers' and paths[1] == 'related-careers':
        paths = ['careers', 'career'] + paths[2:]
        if len(paths) >= 3 and paths[2] == 'edit':
            paths[2] = 'change'

    obj = None
    if len(paths) == 4 and paths[2] not in ('list', 'add'):
        class_name = apps.get_model(paths[0], paths[1])
        obj = class_name.objects.get(pk=paths[3])
    perm = '{0}.{2}_{1}'.format(*paths[:3])
    return user.has_perm(perm, obj)