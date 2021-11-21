from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .forms import UserRegistrationForm


@csrf_exempt
def main(request):
    if request.user.is_authenticated:
        username = request.user.username
        user_hash = request.user._legacy_get_session_auth_hash()
        return render(request, 'main.html',
                      {'username': username, 'user_hash': user_hash})
    else:
        return HttpResponseRedirect('/login/')


def register(request):
    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)

        if user_form.is_valid():
            new_user = user_form.save(commit=False)
            new_user.set_password(user_form.cleaned_data['password'])
            new_user.save()
            return HttpResponseRedirect('/')
    else:
        user_form = UserRegistrationForm()
    return render(request, 'register.html', {'user_form': user_form})
