#!/bin/bash

# Simple startup script for Counselor Project
# Quick version without verbose output

cd /home/itpc6/Public/django/git-repo/7nov/git/
source envp10-13/bin/activate
# python manage.py makemigrations
# python manage.py migrate
cd /home/itpc6/Public/django/git-repo/7nov/git/new_template-demo-topteens/demo-topteens
python manage.py runserver 0.0.0.0:8002
