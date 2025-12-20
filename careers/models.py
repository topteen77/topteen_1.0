from os import link
from pyexpat import model
from unicodedata import name
from django.db import models
from core.models import BaseModel,SlugModel,SeoModel,PublishableModel
from ckeditor.fields import RichTextField
from courses.models import Course
from .utils import  career_media_directory, get_formated_currency,career_cluster_image_directory
from core import choices
from django.urls import reverse
from django.shortcuts import get_object_or_404
import random
from users.models import User
from django.db.models import Q,Avg,Count,F,ExpressionWrapper,IntegerField
from django.core.validators import MaxValueValidator,MinValueValidator
# Create your models here.
    
Active_Status = 1
Inactive_Status = 0
STATUS_CHOICES = (
    (Active_Status, 'Active'),
    (Inactive_Status, 'Inactive'),
    )
    
class CareerCluster(BaseModel,SlugModel):
    name=models.CharField(max_length=500,null=True)
    parent = models.ForeignKey('self',blank=True,null=True,on_delete=models.SET_NULL,related_name="children")
    image = models.ImageField(upload_to=career_cluster_image_directory,null=True,blank=True)
    def get_image_url(self):
        """Get image URL with default fallback"""
        if self.image and self.image.name:
            return self.image.url
        return '/static/images/career-cluster-default.png'  # Default career cluster image

    def get_careers(self):
        return Career.objects.filter(Q(career_cluster=self)|Q(career_cluster__parent=self)).exclude(publish_status=choices.PublishStatus.DRAFT)
   
    @classmethod
    def get_career_library_context(cls,request,cluster_slug=None,cluster_id=None):
        q=request.GET.get("careersearch",None)
        ctx={}
        published_status = choices.PublishStatus.PUBLISHED
        if cluster_slug and cluster_id:
            clstr=get_object_or_404(CareerCluster,slug=cluster_slug,id=cluster_id)
            ctx['current_cluster'] = clstr
            # Child clusters (show all, but mark inactive if they have no active careers).
            ctx['clusters'] = clstr.children.all().annotate(
                direct_active_careers=Count(
                    'career_clusters',
                    filter=Q(career_clusters__publish_status=published_status),
                    distinct=True,
                ),
                child_active_careers=Count(
                    'children__career_clusters',
                    filter=Q(children__career_clusters__publish_status=published_status),
                    distinct=True,
                ),
            ).annotate(
                active_career_count=ExpressionWrapper(
                    F('direct_active_careers') + F('child_active_careers'),
                    output_field=IntegerField(),
                )
            )
            if q:
                # When searching, do not show inactive clusters in results.
                ctx['clusters'] = ctx['clusters'].filter(name__icontains=q).filter(active_career_count__gt=0)
            ctx['careers']=clstr.get_careers()
            ctx["cluster_name"]=clstr.name
        else:
            # Top-level tracks (show all, but mark inactive if they have no active careers).
            ctx['clusters'] = cls.objects.filter(parent__isnull=True).annotate(
                direct_active_careers=Count(
                    'career_clusters',
                    filter=Q(career_clusters__publish_status=published_status),
                    distinct=True,
                ),
                child_active_careers=Count(
                    'children__career_clusters',
                    filter=Q(children__career_clusters__publish_status=published_status),
                    distinct=True,
                ),
            ).annotate(
                active_career_count=ExpressionWrapper(
                    F('direct_active_careers') + F('child_active_careers'),
                    output_field=IntegerField(),
                )
            )
            if q:
                # When searching, do not show inactive tracks in results.
                ctx['clusters'] = ctx['clusters'].filter(name__icontains=q).filter(active_career_count__gt=0)
            ctx['careers']=Career.objects.filter(career_cluster__in=ctx['clusters']).exclude(publish_status=choices.PublishStatus.DRAFT)
            ctx['cluster_name']="Career Tracks"
        if q:
            ctx['careers']=ctx['careers'].filter(name__icontains=q)
        return ctx

    def get_clstr_career_count(self,career_ids):
        careers=Career.objects.filter(id__in=career_ids).exclude(publish_status=choices.PublishStatus.DRAFT)
        count=careers.filter(career_cluster=self).count()
        return count

class Skill(BaseModel,SlugModel):
    name = models.CharField(max_length=250,null=True)
    priority = models.PositiveSmallIntegerField(default=1,help_text="1 is higher than 2")
    
    class Meta(BaseModel.Meta):
        permissions = [('list_skill', 'Can view list of Skill')]
    
