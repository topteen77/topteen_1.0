from django.urls import path
from . import views

app_name="blog"
urlpatterns = [
    path("",views.Blogs.as_view(),name="blogs"),
    path("api/autocomplete/", views.autocomplete_blogs, name="autocomplete_blogs"),
    path("category/<slug:category_slug>/",views.category_filter,name="category"),
    path("tag/<slug:tagslug>/",views.blogtag_filter,name="blogtag"),
    path("subscribemail/",views.SubscribeView.as_view(),name="subscribemail"),
    path("bookmark/", views.ToggleBlogBookmark.as_view(), name="toggle_blog_bookmark"),
    path("<blog_slug>/",views.BlogDetail.as_view(),name="blogdetail"),
    #path("author/<int:author_id>",views.author,name="author"),
]