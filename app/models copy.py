
from time import timezone
from django.utils import timezone
from django.db import models
from utils.db import AbstractModel
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save,m2m_changed,post_delete,pre_delete
from django.dispatch import receiver
from django.contrib.auth.hashers import check_password, make_password
import uuid,sys
from LuckyDraw.utils import encode_string_base64,decode_string_base64
from random import randint
import pyqrcode
from django.contrib.sites.shortcuts import get_current_site
import os
from django.contrib.sites.models import Site
from django.utils import timezone
from io import BytesIO
from urllib.parse import urlparse
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.conf import settings
from django_resized import ResizedImageField
from django.db import transaction
import wand.image
from PIL import ImageDraw,ImageFont
from datetime import datetime
import json
import requests


user_type_data = (('1', "Company"), ('2', "Store"))
draw_type_data = (('Scheme Level', "Scheme Level"), ('Store Level', "Store Level"))

class User(AbstractUser):
    user_type = models.CharField(choices=user_type_data, max_length=10 , null=True,blank=True)
    
    user_pass = models.CharField(max_length=255,null =True,blank=True)

    logo = ResizedImageField(upload_to='user_logo', null=True)

    hashtags = models.CharField(max_length=255,null =True,blank=True)
    
    def save(self,*args, **kwargs):
        if not self.pk and not self.is_superuser :
            self.password = make_password(self.password)
        if not self.username:
            is_unique = False
            while not is_unique:
                id = randint(10000000, 20000000)  # 19 digits: 1, random 18 digits
                if not User.objects.filter(id=id).exists():
                    is_unique = True
            self.username = id
        super().save(*args, **kwargs)

class Company(AbstractModel):
    title = models.CharField(max_length=40)
    admin = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    logo = ResizedImageField(upload_to='company', null=True)
    termsAndConditions = models.TextField(null=True)
    is_active = models.BooleanField(default=True)
    disabled_at = models.DateTimeField(null=True, blank=True)  # New field to store when the company was disabled

    def save(self, *args, **kwargs):
        if not self.is_active and self.disabled_at is None:
            self.disabled_at = timezone.now()  # Set the disabled timestamp
        if self.is_active: 
            self.disabled_at = None  # Clear the disabled timestamp if re-enabled
        super().save(*args, **kwargs)

    def _str_(self):
        return self.title

    class Meta:
        db_table = "Company"
        ordering = ["-created_at"]
        verbose_name_plural = "Companies"


class Store(AbstractModel):
    unique_id = models.CharField(max_length=250)
    title = models.CharField(max_length=40)
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null = True, blank = True)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null = True, blank = True)
    address = models.TextField()
    city = models.CharField(max_length=40)
    state = models.CharField(max_length=40)
    cc = models.CharField(max_length=40,null = True)
    termsAndConditions = models.TextField(null = True)
    hashtag = models.CharField(max_length=250,null = True,blank = True)
    

    def _str_(self):
        return self.title
    
    def save(self,*args, **kwargs):
        if not self.unique_id:
            is_unique = False
            while not is_unique:
                id = randint(100000, 200000) 
                if not Store.objects.filter(unique_id=id).exists():
                    is_unique = True
            self.unique_id = id
        super().save(*args, **kwargs)

    class Meta:
        db_table = "Store"
        ordering = [
            "-created_at",
        ]
        
    def get_participants_count(self,*args, **kwargs):
        return Participant.objects.filter(store__id = self.id).count()
        

class Customer(AbstractModel):
    name = models.CharField(max_length=40)
    contact = models.CharField(max_length=40, unique=True)

    def _str_(self):
        return self.name

    class Meta:
        db_table = "Customer"
        ordering = [
            "-created_at",
        ]


class Vehicle(AbstractModel):
    vehicleNumber = models.CharField(max_length=40)
    customer = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null = True
    )

    def _str_(self):
        return self.VehicleNumber

    class Meta:
        db_table = "Vehicle"
        ordering = [
            "-created_at",
        ]

from .middleware import CurrentUserMiddleware