class ProspectiveEmploymentArea(BaseModel,SlugModel):
    name = models.CharField(max_length=500,null=True)
    
    class Meta(BaseModel.Meta):
        permissions = [('list_prospectiveemploymentarea', 'Can view list of ProspectiveEmploymentArea')]

class ProspectiveRecruiter(BaseModel,SlugModel):
    name =  models.CharField(max_length=500,null=True)
    
    class Meta(BaseModel.Meta):
        permissions = [('list_prospectiverecruiter', 'Can view list of ProspectiveRecruiter')]

class CareerTags(BaseModel,SlugModel):
    name = models.CharField(max_length=500,null=True)
    description = models.CharField(max_length=500,null=True)
    priority = models.PositiveSmallIntegerField(default=1,help_text="1 is higher than 2")
    icon=models.ImageField(upload_to=career_media_directory,null=True,max_length=250)
    status = models.IntegerField(choices=STATUS_CHOICES,blank=True)

    def url(self):
        return reverse('careers:careertag',args=[self.slug])

    class Meta(BaseModel.Meta):
        permissions = [('list_careertags', 'Can view list of careertags')]

class CareerPathStep(BaseModel):
    name = models.CharField(max_length=300,null=True)
    priority = models.PositiveSmallIntegerField(default=1,help_text="1 is higher than 2")
    
    class Meta(BaseModel.Meta):
        permissions = [('list_careerpathsteps', 'Can view list of CareerPathSteps')]
   
       
class CareerPath(BaseModel):
    name = models.CharField(max_length=300,null=True)
    career_route_name=models.CharField(max_length=300,blank=True)
    career_path_steps= models.ManyToManyField(CareerPathStep)

    class Meta(BaseModel.Meta):
        permissions = [('list_careerpath', 'Can view list of CareerPath')]   

    def get_sorted_priority(self):
        return self.career_path_steps.all().order_by('priority')     


