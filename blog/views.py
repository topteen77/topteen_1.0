from cgitb import text
from venv import create
from django.shortcuts import render
from django.urls import reverse
from core.breadcrumbs import get_breadcrumb
from django.shortcuts import get_object_or_404
from core.utils import build_html_head, get_page_seo_html_head
from .models import BlogCategory,Blog,BlogTag,SubscriptionEmail
from django.views.generic import TemplateView
from django.core.paginator import Paginator,EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods
from rest_framework.views import APIView
from core import choices


@require_http_methods(["GET"])
def autocomplete_blogs(request):
    """API for blog search suggest dropdown - returns matching blog titles and URLs."""
    query = request.GET.get("q", "").strip()
    limit = min(int(request.GET.get("limit", 15)), 30)
    blogs = Blog.get_published_objects().only("title", "slug").exclude(title__isnull=True).exclude(title="")
    if query:
        blogs = blogs.filter(Q(title__icontains=query) | Q(summary__icontains=query))
    blogs = blogs.order_by("title")[:limit]
    results = []
    seen = set()
    for b in blogs:
        title = (b.title or "").strip()
        if not title:
            continue
        key = title.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "id": b.id,
            "text": title,
            "value": title,
            "slug": b.slug or "",
            "url": reverse("blog:blogdetail", args=[b.slug]),
        })
    return JsonResponse({"results": results})


def _blog_category_display(name):
    """Display label for blog category: 'Blogs for Parents' / 'Blogs for Students'."""
    if not name:
        return name
    s = (name or '').strip()
    if s in ('Blogs in For Parents', 'For Parents'):
        return 'Blogs for Parents'
    if s in ('Blogs in For Students', 'For Students'):
        return 'Blogs for Students'
    return name


def _blog_category_short(name):
    """Short form for 'Explore blogs X category': 'For Parents' / 'For Students'."""
    if not name:
        return name
    s = (name or '').strip()
    if s in ('Blogs in For Parents', 'For Parents'):
        return 'For Parents'
    if s in ('Blogs in For Students', 'For Students'):
        return 'For Students'
    return name


def _bookmarked_blog_ids_for_request(request, student_id=None):
    """Resolve shortlisted blog ids for list/detail bookmark buttons."""
    if not request.user.is_authenticated:
        return []
    try:
        from .models import BlogShortlist
        from django.contrib.contenttypes.models import ContentType

        if getattr(request.user, "user_type", None) == choices.UserType.PARENT:
            if student_id:
                from users.models import ParentStudentLink, ParentStudentBookmark
                if ParentStudentLink.objects.filter(parent=request.user, student_id=int(student_id)).exists():
                    ct = ContentType.objects.get_for_model(Blog)
                    return list(
                        ParentStudentBookmark.objects.filter(
                            parent=request.user,
                            student_id=int(student_id),
                            content_type=ct,
                        ).values_list("object_id", flat=True)
                    )
                return []
            ids = set(
                BlogShortlist.objects.filter(user=request.user, blog__isnull=False).values_list("blog_id", flat=True)
            )
            ct = ContentType.objects.get_for_model(Blog)
            ids.update(
                ParentStudentBookmark.objects.filter(
                    parent=request.user, content_type=ct
                ).values_list("object_id", flat=True)
            )
            return list(ids)
        return list(
            BlogShortlist.objects.filter(user=request.user, blog__isnull=False).values_list("blog_id", flat=True)
        )
    except Exception:
        try:
            from .models import BlogShortlist
            return list(
                BlogShortlist.objects.filter(user=request.user, blog__isnull=False).values_list("blog_id", flat=True)
            )
        except Exception:
            return []


def _is_blog_bookmarked_for_request(request, blog, student_id=None):
    if not request.user.is_authenticated:
        return False
    return blog.id in _bookmarked_blog_ids_for_request(request, student_id=student_id)