class Scheme(AbstractModel):
    title = models.CharField(max_length=40)
    tagline = models.CharField(max_length=150,null = True)
    company = models.ForeignKey(
        Company, on_delete=models.SET_NULL , null = True,blank=True
    )
    startDate = models.DateField(null=True,blank=True)
    endDate = models.DateField(null=True,blank=True)
    maxWinners = models.PositiveIntegerField(default=3)
    stores = models.ManyToManyField(Store)
    drawDate = models.DateField(null=True,blank=True)
    unique_id = models.CharField(max_length=250)
    qr = models.FileField(upload_to='qr',null=True)
    termsAndConditions = models.TextField(null = True)
    qr_url = models.CharField(max_length=250,null=True)
    hastag = models.CharField(max_length=250,null = True,blank = True)
    details = models.TextField(null = True,blank = True)
    is_active = models.BooleanField(default=True)
    banner_image = models.FileField(upload_to='banners',null=True,blank = True)
    terms_and_conditions = models.FileField(upload_to='terms_and_conditions',null=True,blank = True)
    user = models.ManyToManyField(User)
    hashtags = models.CharField(max_length=255,null =True,blank=True)
    
    def save(self,*args, **kwargs):
        
        if not self.unique_id:
            is_unique = False
            while not is_unique:
                id = randint(100000, 200000) 
                if not Scheme.objects.filter(unique_id=id).exists():
                    is_unique = True
            self.unique_id = id
            print("unique_id" , self.unique_id)
        # site = "127.0.0.1"
        # print(self.stores.all(),'data')
        if not self.qr:
            current_site = f"http://{Site.objects.get_current().domain}"
            url_encoded = encode_string_base64(f"{self.unique_id}")
            s = f"{current_site}/draw-form/{url_encoded}"
            self.qr_url = s
            url = pyqrcode.create(s)
            qr_file_name = f"{settings.BASE_DIR}/media/qr_r{url_encoded}.png"
            qr_image = url.png(qr_file_name, scale = 25)
            im = Image.open(qr_file_name)


            width, height = im.size
            fontsize = 50
            font = ImageFont.truetype("Arial.ttf",fontsize)
            background = Image.new('RGBA', (width + 10, height + 170),color='white')
            draw = ImageDraw.Draw(background)
            Top_text = self.title.upper()
            # Bottom = self.company.company_name.upper()
            top_width = font.getlength(Top_text)
            # botton_width = font.getlength(Bottom)

            # draw.text((((width + 10)-top_width)/2,10), Top_text, (0, 0, 0),font = font, stroke_width=2,stroke_fill="black")
            # draw.text((((width + 10)-botton_width)/2,height+70),Bottom, (0, 0, 0),font = font, stroke_width=2,stroke_fill="black")
            draw.text((((width + 10)-top_width)/2,10), Top_text, (0, 0, 0),font = font)
            # draw.text((((width + 10)-botton_width)/2,height+70),Bottom, (0, 0, 0))

            background.paste(im, (0,70))
            

            file_name = f"{url_encoded}.png"
            output = BytesIO()
            background.save(output, format='png', quality=100)
            output.seek(0)
            background = InMemoryUploadedFile(output,'ImageField',file_name , 'image/jpeg', sys.getsizeof(output), None)
            self.qr = background
        super().save(*args, **kwargs)
        
    def get_participants(self):       
        return Participant.objects.filter(schema__id = self.id).count()
    
    def get_store_participants(self):
        current_user = CurrentUserMiddleware.get_current_user()
        return Participant.objects.filter(schema_id = self.id, store_in=self.stores.filter(admin=current_user)).count()
    
    def get_draws(self):
        return Draw.objects.filter(scheme__id = self.id).values_list('draw_universal_id',flat=True).order_by('draw_universal_id').exclude(draw_universal_id = None).distinct().count()
        
    def _str_(self):
        return self.title

    class Meta:
        db_table = "Scheme"
        ordering = [
            "-created_at",
        ]