class Career(BaseModel,SlugModel,SeoModel,PublishableModel):
    name = models.CharField(max_length=500,null=True)
    summary = models.CharField(null=True,max_length=250)
    description = RichTextField(null=True)
    image=models.ImageField(upload_to=career_media_directory,null=True,blank=True,max_length=250)
    role_description = RichTextField(null=True)
    eligibility = RichTextField(null=True)
    pros_cons = RichTextField(null=True)
    skills = models.ManyToManyField(Skill, blank=True)
    prospective_employment_areas = models.ManyToManyField(ProspectiveEmploymentArea, blank=True)
    prospective_recruiters = models.ManyToManyField(ProspectiveRecruiter, blank=True)
    career_tags = models.ManyToManyField(CareerTags, blank=True)
    courses = models.ManyToManyField(Course,blank=True)
    career_cluster=models.ManyToManyField(CareerCluster,related_name="career_clusters", blank=True)
    career_paths = models.ManyToManyField(CareerPath, blank=True)
    video_url=models.URLField(max_length=250,blank=True)
    videos = models.ManyToManyField("Videos", blank=True)

    
    class Meta(BaseModel.Meta):
        permissions = [('list_career', 'Can view list of Career')]
        
    def url(self):
        return reverse('careers:careerdetail',args=[self.slug,self.id])
    
    def get_image_url(self):
        """Get image URL with default fallback"""
        if self.image and self.image.name:
            return self.image.url
        return '/static/images/career-icon.png'  # Default career icon
    
    def get_xmind_file_path(self):
        """
        Dynamically find XMind file path based on career name and cluster structure.
        Uses the career_mindmap directory at project root.
        Returns None gracefully if file doesn't exist (no errors).
        """
        from pathlib import Path
        from django.conf import settings
        
        try:
            # Use absolute path: /career_mindmap directory at project root
            mind_maps_base = Path(settings.BASE_DIR) / 'career_mindmap'
            
            # Return None if base directory doesn't exist
            if not mind_maps_base.exists():
                return None
            
            # Try multiple search strategies
            search_paths = []
            
            # Strategy 1: Use career clusters (same as import structure)
            if self.career_cluster.exists():
                for cluster in self.career_cluster.all():
                    cluster_folder = cluster.name.strip()
                    cluster_path = mind_maps_base / cluster_folder
                    
                    # Skip if cluster folder doesn't exist
                    if not cluster_path.exists():
                        continue
                    
                    # Try exact career name
                    search_paths.append(cluster_path / f'{self.name}.xmind')
                    # Try slugified name
                    from django.utils.text import slugify
                    search_paths.append(cluster_path / f'{slugify(self.name)}.xmind')
                    # Try with underscores
                    search_paths.append(cluster_path / f'{self.name.replace(" ", "_")}.xmind')
                    # Try with hyphens
                    search_paths.append(cluster_path / f'{self.name.replace(" ", "-")}.xmind')
                    # Try lowercase
                    search_paths.append(cluster_path / f'{self.name.lower()}.xmind')
            
            # Strategy 2: Search all folders (fallback) - only if no cluster matches
            if not search_paths and mind_maps_base.exists():
                from django.utils.text import slugify
                for cluster_folder in mind_maps_base.iterdir():
                    if cluster_folder.is_dir():
                        search_paths.append(cluster_folder / f'{self.name}.xmind')
                        search_paths.append(cluster_folder / f'{slugify(self.name)}.xmind')
                        search_paths.append(cluster_folder / f'{self.name.lower()}.xmind')
            
            # Check each potential path
            for path in search_paths:
                try:
                    if path.exists() and path.is_file():
                        return path
                except (OSError, PermissionError):
                    # Skip files we can't access
                    continue
            
            return None
        
        except Exception:
            # Silently return None on any error
            return None

    def has_xmind_file(self):
        """Check if XMind file exists for this career. Returns False gracefully if not found."""
        try:
            return self.get_xmind_file_path() is not None
        except Exception:
            return False
    
    def has_mindmap_data(self):
        """
        Check if mindmap data is available for this career.
        Returns True if either XMind file exists OR description contains h2 headings.
        """
        try:
            # First check for XMind file
            if self.has_xmind_file():
                return True
            
            # Then check if description has h2 tags
            if self.description:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(self.description, 'html.parser')
                h2_tags = soup.find_all('h2')
                if h2_tags:
                    return True
            
            return False
        except Exception:
            return False
    
    def validate_mindmap(self):
        """
        Validate mindmap file for this career.
        Returns tuple: (is_valid: bool, errors: list)
        Checks:
        1. If mindmap file exists
        2. If title in XMind file matches career name
        """
        errors = []
        
        # Check if file exists
        xmind_path = self.get_xmind_file_path()
        if not xmind_path or not xmind_path.exists():
            errors.append("Mindmap file not found")
            return (False, errors)
        
        # Check if title matches
        try:
            import xmindparser
            xmind_data = xmindparser.xmind_to_dict(str(xmind_path))
            
            if not xmind_data or not isinstance(xmind_data, list) or len(xmind_data) == 0:
                errors.append("Invalid XMind file format")
                return (False, errors)
            
            sheet = xmind_data[0]
            root_topic = sheet.get('topic', {})
            xmind_title = root_topic.get('title') or root_topic.get('label') or ''
            
            # Normalize both titles for comparison (case-insensitive, strip whitespace)
            career_name_normalized = (self.name or '').strip().lower()
            xmind_title_normalized = xmind_title.strip().lower()
            
            if career_name_normalized and xmind_title_normalized:
                if career_name_normalized != xmind_title_normalized:
                    errors.append(f"Title mismatch: XMind has '{xmind_title}' but career name is '{self.name}'")
                    return (False, errors)
            
        except ImportError:
            errors.append("xmindparser library not available")
            return (False, errors)
        except Exception as e:
            errors.append(f"Error reading XMind file: {str(e)}")
            return (False, errors)
        
        # All validations passed
        return (True, [])
    
    def convert_description_to_jsmind_json(self):
        """
        Convert HTML content from career.description to jsMind format.
        Extracts all h2 headings and creates a mindmap structure.
        Also extracts h3 headings as sub-children of h2.
        
        Returns:
            dict: jsMind-compatible JSON structure with 'meta', 'format', and 'data' keys
            None: if description is empty or parsing fails
        """
        if not self.description or not self.name:
            return None
        
        try:
            from bs4 import BeautifulSoup
            from django.utils.html import strip_tags
            import logging
            
            logger = logging.getLogger(__name__)
            
            soup = BeautifulSoup(self.description, 'html.parser')
            
            # Root node with career name
            root_node = {
                'id': 'root',
                'topic': self.name,
                'expanded': True,
                'children': []
            }
            
            # Find all h2 and h3 tags
            all_headings = soup.find_all(['h2', 'h3'])
            
            if not all_headings:
                # If no headings, return just the root node
                return {
                    'meta': {
                        'name': self.name,
                        'author': 'HTML Parser',
                        'version': '1.0'
                    },
                    'format': 'node_tree',
                    'data': root_node
                }
            
            # Process headings to build hierarchy
            h2_idx = -1
            h3_idx = 0
            
            for heading in all_headings:
                heading_text = heading.get_text(strip=True)
                if not heading_text:
                    continue
                
                if heading.name == 'h2':
                    # New h2 - create new child node
                    h2_idx += 1
                    h3_idx = 0
                    
                    h2_node = {
                        'id': f'root-{h2_idx}',
                        'topic': heading_text,
                        'expanded': True,
                        'children': []
                    }
                    root_node['children'].append(h2_node)
                
                elif heading.name == 'h3' and h2_idx >= 0:
                    # h3 - add as child of current h2
                    h3_node = {
                        'id': f'root-{h2_idx}-{h3_idx}',
                        'topic': heading_text,
                        'expanded': True
                    }
                    
                    # Add to the last h2 node's children
                    if root_node['children']:
                        root_node['children'][-1]['children'].append(h3_node)
                        h3_idx += 1
            
            return {
                'meta': {
                    'name': self.name,
                    'author': 'HTML Parser',
                    'version': '1.0'
                },
                'format': 'node_tree',
                'data': root_node
            }
        
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f'Error parsing HTML description for mindmap (career: {self.name}): {str(e)}')
            return None
    
    def save(self, *args, **kwargs):
        """Convert only non-ASCII characters to numeric entities, preserve HTML tags."""
        import html

        def to_numeric_entities_preserve_html(text):
            if not text:
                return text
            # Ensure we operate on actual characters (unescape existing entities first)
            unescaped = html.unescape(text)
            # Replace non-ASCII with numeric entities, keep ASCII (incl. <, >, &)
            return unescaped.encode('ascii', 'xmlcharrefreplace').decode('ascii')

        if self.description:
            self.description = to_numeric_entities_preserve_html(self.description)
        if self.summary:
            converted_summary = to_numeric_entities_preserve_html(self.summary)
            if len(converted_summary) > 250:
                converted_summary = converted_summary[:247] + '...'
            self.summary = converted_summary
        if self.role_description:
            self.role_description = to_numeric_entities_preserve_html(self.role_description)
        if self.eligibility:
            self.eligibility = to_numeric_entities_preserve_html(self.eligibility)
        if self.pros_cons:
            self.pros_cons = to_numeric_entities_preserve_html(self.pros_cons)
        if self.name:
            converted_name = to_numeric_entities_preserve_html(self.name)
            if len(converted_name) > 500:
                converted_name = converted_name[:497] + '...'
            self.name = converted_name

        super().save(*args, **kwargs)
    
    @classmethod
    def get_all_careers(cls):
        return Career.objects.filter(publish_status=choices.PublishStatus.PUBLISHED)
    
    def get_max_salary(self):
        profession=Profession.objects.filter(career_id=self.id).order_by('-salary').first()
        if profession is None:
            return "N/A"
        return profession.get_salary_display()
    
    def get_average_rating(self):
        avg=CareerRating.objects.filter(career=self).aggregate(average=Avg('rating'))
        if avg['average']:
            rate=(avg['average']+4.5)/2
            return str(round(rate,1))
        else:
            return "4.5"
        
    def get_rating_percent(self,num):
        num_of_rating=CareerRating.objects.filter(career=self,rating=num).count()
        total_rating=CareerRating.objects.filter(career=self).exclude(rating=0).count()
        if num_of_rating and total_rating:
            percent=(num_of_rating/total_rating)*100
            return round(percent,0)
        else:
            return 0
    
    def get_validation_errors(self):
        """Get list of validation errors for this career"""
        errors = []
        
        # Check required fields
        if not self.name or not self.name.strip():
            errors.append("Career name is required")
            
        if not self.summary or not self.summary.strip():
            errors.append("Career summary is required")
            
        if not self.description or not self.description.strip():
            errors.append("Career description is required")
            
        # Image is optional - we have a default fallback
        # No validation needed for image field
            
        # Check if slug exists
        if not self.slug or not self.slug.strip():
            errors.append("Career slug is required")
            
        return errors
    
    def is_valid_for_preview(self):
        """Check if career is valid for preview"""
        return len(self.get_validation_errors()) == 0
    
    def get_validation_status(self):
        """Get validation status with color coding"""
        errors = self.get_validation_errors()
        if not errors:
            return "valid"
        elif len(errors) <= 2:
            return "warning"
        else:
            return "error"
    