# Create your views here.
class Blogs(TemplateView):
    template_name = "template20/blogs.html"
    PAGE_SIZE = 6
    def html_head(self):
        name='Blog List'
        return build_html_head(title=name, description=name)

    def get_context(self,request, *args, **kwargs):
        ctx={}
        search_blogs=request.GET.get('search')
        if  search_blogs :
            ctx["search_blogs"] = search_blogs
            ctx["heading"] = "Searched Articles"
        else:
            ctx['search_blogs']=""
            ctx["heading"] ="All Articles"
            
        if search_blogs:
            blogs=Blog.get_published_objects().select_related('author', 'category').filter( Q(title__icontains=search_blogs) | Q(content__icontains=search_blogs)).order_by('-modified') 
        else:
            blogs=Blog.get_published_objects().select_related('author', 'category').order_by('-modified') 

        popular_blogs=Blog.get_published_objects().select_related('author', 'category').order_by('-views_count')[:6]
        ctx['latest_blogs']=Blog.get_published_objects().select_related('author', 'category').order_by('-created')[:3]
        ctx['categories']=BlogCategory.objects.all()
        ctx['breadcrumb'] = get_breadcrumb([{'text': 'Blog', 'url': ''}])
        # For search dropdown: title, slug, url for all published blogs
        ctx['blog_search_list'] = [
            {'title': b.title, 'slug': b.slug, 'url': reverse('blog:blogdetail', args=[b.slug])}
            for b in Blog.get_published_objects().only('title', 'slug')
        ]
        ctx['html_head'] = self.html_head()
        ctx["popular_blogs"] = popular_blogs
        ctx['site_url']= "https://topteen.in"
        ctx['blogs']=blogs
        paginated_blogs =Paginator(blogs,self.PAGE_SIZE)
        # Reuse the paginator's COUNT(*) instead of issuing a second blogs.count() query.
        ctx['remaining_count']=max(0,paginated_blogs.count - self.PAGE_SIZE)
        page_number = request.GET.get('page')
        try:
            user_page_obj = paginated_blogs.get_page(page_number)
        except PageNotAnInteger:
            user_page_obj = paginated_blogs.get_page(1)
        except EmptyPage:
            user_page_obj = paginated_blogs.get_page(paginated_blogs.num_pages)
        
        ctx['page_obj']=user_page_obj
        student_id = request.GET.get("student_id")
        ctx['bookmarked_blog_ids'] = _bookmarked_blog_ids_for_request(request, student_id=student_id)
        ctx['is_parent_student_context'] = False
        ctx['parent_student_id'] = None
        try:
            if request.user.is_authenticated and getattr(request.user, "user_type", None) == choices.UserType.PARENT and student_id:
                from users.models import ParentStudentLink
                if ParentStudentLink.objects.filter(parent=request.user, student_id=int(student_id)).exists():
                    ctx['is_parent_student_context'] = True
                    ctx['parent_student_id'] = int(student_id)
        except Exception:
            pass
        from users.parent_suggestions import apply_student_parent_suggestions_context, maybe_mark_parent_suggestions_seen
        apply_student_parent_suggestions_context(ctx, request, "blogs")
        maybe_mark_parent_suggestions_seen(
            request, "blogs", is_parent_student_context=ctx.get("is_parent_student_context", False)
        )
        return ctx

    def get(self, request, *args, **kwargs):
        if request.GET.get("pagination_ajax",None) and request.GET.get("pagination_ajax") == "Yes":
            ctx=self.get_context(request, *args, **kwargs)
            data={}
            data['html'] = render_to_string("topteenfrontend/includes/blog_item.html",ctx)
            data['page_number']=ctx['page_obj'].number
            data['remaining']= ctx['page_obj'].paginator.count - ctx['page_obj'].number*self.PAGE_SIZE
            data['next_page']= ctx['page_obj'].next_page_number()  if ctx['page_obj'].has_next() else 0
            return JsonResponse(data)
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))

