from django.contrib import admin
from .models import Expense, Friend, Group, GroupMember, SplitExpense, SplitShare

admin.site.register(Expense)
admin.site.register(Friend)
admin.site.register(Group)
admin.site.register(GroupMember)
admin.site.register(SplitExpense)
admin.site.register(SplitShare)