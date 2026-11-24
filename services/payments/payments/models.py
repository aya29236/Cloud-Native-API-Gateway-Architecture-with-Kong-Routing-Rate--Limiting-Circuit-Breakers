"""Payment model (V2.2).

Follows the professor's ORM lesson: one model class = one table, fields
describe the structure, `objects` is the query entry point, `auto_now_add`
records insert time, and `__str__` gives a readable representation.

`account_id` is an integer, not a ForeignKey: Accounts is a separate service,
so crossing a service boundary with a database constraint would couple their
deployments. The value is the account id supplied by the client.
"""

from django.db import models


class Payment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    account_id = models.IntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    # Value of the X-Consumer-Username header forwarded by Kong's JWT plugin.
    consumer = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment #{self.id} account={self.account_id} {self.amount} {self.currency} ({self.status})"