class CareerRating(BaseModel):
    user = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True)
    career = models.ForeignKey(Career,on_delete=models.CASCADE,related_name='career_rating')
    rating = models.IntegerField(null=True,default=0,validators=[MinValueValidator(0), MaxValueValidator(5)])
    title = models.CharField(max_length=255,null=True,blank=True)
    description = models.CharField(max_length=555,null=True,blank=True)


class CareerMedia(BaseModel):
    career = models.ForeignKey(Career,null=True,on_delete=models.SET_NULL,related_name="careermedia")
    type = models.SmallIntegerField(choices=choices.CareerMediaType.CHOICES, default=choices.CareerMediaType.IMAGE)
    media = models.FileField(upload_to=career_media_directory,null=True)
    priority = models.PositiveSmallIntegerField(default=1,help_text="1 is higher than 2")
    
    class Meta(BaseModel.Meta):
        permissions = [('list_careermedia', 'Can view list of CareerMedia')]


class Profession(BaseModel,SlugModel):
    name = models.CharField(max_length=300,null=True)
    career =models.ForeignKey(Career,null=True,on_delete=models.SET_NULL,related_name="profession")
    image = models.ImageField(upload_to=career_media_directory,null=True)
    summary = models.TextField(blank=True)
    salary=models.IntegerField()
    salary_type=models.SmallIntegerField(choices=choices.SalaryType.CHOICE,default=choices.SalaryType.PER_ANNUM)
    currency = models.PositiveSmallIntegerField(choices=choices.Currency.CHOICES,default=choices.Currency.USD)

    def url(self):
        return reverse('careers:profession',args=[self.career.slug])

    def get_salary_display(self):
        return get_formated_currency(self.salary)