class BlogDetail(TemplateView):
    template_name = "template20/blog_detail.html"

    def html_head(self, blog, request=None):
        titleb = blog.title or ""
        descriptionb = blog.summary or ""
        image_url = None
        if blog.image and blog.image.name:
            image_url = blog.get_image_url()
            if request and image_url and not image_url.startswith(('http://', 'https://')):
                image_url = request.build_absolute_uri(image_url)
        # url_key for PageSEO: path-style so dashboard can create/edit SEO for this page
        url_key = "blogs/{}".format(blog.slug)
        return get_page_seo_html_head(url_key, titleb, descriptionb, default_image=image_url, request=request)
    
    def _breadcrumb(self, blog):
        url = str(reverse('blog:blogs'))
        return get_breadcrumb([{'text': 'Blogs', 'url': url}, {'text': blog.title, 'url': ''}])
    
    def get_context(self, request, *args, **kwargs):  
        ctx={}
        blog_slug = kwargs.get('blog_slug')
        search_blogs =request.GET.get('search')

        if search_blogs:
            ctx["search_blogs"] = search_blogs
        else:
            ctx['search_blogs']=""

        blogs=Blog.get_published_objects().select_related('author', 'category')
        blog=get_object_or_404(blogs,slug=blog_slug)
        latest_blogs=Blog.get_published_objects().select_related('author', 'category').exclude(id=blog.id).order_by('-created')
        blog.views_count += 1
        blog.save()
        if blog.category:
            category = get_object_or_404(BlogCategory,slug=blog.category.slug)
            ctx['related_blogs'] = Blog.get_published_objects().select_related('author', 'category').filter(category=category).exclude(id=blog.id)[:4]
        else:
            ctx['related_blogs'] = Blog.get_published_objects().select_related('author', 'category').exclude(id=blog.id)[:4]
        from django.urls import reverse
        ctx['categories']=BlogCategory.objects.all()
        ctx['blog']=blog    
        ctx['views_count']=blog.views_count
        ctx['html_head'] = self.html_head(blog, request)
        ctx['html_head'] = self.html_head(blog, request)
        bread_crumb =self._breadcrumb(blog)
        ctx['breadcrumb']= bread_crumb
        # SEO: Article schema for blog detail (dates + author)
        ctx['seo_schema_type'] = 'Article'
        ctx['seo_schema_extra'] = {
            'date_published': blog.created.isoformat() if blog.created else None,
            'date_modified': blog.modified.isoformat() if blog.modified else None,
            'author': getattr(blog.author, 'get_full_name', lambda: None)() or getattr(blog.author, 'username', 'TopTeen'),
        }
        # SEO: Article schema for blog detail (dates + author)
        ctx['seo_schema_type'] = 'Article'
        ctx['seo_schema_extra'] = {
            'date_published': blog.created.isoformat() if blog.created else None,
            'date_modified': blog.modified.isoformat() if blog.modified else None,
            'author': getattr(blog.author, 'get_full_name', lambda: None)() or getattr(blog.author, 'username', 'TopTeen'),
        }
        ctx['latest_blogs']= latest_blogs[:5]
        student_id = request.GET.get("student_id")
        ctx['is_blog_bookmarked'] = _is_blog_bookmarked_for_request(request, blog, student_id=student_id)
        ctx['bookmarked_blog_ids'] = _bookmarked_blog_ids_for_request(request, student_id=student_id)
        ctx['is_parent_student_context'] = False
        ctx['parent_student_id'] = None
        try:
            if request.user.is_authenticated and getattr(request.user, "user_type", None) == choices.UserType.PARENT and student_id:
                from users.models import ParentStudentLink
                if ParentStudentLink.objects.filter(parent=request.user, student_id=int(student_id)).exists():
                    ctx['is_parent_student_context'] = True
                    ctx['parent_student_id'] = int(student_id)
        except Exception:
            pass
        return ctx

    def get(self, request, *args, **kwargs):
        # This codebase uses get_context() (not TemplateView.get_context_data),
        # so we must render explicitly.
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))


class ToggleBlogBookmark(APIView):
    """
    Toggle blog bookmark for the logged-in user.
    """
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({"success": False, "message": "Login required"}, status=401)
        blog_id = request.POST.get("blog_id")
        blog_slug = request.POST.get("blog_slug")
        blogs = Blog.get_published_objects()
        if blog_id:
            blog = get_object_or_404(blogs, id=blog_id)
        else:
            blog = get_object_or_404(blogs, slug=blog_slug)

        if getattr(request.user, "user_type", None) == choices.UserType.PARENT:
            from users.parent_saved_items import toggle_parent_blog_bookmark

            student_id = request.POST.get("student_id")
            try:
                sid = int(student_id) if student_id not in (None, "", b"") else None
            except (TypeError, ValueError):
                sid = None
            return JsonResponse(toggle_parent_blog_bookmark(request.user, blog, student_id=sid))

        from .models import BlogShortlist
        obj = BlogShortlist.objects.filter(user=request.user, blog=blog).first()
        if obj:
            obj.delete()
            return JsonResponse({"success": True, "bookmarked": False, "message": "Removed from shortlist"})
        BlogShortlist.objects.create(user=request.user, blog=blog)
        return JsonResponse({"success": True, "bookmarked": True, "message": "Blog shortlisted"})
    
    def _breadcrumb(self, blog):
        from django.urls import reverse
        url = str(reverse('blog:blogs'))
        return get_breadcrumb([{'text': 'Blogs', 'url': url}, {'text': blog.title, 'url': ''}])

    def get(self, request, *args, **kwargs):     
        return render(request, self.template_name, self.get_context(request, *args, **kwargs))

