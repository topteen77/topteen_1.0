import django_filters
from institute.models import StudentManagement
from django.db import models

class StudentFilter(django_filters.FilterSet):
    student_name=django_filters.CharFilter(
        field_name='student__name',
        lookup_expr='icontains',
        label='Student Name',
        )
    student_email=django_filters.CharFilter(
        field_name='student__email',
        lookup_expr='icontains',
        label='Student Email',
        )
    class_and_section=django_filters.CharFilter(
        field_name='class_and_section__class_and_section',
        lookup_expr='icontains',
        label='Student Name',
        )
    search_term=django_filters.CharFilter(
        method='filter_by_search_term',
        label='Search',
    )
    test_taken=django_filters.CharFilter(
        method='filter_by_test_taken',
        label='Test Taken Search',
    )
    class META:
        model=StudentManagement
        fields=['student_name','student_email','class_and_section']

    def filter_by_search_term(self,queryset,name,value):
        return queryset.filter(
            models.Q(student__name__icontains=value)|
            models.Q(student__email__icontains=value)|
            models.Q(class_and_section__class_and_section__icontains=value)
        )
    
    def filter_by_test_taken(self,queryset,name,value):
        # This method is not used anymore as we handle test_taken filtering in the view
        # to properly support "In Progress" status
        return queryset