class SchemeProducts(AbstractModel):
    title = models.CharField(max_length=40)
    scheme = models.ForeignKey(
        Scheme, on_delete=models.SET_NULL, null = True
    )

    def _str_(self):
        return self.title

    class Meta:
        db_table = "SchemeProducts"
        ordering = [
            "-created_at",
        ]
        verbose_name_plural = "Scheme Products"

class SchemeStores(AbstractModel):
    stores = models.ManyToManyField(Store)
    
    class Meta:
        db_table = "SchemeStores"
        ordering = [
            "-created_at",
        ]

# def upload_location(instance, filename):
#     filebase, extension = filename.split('.')
#     now = datetime.now()
#     name = filebase + str(now)
#     return 'Bill/%s.%s' % (filebase, extension)
        

def get_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename_start = filename.replace('.'+ext,'')
    now = datetime.now()
    filename = "%s__%s.%s" % (filename_start,now,ext)
    return os.path.join('Bill', filename)

class Participant(AbstractModel):
    
    created_at = models.DateTimeField(default=timezone.now)
    schema = models.ForeignKey(
        Scheme, on_delete=models.SET_NULL, null = True,blank=True
    )
    schemaproduct =  models.ForeignKey(
        SchemeProducts, on_delete=models.SET_NULL , null=True,blank=True
    )
    store =  models.ForeignKey(
        Store, on_delete=models.SET_NULL , null=True,blank=True
    )
    customer =models.ForeignKey(
        Customer, on_delete=models.SET_NULL , null=True,blank=True
    )
    name = models.CharField(max_length=200)
    contact = models.CharField(max_length=40)
    vehiclenumber = models.CharField(max_length=40)
    bill_no =  models.CharField(max_length=100)
    bill_image = ResizedImageField(size=[1240,1240],upload_to=get_file_path,null = True)
    entry_id = models.CharField(max_length=250)
    bill_signature = models.CharField(max_length=250,null=True)
    is_duplicate = models.BooleanField(default=False)

    def _str_(self):
        return self.entry_id

    class Meta:
        db_table = "Participant"
        ordering = [
            "-created_at",
        ]

    def save(self,*args, **kwargs):
        if not self.entry_id:
            is_unique = False
            while not is_unique:
                id = randint(100000, 200000) 
                if not Participant.objects.filter(entry_id=id).exists():
                    is_unique = True
            self.entry_id = id
        super().save(*args, **kwargs)

class StoreQR(AbstractModel):
    scheme = models.ForeignKey(
        Scheme, on_delete=models.SET_NULL, null = True
    )
    store = models.ForeignKey(
        Store, on_delete=models.SET_NULL, null = True
    )
    qr = models.FileField(upload_to='qr',null=True)
    url = models.CharField(null=True,max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "StoreQR"
        ordering = [
            "-created_at",
        ]


class Draw(AbstractModel):
    draw_id = models.CharField(max_length=250)
    draw_universal_id = models.CharField(max_length=250,null = True)
    scheme = models.ForeignKey(
        Scheme, on_delete=models.SET_NULL , null= True
    )
    draw_type = models.CharField(choices=draw_type_data, max_length=30 , null=True,blank=True)
    participant = models.ManyToManyField(Participant)
    store = models.ManyToManyField(Store)
    startDate = models.DateField(null=True,blank=True)
    endDate = models.DateField(null=True,blank=True)

    class Meta:
        db_table = "Draw"
        ordering = [
            "-created_at",
        ]
    def save(self,*args, **kwargs):
        if not self.draw_id:
            is_unique = False
            while not is_unique:
                id = randint(100000, 200000) 
                if not Draw.objects.filter(draw_id=id).exists():
                    is_unique = True
            self.draw_id = id
        super().save(*args, **kwargs)

    def get_stores(self):
        return self.store.all().count()
    
    def get_participants(self):
        return self.participant.all().count()
    
    def get_winners(self):
        win = DrawWinners.objects.get(draw__id = self.id)
        # len(win.winners)
        return len(win.winners)


class DrawWinners(AbstractModel):
    draw = models.ForeignKey(
        Draw, on_delete=models.SET_NULL , null= True
    )
    # scheme = models.ForeignKey(
    #     Scheme, on_delete=models.SET_NULL , null= True
    # )
    # participant = models.ForeignKey(
    #     Participant, on_delete=models.SET_NULL , null= True
    # )
    # winningSpot = models.PositiveIntegerField()
    winners = models.JSONField(null = True,blank = True)
    next_winners = models.JSONField(null = True,blank = True)
    
    class Meta:
        db_table = "DrawWinners"
        ordering = [
            "-created_at",
        ]
        verbose_name_plural = "Draw Winners"

class StorePages(AbstractModel):
    
    store = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True
    )
    page_id = models.CharField(max_length=100, unique=True)
    Auth_token = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = "StorePages"
        ordering = ["-created_at"]
        verbose_name_plural = "Store Pages"
        unique_together = ("store", "page_id")


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        print(instance.user_type,'test')
        if instance.user_type == 1 or instance.user_type == '1':
            Company.objects.create(admin=instance,title =instance.company_name)

