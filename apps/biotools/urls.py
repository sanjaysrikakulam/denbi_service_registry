from django.urls import path
from . import views

app_name = "biotools"

urlpatterns = [
    path("prefill/", views.biotools_prefill, name="prefill"),
    path("search/", views.biotools_search, name="search"),
]
