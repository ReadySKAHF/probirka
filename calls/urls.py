from django.urls import path

from . import views

app_name = 'calls'

urlpatterns = [
    path('', views.call_list, name='call_list'),
    path('call/<int:pk>/', views.call_detail, name='call_detail'),
]