def my_m2m_signal(sender,instance, **kwargs):
    action = kwargs.get('action')
    if action == 'post_add' or action == 'post_remove':
        StoreQR.objects.filter(scheme = instance).delete()
        stores = instance.stores.all()
        for i in stores:
            # current_site = f"http://{settings.SITE_ADD}"
            current_site = f"http://{Site.objects.get_current().domain}"
            base64_url = encode_string_base64(f"{instance.unique_id}_{i.unique_id}")
            s = f"{current_site}/draw-form/{base64_url}"
            url = pyqrcode.create(s)
            qr_file_name = f"{settings.BASE_DIR}/media/{i.city}.{i.cc}.png"
            qr_image = url.png(qr_file_name, scale = 25)
            im = Image.open(qr_file_name)
            width, height = im.size
            fontsize = 50
            font = ImageFont.truetype("Arial.ttf",fontsize)
            background = Image.new('RGBA', (width + 10, height + 170),color='white')
            draw = ImageDraw.Draw(background)
            Top_text = i.title.upper()
            Bottom = f"{i.cc}/{i.city.upper()}"
            top_width = font.getlength(Top_text)
            botton_width = font.getlength(Bottom)

            # draw.text((((width + 10)-top_width)/2,10), Top_text, (0, 0, 0),font = font, stroke_width=2,stroke_fill="black")
            # draw.text((((width + 10)-botton_width)/2,height+70),Bottom, (0, 0, 0),font = font, stroke_width=2,stroke_fill="black")
            draw.text((((width + 10)-top_width)/2,10), Top_text, (0, 0, 0),font = font)
            draw.text((((width + 10)-botton_width)/2,height+70),Bottom, (0, 0, 0),font = font)

            background.paste(im, (0,70))
            file_name = f"{settings.BASE_DIR}/media/{i.city}.{i.cc}.png"
            output = BytesIO()
            background.save(output, format='png', quality=100)

            output.seek(0)
            background = InMemoryUploadedFile(output,'ImageField',file_name , 'image/jpeg', sys.getsizeof(output), None)
            StoreQR.objects.create(scheme = instance,store = i,qr = background,url =s )

@receiver(post_save, sender=Scheme)
def create_store_qr(sender, instance, created,*args, **kwargs):
    m2m_changed.connect(my_m2m_signal, sender=instance.stores.through)

@receiver(post_save, sender=Participant)
def create_image_signature(sender, instance, created, **kwargs):
    print('yes called')
    if created:
        print('yes created')
        filename =instance.bill_image.url
        img = wand.image.Image(width=100, height=100, filename=filename)
        instance.bill_signature = img.signature
        signature_count = Participant.objects.filter(bill_signature = img.signature).count()
        if signature_count > 0:
            instance.is_duplicate  = True
        instance.save()    
    else:
        print('Not created')
    
@receiver(pre_delete, sender=Store)
def remove_schemes(sender, instance, **kwargs):
    storeqr = StoreQR.objects.filter(store = instance)
    storeqr.update(is_active = False)