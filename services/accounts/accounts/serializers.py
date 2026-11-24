"""DRF serializers for the Accounts service (V1.5).

The professor's lesson presents a serializer as a translator:
  model object  ->  Python dict  ->  JSON  (.data)
  JSON          ->  Python dict  ->  validated model data

C1 additionally requires `additionalProperties: false` for Account and
AccountCreate. DRF ignores unknown fields by default, so `validate()` rejects
them explicitly to keep the service faithful to the frozen contract.
"""

from rest_framework import serializers

from .models import Account


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ["id", "owner", "balance", "currency", "created_at"]
        extra_kwargs = {
            # The model declares defaults, but C1 makes all three fields
            # required on input. DRF would otherwise mark them optional.
            "owner": {"required": True},
            "balance": {"required": True},
            "currency": {"required": True, "min_length": 3},
            "created_at": {"read_only": True},
        }

    def validate(self, attrs):
        unknown = set(self.initial_data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {"unexpected_fields": sorted(unknown)}
            )
        return attrs
