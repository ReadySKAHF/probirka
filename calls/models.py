from django.db import models


class Call(models.Model):
    id = models.BigAutoField(primary_key=True)
    from_ip = models.CharField(max_length=45, null=True, blank=True)
    to_ip = models.CharField(max_length=45, null=True, blank=True)
    call_id = models.CharField(max_length=64, null=True, blank=True)
    from_number = models.CharField(max_length=32, null=True, blank=True)
    to_number = models.CharField(max_length=32, null=True, blank=True)
    calling_date = models.DateField(null=True, blank=True)
    calling_time = models.TimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'calls'
        ordering = ['-calling_date', '-calling_time', '-id']

    def __str__(self):
        return f'{self.from_number} -> {self.to_number} ({self.calling_date})'
