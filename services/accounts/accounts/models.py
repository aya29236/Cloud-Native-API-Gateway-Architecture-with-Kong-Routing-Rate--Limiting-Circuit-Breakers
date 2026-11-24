"""
Account model (V1.4).

Following the professor's ORM lesson:
- one model class = one database table;
- fields describe the table structure (no raw SQL);
- `objects` is the default manager and every query starts there;
- `auto_now_add` records creation time at insert;
- `__str__` gives a readable representation in shell and Django Admin.

This is the first ORM code in the project. It is introduced here, after the
structure, health endpoint and gateway headers were verified independently.
"""

from django.db import models


class Account(models.Model):
    owner = models.CharField(max_length=200)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="TND")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.owner} ({self.balance} {self.currency})"
