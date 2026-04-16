import json
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models.functions import TruncMonth
from django.db.models import Sum

from .forms import RegisterForm, FriendForm, GroupForm, SplitExpenseForm
from .models import Expense, Friend, Group, GroupMember, SplitExpense, SplitShare
from django.http import JsonResponse

def home(request):
    return render(request, 'home.html')


def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})


@login_required
def dashboard(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        amount = request.POST.get('amount')
        date = request.POST.get('date')

        is_long_term = request.POST.get('is_long_term') == 'on'
        end_date = request.POST.get('end_date') or None
        interest_rate = request.POST.get('interest_rate') or None

        Expense.objects.create(
            user=request.user,
            name=name,
            amount=amount,
            date=date,
            is_long_term=is_long_term,
            end_date=end_date,
            interest_rate=interest_rate if interest_rate else None
        )

        return redirect('dashboard')

    expenses = Expense.objects.filter(user=request.user).order_by('-date')

    monthly = (
        Expense.objects.filter(user=request.user)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )

    labels = []
    data = []

    for m in monthly:
        labels.append(m['month'].strftime('%b %Y'))
        data.append(float(m['total']))

    total_personal = Expense.objects.filter(user=request.user).aggregate(total=Sum('amount'))['total'] or 0
    total_groups = Group.objects.filter(user=request.user).count()
    total_friends = Friend.objects.filter(user=request.user).count()
    total_split_expenses = SplitExpense.objects.filter(group__user=request.user).count()

    return render(request, 'dashboard.html', {
        'expenses': expenses,
        'labels': json.dumps(labels),
        'data': json.dumps(data),
        'total_personal': total_personal,
        'total_groups': total_groups,
        'total_friends': total_friends,
        'total_split_expenses': total_split_expenses,
    })


@login_required
def friends_list(request):
    friends = Friend.objects.filter(user=request.user).order_by('name')

    if request.method == 'POST':
        form = FriendForm(request.POST)
        if form.is_valid():
            friend = form.save(commit=False)
            friend.user = request.user
            friend.save()
            return redirect('friends_list')
    else:
        form = FriendForm()

    return render(request, 'friends.html', {
        'friends': friends,
        'form': form
    })


@login_required
def delete_friend(request, friend_id):
    friend = get_object_or_404(Friend, id=friend_id, user=request.user)
    friend.delete()
    return redirect('friends_list')


@login_required
def groups_list(request):
    groups = Group.objects.filter(user=request.user).order_by('-created_at')

    if request.method == 'POST':
        form = GroupForm(request.POST, user=request.user)
        if form.is_valid():
            group = Group.objects.create(
                user=request.user,
                name=form.cleaned_data['name']
            )
            selected_members = form.cleaned_data['members']
            for member in selected_members:
                GroupMember.objects.get_or_create(group=group, friend=member)
            return redirect('groups_list')
    else:
        form = GroupForm(user=request.user)

    group_data = []
    for group in groups:
        members_count = Friend.objects.filter(groupmember__group=group).distinct().count()
        total_amount = SplitExpense.objects.filter(group=group).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        group_data.append({
            'group': group,
            'members_count': members_count,
            'total_amount': total_amount,
        })

    return render(request, 'groups.html', {
        'groups': group_data,
        'form': form
    })


@login_required
def delete_group(request, group_id):
    group = get_object_or_404(Group, id=group_id, user=request.user)
    group.delete()
    return redirect('groups_list')


@login_required
def group_detail(request, group_id):
    group = get_object_or_404(Group, id=group_id, user=request.user)
    members = Friend.objects.filter(groupmember__group=group).distinct().order_by('name')
    expenses = SplitExpense.objects.filter(group=group).order_by('-created_at').prefetch_related('shares')

    total_group_amount = expenses.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    balances = defaultdict(Decimal)
    expense_rows = []

    for expense in expenses:
        shares = expense.shares.all()
        per_person = shares[0].share_amount if shares else Decimal('0.00')

        expense_rows.append({
            'title': expense.title,
            'paid_by': expense.paid_by.name,
            'total_amount': expense.total_amount,
            'per_person': per_person,
            'created_at': expense.created_at,
            'shares': shares,
        })

        for share in shares:
            if share.friend != expense.paid_by:
                balances[(share.friend.name, expense.paid_by.name)] += share.share_amount

    settlement_data = []
    for (debtor, creditor), amount in balances.items():
        settlement_data.append({
            'debtor': debtor,
            'creditor': creditor,
            'amount': amount
        })

    return render(request, 'group_detail.html', {
        'group': group,
        'members': members,
        'expenses': expense_rows,
        'total_group_amount': total_group_amount,
        'member_count': members.count(),
        'settlements': settlement_data,
    })


@login_required
def split_expense(request):
    expenses = SplitExpense.objects.filter(group__user=request.user).order_by('-created_at')

    if request.method == 'POST':
        form = SplitExpenseForm(request.POST, user=request.user)
        if form.is_valid():
            split_expense_obj = form.save()

            members = Friend.objects.filter(groupmember__group=split_expense_obj.group).distinct()
            member_count = members.count()

            if member_count > 0:
                total = Decimal(split_expense_obj.total_amount)
                share = (total / member_count).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                created_shares = []
                total_created = Decimal('0.00')

                for index, member in enumerate(members):
                    amount = share
                    if index == member_count - 1:
                        amount = total - total_created

                    created_shares.append(
                        SplitShare(
                            expense=split_expense_obj,
                            friend=member,
                            share_amount=amount
                        )
                    )
                    total_created += amount

                SplitShare.objects.bulk_create(created_shares)

            return redirect('split_expense')
    else:
        form = SplitExpenseForm(user=request.user)

    expense_data = []
    for expense in expenses:
        shares = expense.shares.all()
        per_person = shares[0].share_amount if shares else Decimal('0.00')
        expense_data.append({
            'expense': expense,
            'per_person': per_person,
            'member_count': shares.count(),
        })

    return render(request, 'split_expense.html', {
        'form': form,
        'expenses': expense_data
    })


@login_required
def settlements(request):
    groups = Group.objects.filter(user=request.user)
    balances = defaultdict(Decimal)

    for expense in SplitExpense.objects.filter(group__in=groups).prefetch_related('shares'):
        paid_by = expense.paid_by
        for share in expense.shares.all():
            if share.friend != paid_by:
                balances[(share.friend.name, paid_by.name)] += share.share_amount

    settlement_data = []
    for (debtor, creditor), amount in balances.items():
        settlement_data.append({
            'debtor': debtor,
            'creditor': creditor,
            'amount': amount
        })

    return render(request, 'settlements.html', {
        'settlements': settlement_data
    })
@login_required
def group_members_api(request, group_id):
    group = get_object_or_404(Group, id=group_id, user=request.user)
    members = Friend.objects.filter(groupmember__group=group).distinct().values('id', 'name')
    return JsonResponse(list(members), safe=False)