def category_filter(request,category_slug, *args, **kwargs):
    page_size = 6
    category = get_object_or_404(BlogCategory,slug=category_slug)
    blog = Blog.get_published_objects().select_related('author', 'category').filter(category=category).order_by('-modified')
    categories = BlogCategory.objects.all()
    pages= Paginator(blog,page_size)
    page_numbers = request.GET.get('page')
    latest_blogs=Blog.get_published_objects().select_related('author', 'category').order_by('-created')[:3]
    page_objs = pages.get_page(page_numbers)
    # Reuse Paginator's cached count (get_page already computed it) to avoid a 2nd COUNT query.
    remaining_count = pages.count - page_size
    remaining_count = remaining_count if remaining_count > 0 else None
    
    from django.urls import reverse
    cat_display = _blog_category_display(category.name)
    cat_short = _blog_category_short(category.name)
    blog_search_list = [{'title': b.title, 'slug': b.slug, 'url': reverse('blog:blogdetail', args=[b.slug])} for b in Blog.get_published_objects().only('title', 'slug')]
    student_id = request.GET.get("student_id")
    ctx={'blogs':blog,'categories':categories,'page_obj':page_objs,'latest_blogs':latest_blogs,'site_url':"https://topteen.in","category": category,'remaining_count':remaining_count,"html_head":build_html_head(title=f"Blogs - {cat_display}",description=f"Explore blogs {cat_short} category."),'breadcrumb': get_breadcrumb([{'text': cat_display, 'url': reverse('blog:category', args=[category.slug])}]),'heading': cat_display,'blog_search_list': blog_search_list, 'bookmarked_blog_ids': _bookmarked_blog_ids_for_request(request, student_id=student_id), 'is_parent_student_context': False, 'parent_student_id': None}
    try:
        if request.user.is_authenticated and getattr(request.user, "user_type", None) == choices.UserType.PARENT and student_id:
            from users.models import ParentStudentLink
            if ParentStudentLink.objects.filter(parent=request.user, student_id=int(student_id)).exists():
                ctx['is_parent_student_context'] = True
                ctx['parent_student_id'] = int(student_id)
    except Exception:
        pass

    if request.GET.get("pagination_ajax",None) and request.GET.get("pagination_ajax") == "Yes":
            data={}
            data['html'] = render_to_string("topteenfrontend/includes/blog_item.html",ctx)
            data['page_number']=ctx['page_obj'].number
            data['remaining']=pages.count - page_objs.number*page_size
            data['next_page']= ctx['page_obj'].next_page_number()  if ctx['page_obj'].has_next() else 0
            return JsonResponse(data)
    return render(request,"template20/blogs.html",ctx)

def blogtag_filter(request,tagslug, *args, **kwargs):
    page_size = 6
    blogtag=get_object_or_404(BlogTag,slug=tagslug)
    blogs = Blog.get_published_objects().select_related('author', 'category').filter(tags=blogtag).order_by('-modified')
    latest_blogs =Blog.get_published_objects().select_related('author', 'category').order_by('-created')[:3]
    categories = BlogCategory.objects.all()
    page_numbers = request.GET.get('page')
    pages= Paginator(blogs,page_size)
    page_objs = pages.get_page(page_numbers)
    # Reuse Paginator's cached count (get_page already computed it) to avoid a 2nd COUNT query.
    remaining_count = pages.count - page_size
    remaining_count = remaining_count if remaining_count > 0 else None
    from django.urls import reverse
    blog_search_list = [{'title': b.title, 'slug': b.slug, 'url': reverse('blog:blogdetail', args=[b.slug])} for b in Blog.get_published_objects().only('title', 'slug')]
    student_id = request.GET.get("student_id")
    ctx={'blogs':blogs, 'page_obj':page_objs,'latest_blogs':latest_blogs,'categories':categories,'site_url':"https://topteen.in",'blogtag':blogtag ,'remaining_count':remaining_count,'html_head':build_html_head(title=f"Blogs - {blogtag.name}",description=f"Explore blogs tagged with {blogtag.name}"),'breadcrumb': get_breadcrumb([{'text': blogtag.name, 'url': reverse('blog:blogtag', args=[blogtag.slug])}]),'heading': f"Blogs tagged with {blogtag.name}",'blog_search_list': blog_search_list, 'bookmarked_blog_ids': _bookmarked_blog_ids_for_request(request, student_id=student_id), 'is_parent_student_context': False, 'parent_student_id': None}
    try:
        if request.user.is_authenticated and getattr(request.user, "user_type", None) == choices.UserType.PARENT and student_id:
            from users.models import ParentStudentLink
            if ParentStudentLink.objects.filter(parent=request.user, student_id=int(student_id)).exists():
                ctx['is_parent_student_context'] = True
                ctx['parent_student_id'] = int(student_id)
    except Exception:
        pass

    if request.GET.get("pagination_ajax",None) and request.GET.get("pagination_ajax") == "Yes":
            data={}
            data['html'] = render_to_string("topteenfrontend/includes/blog_item.html",ctx)
            data['page_number']=ctx['page_obj'].number
            data['remaining']= pages.count - page_objs.number*page_size
            data['next_page']= ctx['page_obj'].next_page_number()  if ctx['page_obj'].has_next() else 0
            return JsonResponse(data)
    return render(request,"template20/blogs.html",ctx)


class SubscribeView(APIView):

    def post(self, request):   
        import re
        evalid = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        email=request.POST.get("email")
        em=re.match(evalid,email)
        if em:
            sub_email=SubscriptionEmail(email=email)
            sub_email.save()
            return JsonResponse({'success': "true"})
        else:
            return JsonResponse({'success': "false"})