class CareerFAQ(BaseModel):
    career = models.ForeignKey(Career,on_delete=models.CASCADE,related_name="careerFAQ")
    question = models.CharField(max_length=300,null=True)
    answer = RichTextField(null=True)

    class Meta(BaseModel.Meta):
        permissions = [('list_careerFAQ', 'Can view list of CareerFAQ')]    

class CareerShortlist(BaseModel):
    user=models.ForeignKey(User,null=True,on_delete=models.CASCADE,related_name="career_shortlists")
    career=models.ForeignKey(Career,null=True,on_delete=models.CASCADE,related_name="shortslists")

class VideoCategory(BaseModel,SlugModel):
    name=models.CharField(max_length=200)
    color = models.CharField(max_length=7,null=True)
    
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

class Videos(BaseModel,SlugModel):
    name=models.CharField(max_length=200)
    link=models.URLField(max_length=260, blank=True)
    upload_video=models.FileField(upload_to=career_media_directory,blank=True)
    description=RichTextField(null=True)
    category = models.ManyToManyField(VideoCategory,related_name="videos")
    shortlist = models.ManyToManyField(User,blank=True,related_name='video_shortlist')
    video_image=models.FileField(upload_to=career_media_directory,null=True,blank=True)
    
    
    def get_video_or_url(self):
        if self.link:
            return self.link
        if self.upload_video:
            return self.upload_video.url
            
        raise Exception('No video found')
    
    def get_thumbnail_url(self):
        """Get video thumbnail URL - prefer video_image, fallback to YouTube thumbnail"""
        # First check if video_image exists
        if self.video_image and self.video_image.name:
            try:
                return self.video_image.url
            except:
                pass
        
        # If no video_image but has YouTube link, extract thumbnail
        if self.link:
            import re
            # Check if it's a YouTube URL
            youtube_patterns = [
                r'(?:youtube\.com\/embed\/|youtu\.be\/|youtube\.com\/watch\?v=)([a-zA-Z0-9_-]+)',
                r'youtube\.com\/v\/([a-zA-Z0-9_-]+)',
            ]
            
            for pattern in youtube_patterns:
                match = re.search(pattern, self.link)
                if match:
                    video_id = match.group(1)
                    # Return YouTube thumbnail URL (hqdefault is more reliable than maxresdefault)
                    # hqdefault.jpg (480x360) is available for most videos
                    return f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'
        
        # For S3 or other video URLs without video_image, return None
        # The template will show a placeholder icon
        return None

class RIASECCareer(BaseModel):
    key = models.CharField(max_length=200,unique=True)
    careers=models.ManyToManyField(Career,related_name="riasec_career")