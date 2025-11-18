from django.db import models
from core.models import BaseModel
from users.models import User
from core import choices

class Lead(BaseModel):
    user = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name="leads")
    action=models.PositiveSmallIntegerField(choices=choices.LeadAction.CHOICES)
    status=models.PositiveSmallIntegerField(choices=choices.LeadStatus.CHOICES,default=choices.LeadStatus.FRESH)