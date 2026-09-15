from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render


def landing_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "accounts/landing.html")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = AuthenticationForm(request, data=request.POST or None)
    for field in form.fields.values():
        field.widget.attrs["class"] = "form-control"

    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("dashboard")

    return render(request, "accounts/login.html", {"form": form})


def codex_cli_guide_view(request):
    return render(request, "accounts/codex_cli_guide.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("landing")

# Create your views here.
