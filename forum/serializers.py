from rest_framework import serializers
from forum.models import Query, Response, Category, Country, KnowledgeBaseEntry, AIFeature, AICapability


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'icon']


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name', 'code', 'flag_emoji', 'metadata']


class QuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = Query
        fields = ['id', 'question_text', 'category', 'country_context', 'status', 'created_at', 'processed_at']
        read_only_fields = ['id', 'status', 'created_at', 'processed_at']


class ResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Response
        fields = ['id', 'query', 'response_text', 'confidence_score', 'sources', 'generated_at']
        read_only_fields = ['id', 'generated_at']


class QueryWithResponseSerializer(serializers.ModelSerializer):
    response = ResponseSerializer(read_only=True)
    
    class Meta:
        model = Query
        fields = ['id', 'question_text', 'category', 'country_context', 'status', 'created_at', 'response']


class KnowledgeBaseEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeBaseEntry
        fields = ['id', 'country', 'category', 'title', 'content', 'last_updated']


class AIFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIFeature
        fields = ['id', 'name', 'icon', 'description', 'order']


class AICapabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = AICapability
        fields = ['id', 'name', 'icon', 'description', 'order']
