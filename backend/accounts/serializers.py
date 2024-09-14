from django.contrib.auth.models import User
from django.db.models import Sum
from rest_framework import serializers

from .models import UserProfile
from radius.models import Radacct


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializes UserProfile objects from django model to JSON."""

    class Meta:
        """UserProfileSerializer metadata."""

        model = UserProfile
        fields = "__all__"
        read_only_fields = ("user",)

    num_sessions = serializers.SerializerMethodField()
    bytes_recv = serializers.SerializerMethodField()
    bytes_sent = serializers.SerializerMethodField()

    def sessions(self, user: User):
        return Radacct.objects.filter(username=user.username)

    def get_num_sessions(self, profile: UserProfile) -> int:
        return self.sessions(profile.user).count()

    def get_bytes_recv(self, profile: UserProfile) -> int:
        return self.sessions(profile.user).aggregate(Sum("acctinputoctets"))[
            "acctinputoctets__sum"
        ]

    def get_bytes_sent(self, profile: UserProfile) -> int:
        return self.sessions(profile.user).aggregate(Sum("acctoutputoctets"))[
            "acctoutputoctets__sum"
        ]


class UserSerializer(serializers.ModelSerializer):
    """Serializes User objects from django model to JSON."""

    profile = UserProfileSerializer(required=False)
    groups = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")

    class Meta:
        """UserSerializer metadata."""

        model = User
        fields = "__all__"
        write_only_fields = ("password",)

    def create(self, validated_data):
        """Update profile after creating the user."""
        profile_data = validated_data.pop("profile", None)
        user = super().create(validated_data)
        if profile_data:
            profile_serializer = UserProfileSerializer(user.profile, data=profile_data)
            profile_serializer.is_valid(raise_exception=True)
            profile_serializer.save()
        return user
