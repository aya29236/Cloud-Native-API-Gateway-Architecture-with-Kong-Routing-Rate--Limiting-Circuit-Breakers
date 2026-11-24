"""DRF serializer for Payments (V2.3).

C1 separates client input (`PaymentCreate`: account_id, amount, currency) from
the stored response (`Payment`: plus id, status, consumer, created_at). A
plain ModelSerializer would accept `status` and `consumer` from the client, so
those are read-only and `validate()` rejects any unexpected input key.
"""

from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    CREATE_INPUT_FIELDS = {"account_id", "amount", "currency"}

    class Meta:
        model = Payment
        fields = [
            "id",
            "account_id",
            "amount",
            "currency",
            "status",
            "consumer",
            "created_at",
        ]
        extra_kwargs = {
            "account_id": {"required": True},
            "amount": {"required": True},
            "currency": {"required": True, "min_length": 3, "max_length": 3},
            # Server-owned fields: Kong supplies the consumer, the model
            # supplies status and created_at.
            "status": {"read_only": True},
            "consumer": {"read_only": True},
            "created_at": {"read_only": True},
        }

    def validate(self, attrs):
        unknown = set(self.initial_data) - self.CREATE_INPUT_FIELDS
        if unknown:
            raise serializers.ValidationError({"unexpected_fields": sorted(unknown)})
        return attrs
