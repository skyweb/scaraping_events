from rest_framework import serializers


class AITransformModelsInfoSerializer(serializers.Serializer):
    message = serializers.CharField()
    params = serializers.JSONField()
    providers = serializers.DictField(child=serializers.ListField(child=serializers.CharField()))
    quota = serializers.JSONField()


class AITransformSingleRequestSerializer(serializers.Serializer):
    model = serializers.CharField(required=False)
    thinking = serializers.BooleanField(required=False)
    event = serializers.JSONField(required=False)


class AITransformSingleResponseSerializer(serializers.Serializer):
    model = serializers.CharField()
    provider = serializers.CharField()
    thinking = serializers.BooleanField()
    event = serializers.JSONField()
    quota = serializers.JSONField()


class AITransformFileRequestSerializer(serializers.Serializer):
    model = serializers.CharField(required=False)
    thinking = serializers.BooleanField(required=False)
    file_path = serializers.CharField(required=False)
    limit = serializers.IntegerField(required=False, min_value=0)


class AITransformFileResponseSerializer(serializers.Serializer):
    model = serializers.CharField()
    provider = serializers.CharField()
    thinking = serializers.BooleanField()
    source_file = serializers.CharField()
    total_events = serializers.IntegerField()
    processed = serializers.IntegerField()
    errors_count = serializers.IntegerField()
    events = serializers.ListField(child=serializers.JSONField())
    errors = serializers.ListField(child=serializers.JSONField())


class AITransformErrorSerializer(serializers.Serializer):
    error = serializers.CharField()
