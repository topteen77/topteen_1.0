from django.db import models
from django.conf import settings
from core import choices
# Create your models here.

class CommunicationLog(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    to  = models.CharField(max_length=500)
    body = models.TextField()
    response = models.TextField()
    type =  models.PositiveSmallIntegerField(choices=choices.CommunicationTypeChooices.CHOICES)
    def __str__(self):
        return "{} ({})".format(self.to,self.get_type_display())

class OTP(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    user  = models.CharField(max_length=500)
    otp = models.CharField(max_length=10)
    type =  models.PositiveSmallIntegerField(choices=choices.CommunicationTypeChooices.CHOICES)

    def __str__(self):
        return "{} ({}) : ".format(self.user, self.get_type_display(), self.otp)
