from unicodedata import name
from django.db import models
from core.models import (BaseModel, SlugModel,SeoModel,PublishableModel)
from core import choices
from users.models import User
from django.urls import reverse
from ckeditor.fields import RichTextField
import random
# Create your models here.

def blog_image_directory(instance, filename):
    # file will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return 'upload/blog/{0}'.format(filename)


class BlogCategory(BaseModel,SlugModel):
    name = models.CharField(max_length=200)
    color = models.CharField(max_length=7,null=True)
    def url(self):
        return reverse('blog:category',args=[self.slug])
    
    def save(self, *args, **kwargs):
        if not self.color:
            self._set_color()
        super().save(*args, **kwargs)
       

    def _set_color(self):
        colors_lst=['00AA55','1BA39C','03A678','00AA00','26A65B','00A566','4183D7','3477DB','007FAA',\
            '3455DB','0000E0','0000B5','E26A6A','B381B3','E26A6A','BF6EE0','FF00FF','BF55EC','D252B2',\
            '9370DB','D25299','D25852','D2527F','E73C70','F62459','E000E0','AA8F00','AA8F00','D47500',\
            'FF4500','E63022','E76E3C','EF4836','FF0000','DC143C']
        self.color = random.choice(colors_lst)
        
class BlogTag(BaseModel,SlugModel):
    name = models.CharField(max_length=200)

    def url(self):
        return reverse('blog:name',args=[self.slug])

    

class Blog(BaseModel,SlugModel,SeoModel,PublishableModel):
    author = models.ForeignKey(User,on_delete=models.PROTECT)
    title = models.CharField(max_length=250)
    image = models.ImageField(upload_to=blog_image_directory)
    category = models.ForeignKey(BlogCategory,null=True,on_delete=models.SET_NULL)
    summary = models.CharField(blank=True,max_length=255)
    content = RichTextField(blank=True)
    views_count = models.IntegerField(default=0)
    tags=models.ManyToManyField(BlogTag)

    def url(self):
        return reverse('blog:blogdetail',args=[self.slug])
    
    
    def get_slug_field(self):
        return 'title'

    def get_image_url(self):
        """Get image URL with default fallback"""
        if self.image and self.image.name:
            return self.image.url
        return '/static/images/blog-default.png'  # Default blog image
    
    @classmethod
    def get_published_objects(cls):
        return Blog.objects.filter(publish_status=choices.PublishStatus.PUBLISHED)

class SubscriptionEmail(BaseModel):
    email=models.CharField(max_length=50,null=True,blank=True)


class BlogShortlist(BaseModel):
    """
    Simple bookmark/shortlist for blogs.
    Used by both Parents and Students; Students can also see linked parents' blog bookmarks.
    """
    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE, related_name="blog_shortlists")
    blog = models.ForeignKey(Blog, null=True, on_delete=models.CASCADE, related_name="shortlists")

    class Meta(BaseModel.Meta):
        unique_together = ("user", "blog")
        verbose_name = "Blog Bookmark"
        verbose_name_plural = "Blog Bookmarks"